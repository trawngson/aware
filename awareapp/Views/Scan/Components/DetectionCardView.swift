import SwiftUI

// MARK: - Detection Card View

struct DetectionCardView: View {
    let rank: Int
    let label: String
    let confidence: Double
    let color: Color
    
    @State private var animatedRoundedConfidence: Int = 0
    @State private var animatedColor: Color = .orange
    @State private var isInitialized: Bool = false
    
    var body: some View {
        HStack(spacing: 16) {
            // Rank badge
            ZStack {
                Circle()
                    .fill(animatedColor.opacity(0.15))
                    .frame(width: 44, height: 44)
                
                Text("\(rank)")
                    .font(.headline.weight(.bold))
                    .foregroundStyle(animatedColor)
            }
            
            // Detection info
            VStack(alignment: .leading, spacing: 4) {
                Text(LabelMappings.formatLabel(label))
                    .font(.headline)
                
                HStack(spacing: 8) {
                    // Confidence bar
                    GeometryReader { geometry in
                        ZStack(alignment: .leading) {
                            Capsule()
                                .fill(Color.gray.opacity(0.2))
                            
                            Capsule()
                                .fill(animatedColor)
                                .frame(width: geometry.size.width * (Double(animatedRoundedConfidence) / 100.0))
                        }
                    }
                    .frame(height: 6)
                    
                    Text("\(animatedRoundedConfidence)%")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(animatedColor)
                        .frame(width: 40, alignment: .trailing)
                }
            }
            
            Spacer()
            
            // Category icon - properly centered
            Image(systemName: LabelMappings.iconForLabel(label))
                .font(.title2)
                .foregroundStyle(animatedColor)
                .frame(width: 32, height: 32, alignment: .center)
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(.ultraThinMaterial)
        )
        .onAppear {
            animatedColor = color
            // Animate confidence bar from 0 on appear
            withAnimation(.easeOut(duration: 0.4).delay(0.1)) {
                animatedRoundedConfidence = roundToNearest5(confidence)
            }
            isInitialized = true
        }
        .onChange(of: confidence) { _, newValue in
            guard isInitialized else { return }
            let newRounded = roundToNearest5(newValue)
            if newRounded != animatedRoundedConfidence {
                withAnimation(.easeInOut(duration: 0.3)) {
                    animatedRoundedConfidence = newRounded
                }
            }
        }
        .onChange(of: color) { _, newValue in
            withAnimation(.easeInOut(duration: 0.3)) {
                animatedColor = newValue
            }
        }
    }
    
    private func roundToNearest5(_ value: Double) -> Int {
        let percentage = value * 100
        return Int((percentage / 5).rounded() * 5)
    }
}

// MARK: - Preview

#Preview {
    DetectionCardView(
        rank: 1,
        label: "plastic bottle",
        confidence: 0.85,
        color: .green
    )
    .padding()
}
