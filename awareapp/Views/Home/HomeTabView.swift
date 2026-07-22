import SwiftUI

// thêm asset

struct HomeTabView: View {
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass

    var body: some View {
        NavigationStack {
            ZStack {
                backgroundView
                ScrollView {
                    VStack(alignment: .leading, spacing: 24) {
                        welcomeHeader
                        statsGrid
                        Divider().padding(.horizontal)
                    }
                    .padding()
                }
                .scrollContentBackground(.hidden)
            }
            .toolbarBackground(.hidden, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    private var welcomeHeader: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(
                spacing: 12
            ) {
                ZStack {
                    Circle()
                        .fill(Color.pink.opacity(0.25))
                        .frame(width: 80, height: 80)

                    Image("PlaceholderAvatar")
                        .resizable()
                        .scaledToFill()
                        .frame(width: 70, height: 70)
                        .clipShape(Circle())
                }
                VStack(alignment: .leading) {
                    Text("Welcome back")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.secondary)
                    HStack() {
                        Text("Truong Son")
                            .font(.largeTitle.weight(.bold))
                            .lineLimit(1)
                            .minimumScaleFactor(0.8)
                        HStack(spacing: 3) {
                            Text("1,400")
                                .foregroundStyle(.secondary)
                            Image(systemName: "leaf.fill").foregroundStyle(.secondary)
                        }
                        Image(systemName: "chevron.forward").imageScale(.large).foregroundStyle(.secondary)
                    }
                }
            };
        }
    }

    private var statsGrid: some View {
        LazyVGrid(
            columns: gridColumns,
            alignment: .leading,
            spacing: 12
        ) {
            NavigationLink(destination: WasteInsightsView()) {
                wasteCard
            }
            .buttonStyle(.plain)
            
            NavigationLink(destination: CO2InsightsView()) {
                co2Card
            }
            .buttonStyle(.plain)
            
            recyclingGoalCard
            
            NavigationLink(destination: LeaderboardView()) {
                recycleLeaderboardCard
            }
            .buttonStyle(.plain)
            
            // New cards
            WeeklyStreakCard()
            
            ItemsScannedCard()
            
            RecentActivityCard()
            
            CommunityImpactCard()
            
            EnvironmentalFactCard()
            
            WeeklyComparisonCard()
        }
    }

    private var wasteCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "trash.fill")
                    .foregroundStyle(.green)
                Text("Total Waste Saved")
                    .font(.headline)
                    .foregroundStyle(.green)
                Spacer()
                Text("Today").foregroundStyle(.secondary)
                Image(systemName: "chevron.right").foregroundStyle(.secondary)
            }
            Spacer(minLength: 0)
            HStack {
                Text("6,700g")
                    .font(.largeTitle)
                    .fontWeight(.semibold)
                HStack(spacing: 2) {
                    Image(systemName: "chevron.up.2")
                        .imageScale(.small)
                        .foregroundStyle(.secondary)
                    Text("12%")
                        .foregroundStyle(.secondary)
                }
                Spacer()
            }
        }
        .padding()
        .frame(maxWidth: .infinity, minHeight: 140, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(.thickMaterial)
        )
    }
    
    private var co2Card: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "carbon.monoxide.cloud.fill")
                    .foregroundStyle(.red)
                Text("CO₂ Saved")
                    .font(.headline)
                    .foregroundStyle(.red)
                Spacer()
                Text("Today").foregroundStyle(.secondary)
                Image(systemName: "chevron.right").foregroundStyle(.secondary)
            }
            Spacer(minLength: 0)
            HStack {
                Text("1,250kg")
                    .font(.largeTitle)
                    .fontWeight(.semibold)
                HStack(spacing: 2) {
                    Image(systemName: "chevron.down.2")
                        .imageScale(.small)
                        .foregroundStyle(.secondary)
                    Text("9%")
                        .foregroundStyle(.secondary)
                }
                Spacer()
            }
        }
        .padding()
        .frame(maxWidth: .infinity, minHeight: 140, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(.thickMaterial)
        )
    }

    private var recycleLeaderboardCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "arrow.up.circle.fill")
                    .foregroundStyle(.blue)
                Text("Recycle Leaderboard")
                    .font(.headline)
                    .foregroundStyle(.blue)
                Spacer()
                Text("This Month").foregroundStyle(.secondary)
                Image(systemName: "chevron.right").foregroundStyle(.secondary)
            }
            Spacer(minLength: 0)
            HStack {
                Text("1")
                    .fontWeight(.semibold)
                Text("Dieu Linh")
                    .foregroundStyle(.primary)
                Spacer()
                HStack(spacing: 3) {
                    Text("20,000")
                        .foregroundStyle(.secondary)
                    Image(systemName: "leaf.fill").foregroundStyle(.secondary)
                }
            }
            HStack {
                Text("2")
                    .fontWeight(.semibold)
                Text("Ha Chi")
                    .foregroundStyle(.primary)
                Spacer()
                HStack(spacing: 3) {
                    Text("15,000")
                        .foregroundStyle(.secondary)
                    Image(systemName: "leaf.fill").foregroundStyle(.secondary)
                }
            }
            HStack {
                Text("3")
                    .fontWeight(.semibold)
                Text("Truong Son")
                    .foregroundStyle(.primary)
                Spacer()
                HStack(spacing: 3) {
                    Text("1,400")
                        .foregroundStyle(.secondary)
                    Image(systemName: "leaf.fill").foregroundStyle(.secondary)
                }
            }
        }
        .padding()
        .frame(maxWidth: .infinity, minHeight: 140, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(.thickMaterial)
        )
    }
    
    private var recyclingGoalCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "flag.fill")
                    .foregroundStyle(.cyan)
                Text("Goal")
                    .font(.headline)
                    .foregroundStyle(.cyan)
                Spacer()
                Text("March").foregroundStyle(.secondary)
                Image(systemName: "chevron.right").foregroundStyle(.secondary)
            }
            Spacer(minLength: 0)
            HStack {
                HStack(spacing: 3) {
                    Text("2,000").font(.title).fontWeight(.semibold)
                    Image(systemName: "leaf.fill")
                }
                Text("to go").font(.title).foregroundStyle(.secondary)
                Spacer()
            }
            ProgressView(value: 0.7, )
        }
        .padding()
        .frame(maxWidth: .infinity, minHeight: 140, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(.thickMaterial)
        )
    }

    private var gridColumns: [GridItem] {
        let columnCount = horizontalSizeClass == .compact ? 1 : 2
        return Array(repeating: GridItem(.flexible(), spacing: 12, alignment: .leading), count: columnCount)
    }

    private var backgroundView: some View {
        ZStack(alignment: .top) {
            Color(uiColor: .systemGroupedBackground)
                .ignoresSafeArea()
            LinearGradient(
                stops: [
                    .init(color: Color.green.opacity(0.35), location: 0.0),
                    .init(color: Color.green.opacity(0.2), location: 0.15),
                    .init(color: Color.green.opacity(0.0), location: 0.3)
                ],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()
        }
    }
}

#Preview {
    ContentView()
}
