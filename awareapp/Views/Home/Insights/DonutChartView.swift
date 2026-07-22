import SwiftUI

// MARK: - Donut Chart

struct DonutChartView: View {
    let data: [DataPoint]
    let colors: [Color]
    
    @State private var animationProgress: CGFloat = 0
    @State private var selectedIndex: Int? = nil
    
    init(data: [DataPoint], colors: [Color] = [.green, .blue, .orange, .purple, .pink]) {
        self.data = data
        self.colors = colors
    }
    
    var body: some View {
        let total = data.map(\.value).reduce(0, +)
        
        HStack(spacing: 24) {
            // Donut
            ZStack {
                ForEach(Array(data.enumerated()), id: \.offset) { index, point in
                    let startAngle = startAngle(for: index, total: total)
                    let endAngle = endAngle(for: index, total: total)
                    
                    DonutSlice(
                        startAngle: startAngle,
                        endAngle: Angle(degrees: startAngle.degrees + (endAngle.degrees - startAngle.degrees) * animationProgress),
                        thickness: selectedIndex == index ? 28 : 24
                    )
                    .fill(colors[index % colors.count])
                    .onTapGesture {
                        withAnimation(.spring(response: 0.3, dampingFraction: 0.7)) {
                            selectedIndex = selectedIndex == index ? nil : index
                        }
                    }
                }
                
                // Center label
                VStack(spacing: 2) {
                    if let index = selectedIndex {
                        Text(data[index].label)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text("\(Int(data[index].value))%")
                            .font(.title2.weight(.bold))
                    } else {
                        Text("Total")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text("100%")
                            .font(.title2.weight(.bold))
                    }
                }
            }
            .frame(width: 140, height: 140)
            
            // Legend
            VStack(alignment: .leading, spacing: 10) {
                ForEach(Array(data.enumerated()), id: \.offset) { index, point in
                    HStack(spacing: 8) {
                        Circle()
                            .fill(colors[index % colors.count])
                            .frame(width: 10, height: 10)
                        Text(point.label)
                            .font(.subheadline)
                        Spacer()
                        Text("\(Int(point.value))%")
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(.secondary)
                    }
                    .opacity(selectedIndex == nil || selectedIndex == index ? 1 : 0.4)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .onAppear {
            withAnimation(.easeOut(duration: 1.0)) {
                animationProgress = 1
            }
        }
    }
    
    private func startAngle(for index: Int, total: Double) -> Angle {
        let sum = data.prefix(index).map(\.value).reduce(0, +)
        return Angle(degrees: (sum / total) * 360 - 90)
    }
    
    private func endAngle(for index: Int, total: Double) -> Angle {
        let sum = data.prefix(index + 1).map(\.value).reduce(0, +)
        return Angle(degrees: (sum / total) * 360 - 90)
    }
}

// MARK: - Donut Slice Shape

struct DonutSlice: Shape {
    var startAngle: Angle
    var endAngle: Angle
    var thickness: CGFloat
    
    var animatableData: AnimatablePair<Double, Double> {
        get { AnimatablePair(startAngle.degrees, endAngle.degrees) }
        set {
            startAngle = Angle(degrees: newValue.first)
            endAngle = Angle(degrees: newValue.second)
        }
    }
    
    func path(in rect: CGRect) -> Path {
        let center = CGPoint(x: rect.midX, y: rect.midY)
        let radius = min(rect.width, rect.height) / 2
        let innerRadius = radius - thickness
        
        var path = Path()
        path.addArc(center: center, radius: radius, startAngle: startAngle, endAngle: endAngle, clockwise: false)
        path.addArc(center: center, radius: innerRadius, startAngle: endAngle, endAngle: startAngle, clockwise: true)
        path.closeSubpath()
        return path
    }
}

// MARK: - Preview

#Preview {
    DonutChartView(data: SampleData.wasteByCategory)
        .padding()
}
