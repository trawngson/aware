import SwiftUI

// Home dashboard cards. Each card shows the user's own numbers (`stats`,
// from their scans) or, when `stats` is nil, the demo's sample numbers.

// MARK: - Waste / CO₂ saved

struct SavedStatCard: View {
    let systemImage: String
    let title: LocalizedStringKey
    let tint: Color
    let valueText: String
    let unit: String
    let trendIcon: String
    let trend: String

    init(systemImage: String, title: LocalizedStringKey, tint: Color, value: Int, unit: String,
         trendUp: Bool, trend: String) {
        self.init(systemImage: systemImage, title: title, tint: tint, valueText: AwareFormat.grouped(value),
                  unit: unit, trendIcon: trendUp ? "arrow.up" : "arrow.down", trend: trend)
    }

    init(systemImage: String, title: LocalizedStringKey, tint: Color, valueText: String, unit: String,
         trendIcon: String, trend: String) {
        self.systemImage = systemImage
        self.title = title
        self.tint = tint
        self.valueText = valueText
        self.unit = unit
        self.trendIcon = trendIcon
        self.trend = trend
    }

    /// The user's own total, with what they saved today as the trend.
    init(systemImage: String, title: LocalizedStringKey, tint: Color, grams: Double, todayGrams: Double) {
        let total = AwareFormat.mass(grams: grams)
        let today = AwareFormat.mass(grams: todayGrams)
        self.init(systemImage: systemImage, title: title, tint: tint, valueText: total.value, unit: total.unit,
                  trendIcon: todayGrams > 0 ? "arrow.up" : "minus",
                  trend: String(localized: "\(today.value) \(today.unit) today"))
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: systemImage).font(.system(size: 14))
                Text(title).font(.system(size: 13, weight: .semibold)).tracking(-0.13)
            }
            .foregroundStyle(tint)
            HStack(alignment: .firstTextBaseline, spacing: 1) {
                Text(valueText).displayNumber(27)
                Text(unit).font(.system(size: 16, weight: .semibold)).foregroundStyle(Theme.ink.opacity(0.55))
            }
            TrendPill(systemImage: trendIcon, text: trend, tint: tint)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .glass(.card, cornerRadius: 22)
    }
}

// MARK: - Monthly goal

struct MonthlyGoalCard: View {
    var stats: PersonalStats? = nil

    private var progress: Double { stats?.goalProgress ?? 0.7 }
    private var pointsToGo: Int { stats?.pointsToGoal ?? 2_000 }

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
        let isMe = member.id == Community.current.id
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
    var stats: PersonalStats? = nil

    private static let sampleDays: [(label: LocalizedStringKey, done: Bool)] = [
        ("M", true), ("T", true), ("W", true), ("T", false), ("F", true), ("S", true), ("S", true),
    ]
    private static let dayLabels: [LocalizedStringKey] = ["M", "T", "W", "T", "F", "S", "S"]

    private var days: [(label: LocalizedStringKey, done: Bool)] {
        guard let stats else { return Self.sampleDays }
        return zip(Self.dayLabels, stats.thisWeek).map { (label: $0, done: $1.scans > 0) }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            CardHeader(systemImage: "flame.fill", title: "Recycling Streak", tint: Theme.amber,
                       caption: "This Week", showsChevron: false)
            HStack(alignment: .bottom, spacing: 6) {
                if let stats {
                    Text(verbatim: AwareFormat.grouped(stats.currentStreak)).displayNumber(40)
                    (stats.currentStreak == 1 ? Text("day") : Text("days"))
                        .font(.system(size: 17)).foregroundStyle(Theme.ink.opacity(0.55)).padding(.bottom, 4)
                } else {
                    Text("3").displayNumber(40)
                    Text("days").font(.system(size: 17)).foregroundStyle(Theme.ink.opacity(0.55)).padding(.bottom, 4)
                }
                Spacer(minLength: 0)
                VStack(alignment: .trailing, spacing: 1) {
                    Text("Best").font(.system(size: 11)).foregroundStyle(Theme.ink.opacity(0.5))
                    Group {
                        if let stats {
                            Text("^[\(stats.bestStreak) day](inflect: true)")
                        } else {
                            Text("18 days")
                        }
                    }
                    .font(.system(size: 14, weight: .semibold)).foregroundStyle(Theme.amber)
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
    var stats: PersonalStats? = nil

    private static let names: [(category: ItemCategory, name: LocalizedStringKey, color: Color)] = [
        (.plastic, "Plastic", Theme.green),
        (.paper, "Paper", Color(hex: 0x4FA878)),
        (.metal, "Metal", Color(hex: 0x8FBFA4)),
        (.glass, "Glass", Color(hex: 0xC3DBCC)),
    ]
    private static let sampleCounts: [ItemCategory: Int] = [.plastic: 18, .paper: 14, .metal: 9, .glass: 6]

    private var categories: [(name: LocalizedStringKey, count: Int, color: Color)] {
        let counts = stats?.categoriesThisMonth ?? Self.sampleCounts
        return Self.names.map { (name: $0.name, count: counts[$0.category] ?? 0, color: $0.color) }
    }

    private var total: Int { categories.map(\.count).reduce(0, +) }

    private var weekTrend: String {
        guard let stats else { return "+12 this week" }
        return String(localized: "+\(stats.itemsThisWeek) this week")
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            CardHeader(systemImage: "qrcode.viewfinder", title: "Items Scanned", caption: "This Month")
            HStack(alignment: .bottom, spacing: 6) {
                Text("\(total)").displayNumber(40)
                Text("items").font(.system(size: 17)).foregroundStyle(Theme.ink.opacity(0.55)).padding(.bottom, 4)
                Spacer(minLength: 0)
                TrendPill(systemImage: "arrow.up", text: weekTrend)
            }
            GeometryReader { proxy in
                if total > 0 {
                    HStack(spacing: 3) {
                        ForEach(Array(categories.enumerated()), id: \.offset) { _, category in
                            Capsule().fill(category.color)
                                .frame(width: max(0, (proxy.size.width - 9) * Double(category.count) / Double(total)))
                        }
                    }
                } else {
                    Capsule().fill(Theme.ink.opacity(0.09))
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
    var stats: PersonalStats? = nil

    private struct Activity {
        let icon: String
        let tint: Color
        let title: Text
        let detail: Text
        let points: Int
    }

    // Points follow the reward policy: 20 for a sorted recyclable.
    private static let sampleActivities = [
        Activity(icon: "waterbottle.fill", tint: Theme.green, title: Text("Plastic Bottle"), detail: Text("Recycled · 2m ago"), points: RecyclingPolicy.recyclablePoints),
        Activity(icon: "shippingbox.fill", tint: Theme.amber, title: Text("Cardboard Box"), detail: Text("Recycled · 1h ago"), points: RecyclingPolicy.recyclablePoints),
        Activity(icon: "trophy.fill", tint: Theme.teal, title: Text("Weekly Goal"), detail: Text("Achieved · 3h ago"), points: 100),
    ]

    private var activities: [Activity] {
        guard let stats else { return Self.sampleActivities }
        return stats.recent.compactMap { scan in
            guard let label = scan.canonicalLabel else { return nil }
            let when = scan.scannedAt.formatted(.relative(presentation: .named))
            return Activity(icon: label.iconName, tint: label.tint, title: Text(verbatim: label.displayName),
                            detail: scan.isRecycled ? Text("Recycled · \(when)") : Text("Sorted · \(when)"),
                            points: scan.points)
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            CardHeader(systemImage: "clock.arrow.circlepath", title: "Recent Activity",
                       caption: stats == nil ? "Today" : "Latest", showsChevron: false)
            VStack(spacing: 12) {
                if activities.isEmpty {
                    Text("Scan something and it shows up here.")
                        .font(.system(size: 14))
                        .foregroundStyle(Theme.ink.opacity(0.55))
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                ForEach(Array(activities.enumerated()), id: \.offset) { _, activity in
                    HStack(spacing: 12) {
                        IconTile(systemImage: activity.icon, tint: activity.tint, size: 38, cornerRadius: 13, iconSize: 17)
                        VStack(alignment: .leading, spacing: 1) {
                            activity.title.cardTitleStyle()
                            activity.detail.font(.system(size: 12)).foregroundStyle(Theme.ink.opacity(0.55))
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
    var stats: PersonalStats? = nil
    @ObservedObject private var ledger = RewardLedger.shared

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            CardHeader(systemImage: "globe.asia.australia.fill", title: "Your Impact", tint: Theme.mint,
                       caption: "All Time", showsChevron: false, titleColor: .white,
                       captionColor: .white.opacity(0.7), tileBackground: .white.opacity(0.18))
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                if let stats {
                    Text(verbatim: stats.treesEquivalent.formatted(.number.precision(.fractionLength(0...1))))
                        .displayNumber(46, color: .white)
                } else {
                    Text("3").displayNumber(46, color: .white)
                }
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
    var stats: PersonalStats? = nil

    private static let sampleDays: [(label: LocalizedStringKey, last: CGFloat, this: CGFloat)] = [
        ("M", 18, 26), ("T", 26, 34), ("W", 32, 20), ("T", 23, 46), ("F", 37, 31), ("S", 29, 40), ("S", 20, 23),
    ]
    private static let dayLabels: [LocalizedStringKey] = ["M", "T", "W", "T", "F", "S", "S"]

    /// Bar heights: scans per day, the busiest day of the two weeks full height.
    private var days: [(label: LocalizedStringKey, last: CGFloat, this: CGFloat)] {
        guard let stats else { return Self.sampleDays }
        let peak = max(1, (stats.thisWeek + stats.lastWeek).map(\.scans).max() ?? 1)
        func height(_ scans: Int) -> CGFloat { 4 + 42 * CGFloat(scans) / CGFloat(peak) }
        return (0..<7).map { index in
            (label: Self.dayLabels[index], last: height(stats.lastWeek[index].scans), this: height(stats.thisWeek[index].scans))
        }
    }

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
