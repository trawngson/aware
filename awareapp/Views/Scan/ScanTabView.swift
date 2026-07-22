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
    
    private let confidenceThreshold: Double = 0.4
    private let autoConfirmThreshold: Double = 0.75
    private let stableDetectionDuration: TimeInterval = 1.0
    
    // Camera should be active only when tab is active and not showing results
    private var shouldCameraBeActive: Bool {
        isTabActive && !showResults
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
                                dismissResults()
                            }
                        )
                        .navigationBarBackButtonHidden(true)
                        .toolbar {
                            ToolbarItem(placement: .navigationBarLeading) {
                                Button {
                                    dismissResults()
                                } label: {
                                    HStack(spacing: 4) {
                                        Image(systemName: "chevron.left")
                                            .font(.system(size: 16, weight: .semibold))
                                        Text("Back")
                                    }
                                    .foregroundColor(.blue)
                                }
                            }
                        }
                    }
                }
                .navigationBarHidden(true)
        }
        .onChange(of: isTabActive) { _, isActive in
            if !isActive {
                // Cancel any pending timers when leaving tab
                stableDetectionTimer?.invalidate()
                stableDetectionTimer = nil
                stableDetectionLabel = nil
                noDetectionTimer?.invalidate()
                noDetectionTimer = nil
            }
        }
    }
    
    private var mainScanView: some View {
        ZStack {
            backgroundView
            
            VStack(spacing: 0) {
                cameraSection
                detectionSection
            }
        }
        .overlay(alignment: .topTrailing) {
            debugButton
        }
    }
    
    private func dismissResults() {
        showResults = false
        confirmedDetection = nil
        capturedImage = nil
        // Reset detection state to allow new scans
        hasHadDetection = false
        viewfinderVisible = true
    }
    
    // MARK: - Debug Button
    
    private var debugButton: some View {
        Button {
            showDebug.toggle()
        } label: {
            Image(systemName: showDebug ? "ladybug.fill" : "ladybug")
                .font(.system(size: 18))
                .foregroundStyle(showDebug ? .green : .secondary)
                .padding(10)
                .background(.ultraThinMaterial, in: Circle())
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 4)
        .padding(16)
    }
    
    // MARK: - Camera Section
    
    private var cameraSection: some View {
        ZStack {
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
            .overlay(alignment: .topLeading) {
                if showDebug { statusBadge }
            }
            .overlay(alignment: .topLeading) {
                if showDebug {
                    debugMetricsView.offset(y: 40)
                }
            }
            .overlay(alignment: .center) {
                if viewfinderVisible {
                    scanOverlay
                        .transition(
                            .asymmetric(
                                insertion: .scale(scale: 1.2).combined(with: .opacity),
                                removal: .scale(scale: 0.8).combined(with: .opacity)
                            )
                        )
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 24, style: .continuous)
                    .stroke(Color.white.opacity(0.2), lineWidth: 1)
            )
        }
        .frame(maxWidth: .infinity)
        .frame(height: UIScreen.main.bounds.height * 0.55)
        .padding(.horizontal)
        .padding(.top, 8)
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
               topDetection.label.contains("bottle") {
                
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
    
    // MARK: - Debug Views
    
    private var debugMetricsView: some View {
        VStack(alignment: .trailing, spacing: 2) {
            Text("Frames: \(frameCount)")
            Text("Detections: \(detections.count)")
        }
        .font(.caption2.monospaced())
        .foregroundStyle(.white)
        .padding(8)
        .background(.black.opacity(0.5), in: RoundedRectangle(cornerRadius: 8))
        .padding(16)
    }
    
    private var statusBadge: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(Color.green)
                .frame(width: 8, height: 8)
            Text("Scanning")
                .font(.caption.weight(.medium))
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(.ultraThinMaterial, in: Capsule())
        .padding(16)
    }
    
    private var scanOverlay: some View {
        VStack(spacing: 12) {
            PulsingViewfinder()
            
            Text("Point at an object")
                .font(.subheadline.weight(.medium))
                .foregroundStyle(.white.opacity(0.8))
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 16)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    }
    
    // MARK: - Detection Section
    
    private var detectionSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Detected Items")
                    .font(.headline)
                Spacer()
                if !detections.isEmpty {
                    Text("\(detections.count) item\(detections.count > 1 ? "s" : "")")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }
            .padding(.horizontal)
            
            if detections.isEmpty {
                emptyDetectionView
            } else {
                detectionList
            }
        }
        .padding(.top, 20)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
    }
    
    private var emptyDetectionView: some View {
        VStack(spacing: 4) {
            Image(systemName: "sparkle.magnifyingglass")
                .font(.system(size: 36))
                .foregroundStyle(.secondary)
                .padding(.bottom, 8)
            
            Text("No items detected")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            
            Text("Pinch to zoom in or adjust lighting")
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 32)
    }
    
    private var detectionList: some View {
        VStack(spacing: 12) {
            ForEach(detections) { detection in
                let index = detections.firstIndex(where: { $0.id == detection.id }) ?? 0
                DetectionCardView(
                    rank: index + 1,
                    label: detection.label,
                    confidence: detection.confidence,
                    color: colorForConfidence(detection.confidence)
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
        .padding(.horizontal)
        .animation(.easeOut(duration: 0.35), value: detections.map { "\($0.id)-\($0.label)" })
    }

    // MARK: - Helpers

    private func colorForConfidence(_ confidence: Double) -> Color {
        if confidence >= 0.85 { return .green }
        else if confidence >= 0.70 { return .yellow }
        else { return .orange }
    }

    private var backgroundView: some View {
        ZStack(alignment: .top) {
            Color(uiColor: .systemGroupedBackground)
                .ignoresSafeArea()
            LinearGradient(
                stops: [
                    .init(color: Color.green.opacity(0.3), location: 0.0),
                    .init(color: Color.green.opacity(0.1), location: 0.2),
                    .init(color: Color.green.opacity(0.0), location: 0.4)
                ],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()
        }
    }
}

// MARK: - Preview

#Preview {
    // Use a sample image from assets for preview
    let sampleImage = UIImage(named: "SampleImage")
    let sampleDetection = YOLODetection(
        id: 0,
        label: "plastic_bottle",
        confidence: 0.92,
        boundingBox: CGRect(x: 0.3, y: 0.3, width: 0.2, height: 0.2)
    )
    ScanTabView(
        isTabActive: true
    )
    .environmentObject(PreviewImage(sampleImage))
}
