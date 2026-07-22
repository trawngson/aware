import SwiftUI

struct ItemsScannedCard: View {
    let totalItems: Int = 47
    let weeklyChange: Int = 12
    
    // Category breakdown
    let categories: [(name: String, count: Int, color: Color, icon: String)] = [
        ("Plastic", 18, .blue, "waterbottle.fill"),
        ("Paper", 14, .brown, "newspaper.fill"),
        ("Metal", 9, .gray, "cylinder.fill"),
        ("Glass", 6, .green, "wineglass.fill")
    ]
    
    var body: some View {
        DashboardCard {
            VStack(alignment: .leading, spacing: 12) {
                CardHeader(
                    icon: "qrcode.viewfinder",
                    title: "Items Scanned",
                    iconColor: .purple,
                    subtitle: "This Month"
                )
                
                Spacer(minLength: 0)
                
                HStack(alignment: .bottom) {
                    Text("\(totalItems)")
                        .font(.system(size: 42, weight: .bold, design: .rounded))
                    Text("items")
                        .font(.title3)
                        .foregroundStyle(.secondary)
                        .padding(.bottom, 6)
                    
                    Spacer()
                    
                    TrendIndicator(value: "+\(weeklyChange) this week", isPositive: true)
                        .padding(.bottom, 8)
                }
                
                // Category breakdown bar
                GeometryReader { geometry in
                    HStack(spacing: 2) {
                        ForEach(categories, id: \.name) { category in
                            let width = CGFloat(category.count) / CGFloat(totalItems) * geometry.size.width
                            RoundedRectangle(cornerRadius: 4)
                                .fill(category.color)
                                .frame(width: max(width - 2, 8), height: 8)
                        }
                    }
                }
                .frame(height: 8)
                
                // Legend
                HStack(spacing: 12) {
                    ForEach(categories, id: \.name) { category in
                        HStack(spacing: 4) {
                            Circle()
                                .fill(category.color)
                                .frame(width: 8, height: 8)
                            Text("\(category.count)")
                                .font(.caption.weight(.medium))
                                .foregroundStyle(.secondary)
                        }
                    }
                    Spacer()
                }
            }
        }
    }
}

#Preview {
    ItemsScannedCard()
        .padding()
}
