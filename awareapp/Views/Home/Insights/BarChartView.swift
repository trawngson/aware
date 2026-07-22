import SwiftUI

// MARK: - Animated Bar Chart

struct BarChartView: View {
    let data: [DataPoint]
    let accentColor: Color
    
    @State private var animationProgress: CGFloat = 0
    
    init(data: [DataPoint], accentColor: Color = .green) {
        self.data = data
        self.accentColor = accentColor
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            GeometryReader { geometry in
                let maxValue = data.map(\.value).max() ?? 1
                let barWidth = (geometry.size.width - CGFloat(data.count - 1) * 8) / CGFloat(data.count)
                
                HStack(alignment: .bottom, spacing: 8) {
                    ForEach(Array(data.enumerated()), id: \.offset) { index, point in
                        let normalizedHeight = (point.value / maxValue) * geometry.size.height * 0.9
                        
                        VStack {
                            Spacer()
                            RoundedRectangle(cornerRadius: 6)
                                .fill(
                                    LinearGradient(
                                        colors: [accentColor, accentColor.opacity(0.7)],
                                        startPoint: .top,
                                        endPoint: .bottom
                                    )
                                )
                                .frame(width: barWidth, height: normalizedHeight * animationProgress)
                                .animation(
                                    .easeInOut(duration: 0.6).delay(Double(index) * 0.06),
                                    value: animationProgress
                                )
                        }
                    }
                }
            }
            .frame(height: 160)
            
            // X-axis labels
            HStack(spacing: 8) {
                ForEach(data) { point in
                    Text(point.label)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity)
                }
            }
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 0.8)) {
                animationProgress = 1
            }
        }
    }
}

// MARK: - Preview

#Preview {
    BarChartView(data: SampleData.wasteWeekly, accentColor: .blue)
        .padding()
}
