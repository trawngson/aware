import SwiftUI

struct EnvironmentalFactCard: View {
    struct Fact {
        let icon: String
        let iconColor: Color
        let value: String
        let unit: String
        let description: String
    }
    
    let facts: [Fact] = [
        Fact(icon: "tree.fill", iconColor: .green, value: "3", unit: "trees", description: "equivalent saved"),
        Fact(icon: "drop.fill", iconColor: .blue, value: "850", unit: "L", description: "water conserved"),
        Fact(icon: "bolt.fill", iconColor: .yellow, value: "42", unit: "kWh", description: "energy saved")
    ]
    
    @State private var currentIndex: Int = 0
    let timer = Timer.publish(every: 4, on: .main, in: .common).autoconnect()
    
    var body: some View {
        DashboardCard {
            VStack(alignment: .leading, spacing: 12) {
                CardHeader(
                    icon: "globe.americas.fill",
                    title: "Your Impact",
                    iconColor: .mint,
                    subtitle: "All Time",
                    showChevron: false
                )
                
                Spacer(minLength: 0)
                
                // Animated fact display
                let fact = facts[currentIndex]
                
                HStack(spacing: 16) {
                    ZStack {
                        Circle()
                            .fill(fact.iconColor.opacity(0.15))
                            .frame(width: 60, height: 60)
                        Image(systemName: fact.icon)
                            .font(.system(size: 28))
                            .foregroundStyle(fact.iconColor)
                    }
                    
                    VStack(alignment: .leading, spacing: 4) {
                        HStack(alignment: .firstTextBaseline, spacing: 4) {
                            Text(fact.value)
                                .font(.system(size: 36, weight: .bold, design: .rounded))
                            Text(fact.unit)
                                .font(.title3.weight(.medium))
                                .foregroundStyle(.secondary)
                        }
                        Text(fact.description)
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    
                    Spacer()
                }
                .animation(.easeInOut(duration: 0.5), value: currentIndex)
                
                // Page indicators
                HStack(spacing: 6) {
                    ForEach(0..<facts.count, id: \.self) { index in
                        Circle()
                            .fill(index == currentIndex ? fact.iconColor : Color.gray.opacity(0.3))
                            .frame(width: 6, height: 6)
                            .animation(.easeInOut, value: currentIndex)
                    }
                    Spacer()
                }
            }
        }
        .onReceive(timer) { _ in
            withAnimation {
                currentIndex = (currentIndex + 1) % facts.count
            }
        }
    }
}

#Preview {
    EnvironmentalFactCard()
        .padding()
}
