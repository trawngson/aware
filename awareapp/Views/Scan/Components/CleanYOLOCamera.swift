import SwiftUI
import AVFoundation
import YOLO

// MARK: - Clean YOLO Camera (hides Ultralytics overlay)

struct CleanYOLOCamera: UIViewRepresentable {
    let modelPathOrName: String
    let task: YOLOTask
    let cameraPosition: AVCaptureDevice.Position
    var confidenceThreshold: Float = 0.5
    var showDebug: Bool = false
    var isActive: Bool = true
    let onDetection: ((YOLOResult) -> Void)?
    var onFrameCapture: ((UIImage) -> Void)?
    
    func makeCoordinator() -> Coordinator {
        Coordinator()
    }
    
    class Coordinator {
        var hasSetThreshold = false
        var lastCapturedImage: UIImage?
        var wasActive = true
    }
    
    func makeUIView(context: Context) -> YOLOView {
        let view = YOLOView(frame: .zero, modelPathOrName: modelPathOrName, task: task)
        if cameraPosition == .front {
            view.pendingCameraPosition = .front
        }
        
        // Set initial visibility based on showDebug
        setOverlayVisibility(in: view, visible: showDebug)
        
        return view
    }
    
    func updateUIView(_ uiView: YOLOView, context: Context) {
        let coordinator = context.coordinator
        
        // Handle camera session pause/resume based on isActive
        if isActive && !coordinator.wasActive {
            // Resuming from inactive state
            uiView.resumeSession()
        } else if !isActive && coordinator.wasActive {
            // Pausing - going inactive
            uiView.pauseSession()
        }
        coordinator.wasActive = isActive
        
        // Only forward detections when active
        if isActive {
            uiView.onDetection = { result in
                // Capture the current frame from the video buffer (clean, no overlays)
                DispatchQueue.main.async {
                    if let image = uiView.captureCurrentFrame() {
                        coordinator.lastCapturedImage = image
                        self.onFrameCapture?(image)
                    }
                }
                self.onDetection?(result)
            }
        } else {
            uiView.onDetection = nil
        }
        
        // Set confidence threshold on first update (after view is fully initialized)
        if !coordinator.hasSetThreshold {
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                uiView.sliderConf.value = self.confidenceThreshold
                uiView.sliderConf.sendActions(for: .valueChanged)
            }
            coordinator.hasSetThreshold = true
        }
        
        // Update visibility based on showDebug
        setOverlayVisibility(in: uiView, visible: showDebug)
    }
    
    private func setOverlayVisibility(in view: YOLOView, visible: Bool) {
        // Show/hide known public properties
        view.labelName.isHidden = !visible
        view.labelFPS.isHidden = !visible
        view.sliderConf.isHidden = !visible
        view.sliderIoU.isHidden = !visible
        view.sliderNumItems.isHidden = !visible
        view.labelSliderConf.isHidden = !visible
        view.labelSliderIoU.isHidden = !visible
        view.labelSliderNumItems.isHidden = !visible
        view.shareButton.isHidden = !visible
        
        // Aggressively hide all subviews that are not the camera preview
        for subview in view.subviews {
            // Check if this subview contains the camera preview layer
            let hasCameraPreview = hasCameraPreviewLayer(subview)
            
            if !hasCameraPreview {
                // This is an overlay view - hide it unless debug is on
                subview.isHidden = !visible
            } else {
                // This contains camera preview - recurse into it to hide nested controls
                setControlsVisibilityRecursively(in: subview, visible: visible)
            }
        }
        
        // Also hide any views positioned in the bottom portion of the view (toolbars)
        let bottomThreshold = view.bounds.height * 0.7
        for subview in view.subviews {
            if subview.frame.origin.y > bottomThreshold && !hasCameraPreviewLayer(subview) {
                subview.isHidden = !visible
            }
        }
    }
    
    private func hasCameraPreviewLayer(_ view: UIView) -> Bool {
        // Check if this view or any of its sublayers is a camera preview
        if let sublayers = view.layer.sublayers {
            for layer in sublayers {
                if layer is AVCaptureVideoPreviewLayer {
                    return true
                }
            }
        }
        // Also check subviews recursively (preview might be nested)
        for subview in view.subviews {
            if hasCameraPreviewLayer(subview) {
                return true
            }
        }
        return false
    }
    
    private func setControlsVisibilityRecursively(in view: UIView, visible: Bool) {
        for subview in view.subviews {
            // Hide UI control elements
            if subview is UILabel || subview is UISlider || subview is UIButton || subview is UIStackView || subview is UIVisualEffectView {
                subview.isHidden = !visible
            }
            
            setControlsVisibilityRecursively(in: subview, visible: visible)
        }
    }
}
