import SwiftUI

struct WeeklyStreakCard: View {
    let currentStreak: Int = 12
    let longestStreak: Int = 18
    let weekData: [Bool] = [true, true, true, false, true, true, true] // M-T-W-T-F-S-S
    
    var body: some View {
        DashboardCard {
            VStack(alignment: .leading, spacing: 12) {
                CardHeader(
                    icon: "flame.fill",
                    title: "Recycling Streak",
                    iconColor: .orange,
                    subtitle: "This Week"
                )
                
                Spacer(minLength: 0)
                
                HStack(alignment: .bottom, spacing: 4) {
                    Text("\(currentStreak)")
                        .font(.system(size: 42, weight: .bold, design: .rounded))
                    Text("days")
                        .font(.title3)
                        .foregroundStyle(.secondary)
                        .padding(.bottom, 6)
                }
                
                // Week visualization
                HStack(spacing: 8) {
                    ForEach(Array(zip(["M", "T", "W", "T", "F", "S", "S"], weekData)), id: \.0) { day, completed in
                        VStack(spacing: 4) {
                            Circle()
                                .fill(completed ? Color.orange : Color.gray.opacity(0.3))
                                .frame(width: 24, height: 24)
                                .overlay {
                                    if completed {
                                        Image(systemName: "checkmark")
                                            .font(.system(size: 12, weight: .bold))
                                            .foregroundStyle(.white)
                                    }
                                }
                            Text(day)
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                    }
                    
                    Spacer()
                    
                    VStack(alignment: .trailing) {
                        Text("Best")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text("\(longestStreak) days")
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(.orange)
                    }
                }
            }
        }
    }
}

#Preview {
    WeeklyStreakCard()
        .padding()
}
