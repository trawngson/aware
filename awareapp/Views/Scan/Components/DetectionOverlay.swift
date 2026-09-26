import SwiftUI

/// Draws the current detections over the camera preview. Boxes arrive as
/// normalized, top-left-origin rects of the full camera frame, and the preview
/// fills its view with aspect-fill, so the frame is scaled and center-cropped
/// the same way here.
struct DetectionOverlay: View {
    let detections: [YOLODetection]
    /// Width / height of the camera frame (portrait).
    let frameAspect: CGFloat
    let strongThreshold: Double

    var body: some View {
        GeometryReader { proxy in
            let fitted = fittedFrame(in: proxy.size)
            ForEach(detections) { detection in
                let rect = CGRect(
                    x: fitted.minX + detection.boundingBox.minX * fitted.width,
                    y: fitted.minY + detection.boundingBox.minY * fitted.height,
                    width: detection.boundingBox.width * fitted.width,
                    height: detection.boundingBox.height * fitted.height
                )
                box(for: detection, in: rect)
            }
        }
        .allowsHitTesting(false)
        .animation(.easeOut(duration: 0.15), value: detections)
    }

    private func fittedFrame(in size: CGSize) -> CGRect {
        guard size.width > 0, size.height > 0, frameAspect > 0 else { return .zero }
        if size.width / size.height > frameAspect {
            let height = size.width / frameAspect
            return CGRect(x: 0, y: (size.height - height) / 2, width: size.width, height: height)
        } else {
            let width = size.height * frameAspect
            return CGRect(x: (size.width - width) / 2, y: 0, width: width, height: size.height)
        }
    }

    private func box(for detection: YOLODetection, in rect: CGRect) -> some View {
        let color = detection.confidence >= strongThreshold ? Theme.detectionGreen : Theme.detectionYellow
        return ZStack(alignment: .topLeading) {
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .strokeBorder(color, lineWidth: 2)
                .background(
                    RoundedRectangle(cornerRadius: 10, style: .continuous)
                        .strokeBorder(color.opacity(0.22), lineWidth: 8)
                        .blur(radius: 6)
                )
                .shadow(color: Theme.scanShade.opacity(0.35), radius: 8, y: 6)
                .frame(width: rect.width, height: rect.height)

            Text("\(LabelMappings.formatLabel(detection.label)) · \(Int((detection.confidence * 100).rounded()))%")
                .font(.system(size: 10, weight: .semibold))
                .foregroundStyle(.white)
                .lineLimit(1)
                .fixedSize()
                .padding(.horizontal, 7)
                .padding(.vertical, 3)
                .background(RoundedRectangle(cornerRadius: 7, style: .continuous).fill(.ultraThinMaterial))
                .background(RoundedRectangle(cornerRadius: 7, style: .continuous).fill(Color(hex: 0x0A1A11, opacity: 0.55)))
                .environment(\.colorScheme, .dark)
                .offset(y: -21)
        }
        .frame(width: rect.width, height: rect.height, alignment: .topLeading)
        .position(x: rect.midX, y: rect.midY)
    }
}
