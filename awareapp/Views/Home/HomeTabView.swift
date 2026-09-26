import SwiftUI

struct HomeTabView: View {
    @ObservedObject private var ledger = RewardLedger.shared
    @ObservedObject private var navigationManager = NavigationManager.shared
    @GestureState private var isTouchingGlassHeader = false

    var body: some View {
        NavigationStack {
            TabScrollView {
                VStack(spacing: 14) {
                    if #available(iOS 26, *) {
                        // Liquid Glass systems: the system glass button swells and stretches toward
                        // the finger. It adds its own 12 × 7 pt inset, so the header pads less here.
                        NavigationLink(destination: UserOptionsView()) {
                            welcomeHeader(horizontalPadding: 2, verticalPadding: 5)
                        }
                        .buttonStyle(.glass)
                        .buttonBorderShape(.roundedRectangle(radius: 26))
                        // A drag that starts on the glass stretches it instead of scrolling the page.
                        .simultaneousGesture(DragGesture(minimumDistance: 0)
                            .updating($isTouchingGlassHeader) { _, touching, _ in touching = true })
                    } else {
                        // Before Liquid Glass: a plain translucent bar, no stretching.
                        NavigationLink(destination: UserOptionsView()) {
                            welcomeHeader(horizontalPadding: 14, verticalPadding: 12)
                                .glass(.frosted, cornerRadius: 26)
                        }
                        .buttonStyle(PressableStyle())
                    }

                    HStack(spacing: 10) {
                        NavigationLink(destination: WasteInsightsView()) {
                            SavedStatCard(systemImage: "trash.fill", title: "Waste Saved", tint: Theme.green,
                                          value: 6_700, unit: "g", trendUp: true, trend: "12% today")
                        }
                        NavigationLink(destination: CO2InsightsView()) {
                            SavedStatCard(systemImage: "cloud.fill", title: "CO₂ Saved", tint: Theme.teal,
                                          value: 1_250, unit: "kg", trendUp: false, trend: "9% today")
                        }
                    }
                    .buttonStyle(PressableStyle())

                    MonthlyGoalCard()

                    NavigationLink(destination: RecyclingMapView()) {
                        RecyclingMapCard()
                    }
                    .buttonStyle(PressableStyle())

                    NavigationLink(destination: LeaderboardView()) {
                        LeaderboardPreviewCard()
                    }
                    .buttonStyle(PressableStyle())

                    WeeklyStreakCard()

                    NavigationLink(destination: WasteInsightsView()) {
                        ItemsScannedCard()
                    }
                    .buttonStyle(PressableStyle())

                    RecentActivityCard()

                    CommunityImpactCard()

                    NavigationLink(destination: WasteInsightsView()) {
                        WeeklyComparisonCard()
                    }
                    .buttonStyle(PressableStyle())
                }
                .padding(.horizontal, 16)
                .padding(.top, 12)
                .padding(.bottom, 24)
            }
            .scrollIndicators(.hidden)
            .scrollDisabled(isTouchingGlassHeader)
            .overlay(alignment: .top) {
                // Keeps the status bar readable when light cards scroll under it.
                LinearGradient(colors: [Theme.forestShade.opacity(0.55), Theme.forestShade.opacity(0)],
                               startPoint: .top, endPoint: .bottom)
                    .frame(height: 12)
                    .ignoresSafeArea(edges: .top)
                    .allowsHitTesting(false)
            }
            .background { ForestBackdrop() }
            .toolbar(.hidden, for: .navigationBar)
        }
        .tint(navigationManager.chromeTint)
    }

    private func welcomeHeader(horizontalPadding: CGFloat, verticalPadding: CGFloat) -> some View {
        HStack(spacing: 13) {
            MemberAvatar(member: Community.me, size: 58, borderColor: .white.opacity(0.7), borderWidth: 1.5)
            VStack(alignment: .leading, spacing: 3) {
                Text("Welcome back")
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(.white.opacity(0.85))
                Text(Community.me.shortName)
                    .font(.system(size: 26, weight: .bold))
                    .tracking(-0.8)
                    .foregroundStyle(.white)
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
            }
            Spacer(minLength: 0)
            LeafAmount(value: Community.me.points + ledger.totalPoints, size: 15, weight: .semibold,
                       color: .white, leafColor: Theme.mint)
                .padding(.horizontal, 10)
                .padding(.vertical, 5)
                .background(Capsule().fill(.white.opacity(0.2)))
                .overlay(Capsule().strokeBorder(.white.opacity(0.3), lineWidth: 0.5))
                .contentTransition(.numericText())
        }
        .padding(.horizontal, horizontalPadding)
        .padding(.vertical, verticalPadding)
        .accessibilityElement(children: .combine)
        .accessibilityHint("Opens More")
    }
}

#Preview {
    ContentView()
}
