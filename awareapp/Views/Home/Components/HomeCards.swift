import SwiftUI

// Home dashboard cards. All figures are demo values, except the current
// user's points, which include rewards earned from scans this session.

// MARK: - Waste / CO₂ saved

struct SavedStatCard: View {
    let systemImage: String
    let title: LocalizedStringKey
    let tint: Color
    let value: Int
    let unit: String
    let trendUp: Bool
    let trend: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: systemImage).font(.system(size: 14))
                Text(title).font(.system(size: 13, weight: .semibold)).tracking(-0.13)
            }
            .foregroundStyle(tint)
            HStack(alignment: .firstTextBaseline, spacing: 1) {
                Text(AwareFormat.grouped(value)).displayNumber(27)
                Text(unit).font(.system(size: 16, weight: .semibold)).foregroundStyle(Theme.ink.opacity(0.55))
            }
            TrendPill(systemImage: trendUp ? "arrow.up" : "arrow.down", text: trend, tint: tint)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .glass(.card, cornerRadius: 22)
    }
}

// MARK: - Monthly goal

struct MonthlyGoalCard: View {
    private let progress = 0.7
    private let pointsToGo = 2_000

    private var monthName: String {
        Date.now.formatted(.dateTime.month(.wide))
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            CardHeader(systemImage: "flag.fill", title: "\(monthName) Goal",
                       caption: "\(Int(progress * 100))%", showsChevron: false)
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                HStack(spacing: 4) {
                    Text(AwareFormat.grouped(pointsToGo)).displayNumber(30)
                    Image(systemName: "leaf.fill").font(.system(size: 22)).foregroundStyle(Theme.green)
                }
                Text("to go").font(.system(size: 17)).foregroundStyle(Theme.ink.opacity(0.55))
            }
            GoalProgressBar(progress: progress)
        }
        .padding(16)
        .glass(.card)
    }
}

struct GoalProgressBar: View {
    let progress: Double

    var body: some View {
        GeometryReader { proxy in
            ZStack(alignment: .leading) {
                Capsule().fill(Theme.ink.opacity(0.09))
                Capsule()
                    .fill(Theme.progressGradient)
                    .overlay(Capsule().strokeBorder(LinearGradient(colors: [.white.opacity(0.45), .clear],
                                                                   startPoint: .top, endPoint: .center), lineWidth: 1))
                    .frame(width: proxy.size.width * progress)
            }
        }
        .frame(height: 10)
        .accessibilityElement()
        .accessibilityLabel("Goal progress")
        .accessibilityValue(Text(progress, format: .percent))
    }
}

// MARK: - Recycling map

struct RecyclingMapCard: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            CardHeader(systemImage: "mappin", title: "Recycling Map", caption: "Near you")
            MiniRecyclingMap()
                .frame(height: 138)
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            HStack(spacing: 10) {
                HStack(spacing: -7) {
                    ForEach([Theme.greenMid, Theme.teal, Theme.amber], id: \.self) { color in
                        Circle().fill(color).frame(width: 22, height: 22)
                            .overlay(Circle().strokeBorder(.white, lineWidth: 1.5))
                    }
                }
                Text("\(RecyclingMapData.nearbyCount(for: nil)) items recycled within 2 km")
                    .font(.system(size: 13))
                    .foregroundStyle(Theme.ink.opacity(0.62))
            }
        }
        .padding(16)
        .glass(.card)
    }
}

// MARK: - Leaderboard

struct LeaderboardPreviewCard: View {
    @ObservedObject private var ledger = RewardLedger.shared

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            CardHeader(systemImage: "chart.bar.fill", title: "Recycle Leaderboard", caption: "This Month")
            VStack(spacing: 8) {
                ForEach(Array(Community.ranking.prefix(3).enumerated()), id: \.element.member.id) { index, entry in
                    row(rank: index + 1, member: entry.member, points: entry.points)
                }
            }
        }
        .padding(16)
        .glass(.card)
    }

    private func row(rank: Int, member: CommunityMember, points: Int) -> some View {
        let isMe = member.id == Community.me.id
        return HStack(spacing: 10) {
            Text("\(rank)")
                .font(.system(size: 12, weight: .bold))
                .foregroundStyle(isMe ? .white : Theme.green)
                .frame(width: 22, height: 22)
                .background(RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(isMe ? Theme.green : Theme.green.opacity(0.16)))
            Text(member.shortName)
                .font(.system(size: 15, weight: isMe ? .semibold : .medium))
                .foregroundStyle(Theme.ink)
            if isMe {
                Text("You")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(Theme.green)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Capsule().fill(Theme.green.opacity(0.14)))
            }
            Spacer(minLength: 0)
            LeafAmount(value: points)
        }
        .padding(.horizontal, isMe ? 8 : 0)
        .padding(.vertical, isMe ? 6 : 0)
        .background {
            if isMe {
                RoundedRectangle(cornerRadius: 14, style: .continuous).fill(Theme.green.opacity(0.08))
            }
        }
        .padding(.horizontal, isMe ? -8 : 0)
    }
}

// MARK: - Streak

struct WeeklyStreakCard: View {
    private let days: [(label: LocalizedStringKey, done: Bool)] = [
        ("M", true), ("T", true), ("W", true), ("T", false), ("F", true), ("S", true), ("S", true),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            CardHeader(systemImage: "flame.fill", title: "Recycling Streak", tint: Theme.amber,
                       caption: "This Week", showsChevron: false)
            HStack(alignment: .bottom, spacing: 6) {
                Text("3").displayNumber(40)
                Text("days").font(.system(size: 17)).foregroundStyle(Theme.ink.opacity(0.55)).padding(.bottom, 4)
                Spacer(minLength: 0)
                VStack(alignment: .trailing, spacing: 1) {
                    Text("Best").font(.system(size: 11)).foregroundStyle(Theme.ink.opacity(0.5))
                    Text("18 days").font(.system(size: 14, weight: .semibold)).foregroundStyle(Theme.amber)
                }
                .padding(.bottom, 2)
            }
            HStack(spacing: 7) {
                ForEach(Array(days.enumerated()), id: \.offset) { _, day in
                    VStack(spacing: 5) {
                        RoundedRectangle(cornerRadius: 11, style: .continuous)
                            .fill(day.done ? AnyShapeStyle(Theme.primaryGradient) : AnyShapeStyle(Theme.ink.opacity(0.09)))
                            .frame(height: 30)
                        Text(day.label).font(.system(size: 11)).foregroundStyle(Theme.ink.opacity(0.5))
                    }
                }
            }
        }
        .padding(16)
        .glass(.card)
    }
}

// MARK: - Items scanned

struct ItemsScannedCard: View {
    private let categories: [(name: LocalizedStringKey, count: Int, color: Color)] = [
        ("Plastic", 18, Theme.green),
        ("Paper", 14, Color(hex: 0x4FA878)),
        ("Metal", 9, Color(hex: 0x8FBFA4)),
        ("Glass", 6, Color(hex: 0xC3DBCC)),
    ]

    private var total: Int { categories.map(\.count).reduce(0, +) }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            CardHeader(systemImage: "qrcode.viewfinder", title: "Items Scanned", caption: "This Month")
            HStack(alignment: .bottom, spacing: 6) {
                Text("\(total)").displayNumber(40)
                Text("items").font(.system(size: 17)).foregroundStyle(Theme.ink.opacity(0.55)).padding(.bottom, 4)
                Spacer(minLength: 0)
                TrendPill(systemImage: "arrow.up", text: "+12 this week")
            }
            GeometryReader { proxy in
                HStack(spacing: 3) {
                    ForEach(Array(categories.enumerated()), id: \.offset) { _, category in
                        Capsule().fill(category.color)
                            .frame(width: max(0, (proxy.size.width - 9) * Double(category.count) / Double(total)))
                    }
                }
            }
            .frame(height: 10)
            HStack(spacing: 14) {
                ForEach(Array(categories.enumerated()), id: \.offset) { _, category in
                    HStack(spacing: 5) {
                        RoundedRectangle(cornerRadius: 3).fill(category.color).frame(width: 8, height: 8)
                        Text(category.name) + Text(" \(category.count)")
                    }
                    .font(.system(size: 12))
                    .foregroundStyle(Theme.ink.opacity(0.6))
                }
            }
        }
        .padding(16)
        .glass(.card)
    }
}

// MARK: - Recent activity

struct RecentActivityCard: View {
    private struct Activity: Identifiable {
        let id = UUID()
        let icon: String
        let tint: Color
        let title: LocalizedStringKey
        let detail: LocalizedStringKey
        let points: Int
    }

    // Points follow the reward policy: 20 for a sorted recyclable.
    private let activities = [
        Activity(icon: "waterbottle.fill", tint: Theme.green, title: "Plastic Bottle", detail: "Recycled · 2m ago", points: RecyclingPolicy.recyclablePoints),
        Activity(icon: "shippingbox.fill", tint: Theme.amber, title: "Cardboard Box", detail: "Recycled · 1h ago", points: RecyclingPolicy.recyclablePoints),
        Activity(icon: "trophy.fill", tint: Theme.teal, title: "Weekly Goal", detail: "Achieved · 3h ago", points: 100),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            CardHeader(systemImage: "clock.arrow.circlepath", title: "Recent Activity", caption: "Today", showsChevron: false)
            VStack(spacing: 12) {
                ForEach(activities) { activity in
                    HStack(spacing: 12) {
                        IconTile(systemImage: activity.icon, tint: activity.tint, size: 38, cornerRadius: 13, iconSize: 17)
                        VStack(alignment: .leading, spacing: 1) {
                            Text(activity.title).cardTitleStyle()
                            Text(activity.detail).font(.system(size: 12)).foregroundStyle(Theme.ink.opacity(0.55))
                        }
                        Spacer(minLength: 0)
                        HStack(spacing: 2) {
                            Text("+\(activity.points)")
                            Image(systemName: "leaf.fill").font(.system(size: 11))
                        }
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(Theme.green)
                    }
                }
            }
        }
        .padding(16)
        .glass(.card)
    }
}

// MARK: - Your impact

struct CommunityImpactCard: View {
    @ObservedObject private var ledger = RewardLedger.shared

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            CardHeader(systemImage: "globe.asia.australia.fill", title: "Your Impact", tint: Theme.mint,
                       caption: "All Time", showsChevron: false, titleColor: .white,
                       captionColor: .white.opacity(0.7), tileBackground: .white.opacity(0.18))
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text("3").displayNumber(46, color: .white)
                Text("trees saved").font(.system(size: 19, weight: .medium)).foregroundStyle(.white.opacity(0.8))
            }
            HStack(spacing: 10) {
                HStack(spacing: -8) {
                    ForEach([Theme.greenMid, Theme.teal, Theme.amber, Color(hex: 0x5C7360)], id: \.self) { color in
                        Circle().fill(color).frame(width: 24, height: 24)
                            .overlay(Circle().strokeBorder(.white.opacity(0.85), lineWidth: 1.5))
                    }
                }
                Text("\(AwareFormat.grouped(1_247)) recyclers · \(2.4.formatted()) tons together")
                    .font(.system(size: 13))
                    .foregroundStyle(.white.opacity(0.88))
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
                Spacer(minLength: 0)
                Text("#\(Community.myRank)")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 9)
                    .padding(.vertical, 3)
                    .background(Capsule().fill(.white.opacity(0.2)))
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(RoundedRectangle(cornerRadius: 16, style: .continuous).fill(.white.opacity(0.14)))
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(.white.opacity(0.22), lineWidth: 0.5))
        }
        .padding(16)
        .background {
            ZStack {
                Image("ForestBackground").resizable().scaledToFill()
                LinearGradient(colors: [Color(hex: 0x091C11, opacity: 0.55), Color(hex: 0x091C11, opacity: 0.78)],
                               startPoint: .top, endPoint: .bottom)
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        .shadow(color: Color(hex: 0x0C2616, opacity: 0.28), radius: 16, y: 14)
    }
}

// MARK: - Weekly comparison

struct WeeklyComparisonCard: View {
    private let days: [(label: LocalizedStringKey, last: CGFloat, this: CGFloat)] = [
        ("M", 18, 26), ("T", 26, 34), ("W", 32, 20), ("T", 23, 46), ("F", 37, 31), ("S", 29, 40), ("S", 20, 23),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            CardHeader(systemImage: "chart.bar.xaxis", title: "Weekly Comparison")
            HStack(spacing: 16) {
                legend(Theme.green, "This week")
                legend(Theme.ink.opacity(0.15), "Last week")
            }
            HStack(alignment: .bottom) {
                ForEach(Array(days.enumerated()), id: \.offset) { index, day in
                    if index > 0 { Spacer(minLength: 0) }
                    VStack(spacing: 6) {
                        HStack(alignment: .bottom, spacing: 3) {
                            RoundedRectangle(cornerRadius: 4).fill(Theme.ink.opacity(0.13)).frame(width: 9, height: day.last)
                            RoundedRectangle(cornerRadius: 4).fill(Theme.primaryGradient).frame(width: 9, height: day.this)
                        }
                        .frame(height: 48, alignment: .bottom)
                        Text(day.label).font(.system(size: 11)).foregroundStyle(Theme.ink.opacity(0.5))
                    }
                }
            }
            .accessibilityElement()
            .accessibilityLabel("Scans per day, this week compared with last week")
        }
        .padding(16)
        .glass(.card)
    }

    private func legend(_ color: Color, _ title: LocalizedStringKey) -> some View {
        HStack(spacing: 5) {
            RoundedRectangle(cornerRadius: 3).fill(color).frame(width: 10, height: 10)
            Text(title).font(.system(size: 12)).foregroundStyle(Theme.ink.opacity(0.6))
        }
    }
}

#Preview {
    ScrollView {
        VStack(spacing: 14) {
            MonthlyGoalCard()
            LeaderboardPreviewCard()
            WeeklyStreakCard()
            ItemsScannedCard()
            RecentActivityCard()
            CommunityImpactCard()
            WeeklyComparisonCard()
        }
        .padding()
    }
    .background(Theme.page)
}
