import AVFoundation
import SwiftUI
import YOLO

// Define a simple PreviewImage class to hold the sample image for preview purposes
final class PreviewImage: ObservableObject {
    @Published var image: UIImage?

    init(_ image: UIImage?) {
        self.image = image
    }
}

struct ScanTabView: View {
    var isTabActive: Bool = true  // Passed from parent TabView
    
    @State private var detections: [YOLODetection] = []
    @State private var frameCount: Int = 0
    @State private var showDebug: Bool = false
    @State private var hasHadDetection: Bool = false
    @State private var showViewfinder: Bool = true
    @State private var noDetectionTimer: Timer? = nil
    @State private var viewfinderVisible: Bool = true
    @State private var showResults: Bool = false
    @State private var confirmedDetection: YOLODetection? = nil
    @State private var stableDetectionTimer: Timer? = nil
    @State private var stableDetectionLabel: String? = nil
    @State private var capturedImage: UIImage? = nil
    @State private var isTorchOn: Bool = false
    
    private let confidenceThreshold: Double = 0.4
    private let autoConfirmThreshold: Double = 0.75
    private let stableDetectionDuration: TimeInterval = 1.0
    
    // Camera should be active only when tab is active and not showing results
    private var shouldCameraBeActive: Bool {
        isTabActive && !showResults
    }

    /// Portrait width / height of the camera frames, for placing boxes.
    private var frameAspect: CGFloat {
        guard let size = capturedImage?.size, size.height > 0 else { return 3.0 / 4.0 }
        return size.width / size.height
    }
    
    var body: some View {
        NavigationStack {
            mainScanView
                .navigationDestination(isPresented: $showResults) {
                    if let detection = confirmedDetection {
                        ScanResultsView(
                            detection: detection,
                            capturedImage: capturedImage,
                            onDismiss: {
                                showResults = false
                            }
                        )
                    }
                }
                .navigationBarTitleDisplayMode(.inline)
                .toolbarColorScheme(.dark, for: .navigationBar)
                .toolbar {
                    ToolbarItem(placement: .topBarLeading) { statusPill }
                    ToolbarItemGroup(placement: .topBarTrailing) {
                        if Torch.isAvailable {
                            Button {
                                isTorchOn = Torch.set(!isTorchOn)
                            } label: {
                                Image(systemName: isTorchOn ? "bolt.fill" : "bolt")
                            }
                            .accessibilityLabel(isTorchOn ? "Turn off flashlight" : "Turn on flashlight")
                        }
                        Button {
                            showDebug.toggle()
                        } label: {
                            Image(systemName: "slider.horizontal.3")
                                .symbolVariant(showDebug ? .fill : .none)
                        }
                        .accessibilityLabel(showDebug ? "Hide detector details" : "Show detector details")
                    }
                }
        }
        .tint(.white)
        .onChange(of: showResults) { _, isShowing in
            if isShowing {
                turnTorchOff()
            } else {
                dismissResults()
            }
        }
        .onChange(of: isTabActive) { _, isActive in
            if !isActive {
                // Cancel any pending timers when leaving tab
                stableDetectionTimer?.invalidate()
                stableDetectionTimer = nil
                stableDetectionLabel = nil
                noDetectionTimer?.invalidate()
                noDetectionTimer = nil
                turnTorchOff()
            }
        }
    }
    
    private var mainScanView: some View {
        GeometryReader { proxy in
            let fullHeight = proxy.size.height + proxy.safeAreaInsets.top + proxy.safeAreaInsets.bottom
            let cameraHeight = fullHeight * 0.64
            let listTop = cameraHeight - proxy.safeAreaInsets.top - 118

            ZStack(alignment: .top) {
                Theme.scanDark
                    .ignoresSafeArea()

                cameraSection
                    .frame(height: cameraHeight)
                    .ignoresSafeArea(edges: .top)

                VStack(spacing: 0) {
                    ZStack {
                        if viewfinderVisible {
                            PulsingViewfinder()
                                .transition(
                                    .asymmetric(
                                        insertion: .scale(scale: 1.2).combined(with: .opacity),
                                        removal: .scale(scale: 0.8).combined(with: .opacity)
                                    )
                                )
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .frame(height: max(listTop, 0))
                    .overlay(alignment: .topLeading) {
                        if showDebug { debugMetricsView }
                    }

                    detectionSection
                }
            }
        }
    }
    
    private func dismissResults() {
        confirmedDetection = nil
        // Reset detection state to allow new scans
        hasHadDetection = false
        viewfinderVisible = true
    }

    private func turnTorchOff() {
        if isTorchOn {
            isTorchOn = Torch.set(false)
        }
    }
    
    // MARK: - Camera Section
    
    private var cameraSection: some View {
        // Keep camera alive but pause inference when not active
        CleanYOLOCamera(
            modelPathOrName: "aware",
            task: .detect,
            cameraPosition: .back,
            confidenceThreshold: 0.4,
            showDebug: showDebug,
            isActive: shouldCameraBeActive,
            onDetection: { result in
                handleDetectionResult(result)
            },
            onFrameCapture: { image in
                // Store the latest frame for potential capture
                capturedImage = image
            }
        )
        .overlay {
            if !showDebug {
                DetectionOverlay(detections: detections, frameAspect: frameAspect,
                                 strongThreshold: autoConfirmThreshold)
            }
        }
        .overlay {
            LinearGradient(
                stops: [
                    .init(color: Theme.scanShade.opacity(0.45), location: 0),
                    .init(color: Theme.scanShade.opacity(0.05), location: 0.28),
                    .init(color: Theme.scanShade.opacity(0.15), location: 0.62),
                    .init(color: Theme.scanDark.opacity(0.9), location: 0.96),
                    .init(color: Theme.scanDark, location: 1),
                ],
                startPoint: .top, endPoint: .bottom
            )
            .allowsHitTesting(false)
        }
        .clipped()
    }
    
    // MARK: - Detection Handler
    
    private func handleDetectionResult(_ result: YOLOResult) {
        // Skip processing if already showing results or camera inactive
        guard !showResults, shouldCameraBeActive else { return }
        
        DispatchQueue.main.async {
            frameCount += 1
            
            let filteredBoxes = result.boxes
                .filter { Double($0.conf) >= confidenceThreshold }
                .sorted { $0.conf > $1.conf }
            
            detections = filteredBoxes.prefix(3).enumerated().map { index, box in
                YOLODetection(
                    id: index,
                    label: box.cls,
                    confidence: Double(box.conf),
                    boundingBox: box.xywhn
                )
            }
            
            // Check for stable high-confidence detection
            if let topDetection = detections.first,
               topDetection.confidence >= autoConfirmThreshold,
               CanonicalLabel(modelLabel: topDetection.label) != nil {
                
                // Same item as before - timer is already running
                if stableDetectionLabel == topDetection.label {
                    // Timer will fire when ready
                } else {
                    // New item detected - start/restart timer
                    stableDetectionTimer?.invalidate()
                    stableDetectionLabel = topDetection.label
                    
                    stableDetectionTimer = Timer.scheduledTimer(withTimeInterval: stableDetectionDuration, repeats: false) { _ in
                        DispatchQueue.main.async {
                            // Verify detection is still valid
                            if let currentTop = self.detections.first,
                               currentTop.label == self.stableDetectionLabel,
                               currentTop.confidence >= self.autoConfirmThreshold {
                                self.confirmedDetection = currentTop
                                withAnimation {
                                    self.showResults = true
                                }
                            }
                            self.stableDetectionTimer = nil
                            self.stableDetectionLabel = nil
                        }
                    }
                }
            } else {
                // No high-confidence detection - cancel timer
                stableDetectionTimer?.invalidate()
                stableDetectionTimer = nil
                stableDetectionLabel = nil
            }
            
            updateViewfinderVisibility()
        }
    }
    
    private func updateViewfinderVisibility() {
        if !detections.isEmpty {
            hasHadDetection = true
            noDetectionTimer?.invalidate()
            noDetectionTimer = nil
            if viewfinderVisible {
                withAnimation(.easeOut(duration: 0.4)) {
                    viewfinderVisible = false
                }
            }
        } else if hasHadDetection && noDetectionTimer == nil {
            noDetectionTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: false) { _ in
                DispatchQueue.main.async {
                    withAnimation(.easeIn(duration: 0.5)) {
                        viewfinderVisible = true
                    }
                    noDetectionTimer = nil
                }
            }
        }
    }
    
    // MARK: - Status and debug
    
    private var statusPill: some View {
        HStack(spacing: 7) {
            Circle()
                .fill(Theme.detectionGreen)
                .frame(width: 8, height: 8)
                .shadow(color: Theme.detectionGreen.opacity(0.9), radius: 4)
            Text(stableDetectionLabel == nil ? "Scanning" : "Hold steady…")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.white)
                .fixedSize()
        }
        .padding(.horizontal, 6)
        .accessibilityElement(children: .combine)
    }
    
    private var debugMetricsView: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("Frames: \(frameCount)")
            Text("Detections: \(detections.count)")
        }
        .font(.caption2.monospaced())
        .foregroundStyle(.white)
        .padding(8)
        .background(.black.opacity(0.5), in: RoundedRectangle(cornerRadius: 8))
        .padding(16)
    }
    
    // MARK: - Detection Section
    
    private var detectionSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Detected Items")
                    .font(.system(size: 17, weight: .semibold))
                    .tracking(-0.34)
                    .foregroundStyle(.white)
                Spacer()
                if !detections.isEmpty {
                    Text("^[\(detections.count) item](inflect: true)")
                        .font(.system(size: 13))
                        .foregroundStyle(.white.opacity(0.65))
                }
            }
            .padding(.horizontal, 4)
            
            if detections.isEmpty {
                emptyDetectionView
            } else {
                detectionList
            }
        }
        .padding(.horizontal, 16)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
    }
    
    private var emptyDetectionView: some View {
        HStack(spacing: 14) {
            Image(systemName: "sparkle.magnifyingglass")
                .font(.system(size: 18))
                .foregroundStyle(.white.opacity(0.8))
                .frame(width: 40, height: 40)
                .background(RoundedRectangle(cornerRadius: 14, style: .continuous).fill(.white.opacity(0.12)))
            VStack(alignment: .leading, spacing: 2) {
                Text("No items detected")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(.white)
                Text("Pinch to zoom in or adjust lighting")
                    .font(.system(size: 13))
                    .foregroundStyle(.white.opacity(0.65))
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 13)
        .glass(.dark, cornerRadius: 20)
    }
    
    private var detectionList: some View {
        VStack(spacing: 10) {
            ForEach(detections) { detection in
                DetectedItemRow(
                    label: detection.label,
                    confidence: detection.confidence,
                    isStrong: detection.confidence >= autoConfirmThreshold
                )
                .id("\(detection.id)-\(detection.label)")
                .transition(
                    .asymmetric(
                        insertion: .scale(scale: 0.85).combined(with: .opacity),
                        removal: .scale(scale: 0.95).combined(with: .opacity)
                    )
                )
            }
        }
        .animation(.easeOut(duration: 0.35), value: detections.map { "\($0.id)-\($0.label)" })
    }
}

// MARK: - Flashlight

/// Turns the back camera's torch on or off while the camera is running.
enum Torch {
    static var isAvailable: Bool {
#if targetEnvironment(simulator)
        false
#else
        bestCaptureDevice(position: .back)?.hasTorch ?? false
#endif
    }

    /// Returns the torch state after the attempt.
    @discardableResult
    static func set(_ on: Bool) -> Bool {
#if targetEnvironment(simulator)
        return false
#else
        guard let device = bestCaptureDevice(position: .back), device.hasTorch else { return false }
        do {
            try device.lockForConfiguration()
            device.torchMode = on ? .on : .off
            device.unlockForConfiguration()
            return device.torchMode == .on
        } catch {
            return false
        }
#endif
    }
}

// MARK: - Preview

#Preview {
    // Use a sample image from assets for preview
    let sampleImage = UIImage(named: "SampleImage")
    ScanTabView(
        isTabActive: true
    )
    .environmentObject(PreviewImage(sampleImage))
    .preferredColorScheme(.dark)
}
