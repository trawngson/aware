import SwiftUI

// MARK: - Animated Line Chart

struct LineChartView: View {
    let data: [DataPoint]
    let accentColor: Color
    let showArea: Bool
    
    @State private var animationProgress: CGFloat = 0
    
    init(data: [DataPoint], accentColor: Color = .green, showArea: Bool = true) {
        self.data = data
        self.accentColor = accentColor
        self.showArea = showArea
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            GeometryReader { geometry in
                let maxValue = data.map(\.value).max() ?? 1
                let minValue = data.map(\.value).min() ?? 0
                let range = max(maxValue - minValue, 1)
                let stepX = geometry.size.width / CGFloat(max(data.count - 1, 1))
                
                ZStack {
                    // Grid lines
                    ForEach(0..<4) { i in
                        Path { path in
                            let y = geometry.size.height * CGFloat(i) / 3
                            path.move(to: CGPoint(x: 0, y: y))
                            path.addLine(to: CGPoint(x: geometry.size.width, y: y))
                        }
                        .stroke(Color.gray.opacity(0.2), style: StrokeStyle(lineWidth: 1, dash: [5]))
                    }
                    
                    // Area fill
                    if showArea {
                        Path { path in
                            path.move(to: CGPoint(x: 0, y: geometry.size.height))
                            for (index, point) in data.enumerated() {
                                let x = stepX * CGFloat(index)
                                let normalizedY = (point.value - minValue) / range
                                let y = geometry.size.height - (normalizedY * geometry.size.height * 0.85)
                                if index == 0 {
                                    path.addLine(to: CGPoint(x: x, y: y))
                                } else {
                                    path.addLine(to: CGPoint(x: x, y: y))
                                }
                            }
                            path.addLine(to: CGPoint(x: geometry.size.width, y: geometry.size.height))
                            path.closeSubpath()
                        }
                        .fill(
                            LinearGradient(
                                colors: [accentColor.opacity(0.3), accentColor.opacity(0.05)],
                                startPoint: .top,
                                endPoint: .bottom
                            )
                        )
                        .mask(
                            Rectangle()
                                .scale(x: animationProgress, y: 1, anchor: .leading)
                        )
                    }
                    
                    // Line
                    Path { path in
                        for (index, point) in data.enumerated() {
                            let x = stepX * CGFloat(index)
                            let normalizedY = (point.value - minValue) / range
                            let y = geometry.size.height - (normalizedY * geometry.size.height * 0.85)
                            if index == 0 {
                                path.move(to: CGPoint(x: x, y: y))
                            } else {
                                path.addLine(to: CGPoint(x: x, y: y))
                            }
                        }
                    }
                    .trim(from: 0, to: animationProgress)
                    .stroke(
                        accentColor,
                        style: StrokeStyle(lineWidth: 3, lineCap: .round, lineJoin: .round)
                    )
                }
            }
            .frame(height: 180)
            
            // X-axis labels
            HStack {
                ForEach(data) { point in
                    Text(point.label)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity)
                }
            }
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 1.0)) {
                animationProgress = 1
            }
        }
    }
}

// MARK: - Preview

#Preview {
    LineChartView(data: SampleData.wasteWeekly, accentColor: .green)
        .padding()
}
