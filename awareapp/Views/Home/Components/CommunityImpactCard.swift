import SwiftUI

struct CommunityImpactCard: View {
    let totalUsers: Int = 1247
    let totalWasteSaved: String = "2.4 tons"
    let userRank: Int = 3
    
    var body: some View {
        DashboardCard {
            VStack(alignment: .leading, spacing: 12) {
                CardHeader(
                    icon: "person.3.fill",
                    title: "Community Impact",
                    iconColor: Color.indigo,
                    subtitle: "Global"
                )
                
                Spacer(minLength: 0)
                
                HStack(spacing: 16) {
                    // Total community impact
                    VStack(alignment: .leading, spacing: 4) {
                        Text(totalWasteSaved)
                            .font(.system(size: 28, weight: .bold, design: .rounded))
                        Text("saved together")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    
                    Spacer()
                    
                    // User rank
                    VStack(alignment: .center, spacing: 4) {
                        ZStack {
                            Circle()
                                .fill(LinearGradient(
                                    colors: [.indigo, .purple],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                ))
                                .frame(width: 50, height: 50)
                            
                            Text("#\(userRank)")
                                .font(.system(size: 14, weight: .bold, design: .rounded))
                                .foregroundStyle(.white)
                        }
                        Text("Your Rank")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
                
                // Active users indicator
                HStack(spacing: 8) {
                    // Overlapping avatars
                    HStack(spacing: -8) {
                        ForEach(0..<4, id: \.self) { i in
                            Circle()
                                .fill([Color.blue, .green, .orange, .pink][i].opacity(0.8))
                                .frame(width: 24, height: 24)
                                .overlay(
                                    Circle()
                                        .stroke(Color(uiColor: .systemBackground), lineWidth: 2)
                                )
                        }
                        Circle()
                            .fill(Color.gray.opacity(0.3))
                            .frame(width: 24, height: 24)
                            .overlay(
                                Text("+")
                                    .font(.caption2.weight(.bold))
                                    .foregroundStyle(.secondary)
                            )
                            .overlay(
                                Circle()
                                    .stroke(Color(uiColor: .systemBackground), lineWidth: 2)
                            )
                    }
                    
                    Text("\(totalUsers) active recyclers")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    
                    Spacer()
                }
            }
        }
    }
}

#Preview {
    CommunityImpactCard()
        .padding()
}
