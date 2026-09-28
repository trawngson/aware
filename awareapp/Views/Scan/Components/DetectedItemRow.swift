import SwiftUI

/// One detection in the Scan tab's "Detected Items" list.
struct DetectedItemRow: View {
    let label: String
    let confidence: Double
    /// Confident enough to open the results automatically.
    let isStrong: Bool

    private var accent: Color { isStrong ? Theme.detectionGreen : .white.opacity(0.6) }

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: LabelMappings.iconForLabel(label))
                .font(.system(size: 18))
                .foregroundStyle(isStrong ? Theme.mint : .white.opacity(0.85))
                .frame(width: 40, height: 40)
                .background(RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .fill(isStrong ? Theme.mint.opacity(0.2) : .white.opacity(0.14)))
            VStack(alignment: .leading, spacing: 6) {
                Text(LabelMappings.formatLabel(label))
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(.white)
                HStack(spacing: 8) {
                    ProgressView(value: confidence)
                        .progressViewStyle(.linear)
                        .tint(accent)
                        .animation(.easeOut(duration: 0.3), value: confidence)
                    Text(confidence, format: .percent.precision(.fractionLength(0)))
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(isStrong ? Theme.mint : .white.opacity(0.8))
                        .monospacedDigit()
                        .frame(width: 38, alignment: .trailing)
                        .contentTransition(.numericText())
                }
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 13)
        .glass(.dark, cornerRadius: 20)
        .accessibilityElement(children: .combine)
    }
}

#Preview {
    VStack {
        DetectedItemRow(label: "plastic_bottle", confidence: 0.9, isStrong: true)
        DetectedItemRow(label: "disposable_cup", confidence: 0.55, isStrong: false)
    }
    .padding()
    .background(Theme.scanDark)
}
