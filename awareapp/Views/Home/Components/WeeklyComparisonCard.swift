import SwiftUI

struct WeeklyComparisonCard: View {
    // Sample data: (day, thisWeek, lastWeek)
    let weekData: [(day: String, current: CGFloat, previous: CGFloat)] = [
        ("M", 45, 30),
        ("T", 60, 45),
        ("W", 35, 55),
        ("T", 80, 40),
        ("F", 55, 65),
        ("S", 70, 50),
        ("S", 40, 35)
    ]
    
    let maxValue: CGFloat = 100
    
    var body: some View {
        DashboardCard {
            VStack(alignment: .leading, spacing: 12) {
                CardHeader(
                    icon: "chart.bar.fill",
                    title: "Weekly Comparison",
                    iconColor: .pink,
                    subtitle: nil,
                    showChevron: true
                )
                
                Spacer(minLength: 0)
                
                // Legend
                HStack(spacing: 16) {
                    HStack(spacing: 4) {
                        RoundedRectangle(cornerRadius: 2)
                            .fill(Color.pink)
                            .frame(width: 12, height: 12)
                        Text("This Week")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    HStack(spacing: 4) {
                        RoundedRectangle(cornerRadius: 2)
                            .fill(Color.gray.opacity(0.4))
                            .frame(width: 12, height: 12)
                        Text("Last Week")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                }
                
                // Chart
                HStack(alignment: .bottom, spacing: 8) {
                    ForEach(weekData, id: \.day) { data in
                        VStack(spacing: 4) {
                            // Bars
                            HStack(alignment: .bottom, spacing: 2) {
                                // Last week (background)
                                RoundedRectangle(cornerRadius: 3)
                                    .fill(Color.gray.opacity(0.3))
                                    .frame(width: 12, height: max(data.previous / maxValue * 50, 4))
                                
                                // This week (foreground)
                                RoundedRectangle(cornerRadius: 3)
                                    .fill(
                                        LinearGradient(
                                            colors: [.pink, .pink.opacity(0.7)],
                                            startPoint: .top,
                                            endPoint: .bottom
                                        )
                                    )
                                    .frame(width: 12, height: max(data.current / maxValue * 50, 4))
                            }
                            
                            // Day label
                            Text(data.day)
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
                .frame(maxWidth: .infinity)
            }
        }
    }
}

#Preview {
    WeeklyComparisonCard()
        .padding()
}
