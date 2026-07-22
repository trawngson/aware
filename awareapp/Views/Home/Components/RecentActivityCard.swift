import SwiftUI

struct RecentActivityCard: View {
    struct Activity: Identifiable {
        let id = UUID()
        let icon: String
        let iconColor: Color
        let title: String
        let subtitle: String
        let time: String
        let points: Int
    }
    
    let activities: [Activity] = [
        Activity(icon: "waterbottle.fill", iconColor: .blue, title: "Plastic Bottle", subtitle: "Recycled", time: "2m ago", points: 15),
        Activity(icon: "newspaper.fill", iconColor: .brown, title: "Cardboard Box", subtitle: "Recycled", time: "1h ago", points: 25),
        Activity(icon: "trophy.fill", iconColor: .yellow, title: "Weekly Goal", subtitle: "Achieved", time: "3h ago", points: 100)
    ]
    
    var body: some View {
        DashboardCard {
            VStack(alignment: .leading, spacing: 12) {
                CardHeader(
                    icon: "clock.arrow.circlepath",
                    title: "Recent Activity",
                    iconColor: .teal,
                    subtitle: "Today"
                )
                
                Spacer(minLength: 0)
                
                VStack(spacing: 10) {
                    ForEach(activities) { activity in
                        HStack(spacing: 12) {
                            // Icon
                            ZStack {
                                RoundedRectangle(cornerRadius: 8, style: .continuous)
                                    .fill(activity.iconColor.opacity(0.15))
                                    .frame(width: 36, height: 36)
                                Image(systemName: activity.icon)
                                    .font(.system(size: 16))
                                    .foregroundStyle(activity.iconColor)
                            }
                            
                            // Title & subtitle
                            VStack(alignment: .leading, spacing: 2) {
                                Text(activity.title)
                                    .font(.subheadline.weight(.medium))
                                Text(activity.subtitle)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            
                            Spacer()
                            
                            // Points & time
                            VStack(alignment: .trailing, spacing: 2) {
                                HStack(spacing: 2) {
                                    Text("+\(activity.points)")
                                        .font(.subheadline.weight(.semibold))
                                        .foregroundStyle(.green)
                                    Image(systemName: "leaf.fill")
                                        .font(.caption)
                                        .foregroundStyle(.green)
                                }
                                Text(activity.time)
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            }
        }
    }
}

#Preview {
    RecentActivityCard()
        .padding()
}
