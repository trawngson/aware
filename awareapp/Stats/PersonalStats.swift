import Foundation

/// Material groups on Home's "Items Scanned" card and the insight breakdown.
enum ItemCategory: String, CaseIterable, Sendable {
    case plastic, paper, metal, glass
}

extension ScanSnapshot {
    /// Foam (styrofoam, foam cups) is polystyrene, so it counts as plastic.
    var category: ItemCategory? {
        switch canonicalLabel {
        case .plasticBottle, .plasticBag, .styrofoam: .plastic
        case .cardboard: .paper
        case .metalCan: .metal
        case .glassContainer: .glass
        case .disposableCup: choiceID == "paper" ? .paper : .plastic
        case nil: nil
        }
    }

    /// Typical mass kept out of landfill, only when the item was recycled.
    var wasteSavedGrams: Double {
        guard isRecycled, let label = canonicalLabel else { return 0 }
        return PersonalStats.typicalMassGrams(for: label)
    }

    /// CO₂e avoided by recycling it (ImpactFactors), only when it was recycled.
    var co2SavedGrams: Double {
        guard isRecycled, let label = canonicalLabel else { return 0 }
        switch ImpactFactors.estimate(for: label) {
        case .perItem(let grams, _):
            return grams
        case .perKilogram(let gramsPerKilogram, let sizes, let defaultSizeID):
            let mass = sizes.first { $0.id == defaultSizeID }?.massGrams ?? 0
            return gramsPerKilogram * mass / 1_000
        case .unavailable:
            return 0
        }
    }
}

/// The numbers behind Home and the insight screens, from the user's own
/// scans. Days, weeks (Monday first) and months follow the phone's calendar.
struct PersonalStats: Equatable, Sendable {
    /// Totals for a day, week or month.
    struct Totals: Equatable, Sendable {
        let start: Date
        var scans = 0
        /// Scans whose item went to recycling.
        var recycled = 0
        var points = 0
        var wasteGrams = 0.0
        var co2Grams = 0.0

        mutating func add(_ scan: ScanSnapshot) {
            scans += 1
            if scan.isRecycled { recycled += 1 }
            points += scan.points
            wasteGrams += scan.wasteSavedGrams
            co2Grams += scan.co2SavedGrams
        }
    }

    /// Leaves a user aims for each month.
    static let monthlyGoal = 500
    /// CO₂ one tree absorbs in a year (the figure the CO₂ screen quotes).
    static let treeGramsPerYear = 22_000.0

    /// Typical item masses (CO2_IMPACT_NOTES.md; glass and cardboard use the
    /// default sizes of ImpactFactors). Cups and foam have no sourced mass.
    static func typicalMassGrams(for label: CanonicalLabel) -> Double {
        switch label {
        case .plasticBottle: 10
        case .metalCan: 13
        case .plasticBag: 8
        case .glassContainer, .cardboard:
            if case .perKilogram(_, let sizes, let defaultSizeID) = ImpactFactors.estimate(for: label) {
                sizes.first { $0.id == defaultSizeID }?.massGrams ?? 0
            } else {
                0
            }
        case .disposableCup, .styrofoam: 0
        }
    }

    let points: Int
    let wasteGrams: Double
    let co2Grams: Double
    let itemsRecycled: Int
    let today: Totals
    let yesterday: Totals
    /// Monday to Sunday of this week.
    let thisWeek: [Totals]
    let lastWeek: [Totals]
    let thisMonth: Totals
    let lastMonth: Totals
    /// The last six months, oldest first, ending with this one.
    let recentMonths: [Totals]
    let categoriesThisMonth: [ItemCategory: Int]
    let currentStreak: Int
    let bestStreak: Int
    /// Newest first, at most three.
    let recent: [ScanSnapshot]

    var goalProgress: Double { min(Double(max(thisMonth.points, 0)) / Double(Self.monthlyGoal), 1) }
    var pointsToGoal: Int { max(Self.monthlyGoal - thisMonth.points, 0) }
    var itemsThisWeek: Int { thisWeek.reduce(0) { $0 + $1.scans } }
    var itemsThisMonth: Int { categoriesThisMonth.values.reduce(0, +) }
    var treesEquivalent: Double { co2Grams / Self.treeGramsPerYear }
    var thisWeekTotals: Totals { Self.sum(thisWeek, start: thisWeek.first?.start ?? today.start) }
    var lastWeekTotals: Totals { Self.sum(lastWeek, start: lastWeek.first?.start ?? today.start) }

    init(scans: [ScanSnapshot], now: Date = .now, calendar: Calendar = .current) {
        var calendar = calendar
        calendar.firstWeekday = 2
        calendar.minimumDaysInFirstWeek = 4

        let todayStart = calendar.startOfDay(for: now)
        let yesterdayStart = calendar.date(byAdding: .day, value: -1, to: todayStart) ?? todayStart
        let weekStart = calendar.dateInterval(of: .weekOfYear, for: now)?.start ?? todayStart
        let monthStart = calendar.dateInterval(of: .month, for: now)?.start ?? todayStart

        var byDay: [Date: Totals] = [:]
        for scan in scans {
            let day = calendar.startOfDay(for: scan.scannedAt)
            byDay[day, default: Totals(start: day)].add(scan)
        }
        func day(_ start: Date) -> Totals { byDay[start] ?? Totals(start: start) }
        func days(from start: Date) -> [Totals] {
            (0..<7).map { day(calendar.date(byAdding: .day, value: $0, to: start) ?? start) }
        }
        func month(offset: Int) -> Totals {
            let start = calendar.date(byAdding: .month, value: offset, to: monthStart) ?? monthStart
            let end = calendar.date(byAdding: .month, value: 1, to: start) ?? start
            var totals = Totals(start: start)
            for scan in scans where scan.scannedAt >= start && scan.scannedAt < end {
                totals.add(scan)
            }
            return totals
        }

        points = scans.reduce(0) { $0 + $1.points }
        wasteGrams = scans.reduce(0) { $0 + $1.wasteSavedGrams }
        co2Grams = scans.reduce(0) { $0 + $1.co2SavedGrams }
        itemsRecycled = scans.filter(\.isRecycled).count
        today = day(todayStart)
        yesterday = day(yesterdayStart)
        thisWeek = days(from: weekStart)
        lastWeek = days(from: calendar.date(byAdding: .day, value: -7, to: weekStart) ?? weekStart)
        thisMonth = month(offset: 0)
        lastMonth = month(offset: -1)
        recentMonths = (-5...0).map(month(offset:))

        let monthEnd = calendar.date(byAdding: .month, value: 1, to: monthStart) ?? monthStart
        var categories: [ItemCategory: Int] = [:]
        for scan in scans where scan.scannedAt >= monthStart && scan.scannedAt < monthEnd {
            if let category = scan.category { categories[category, default: 0] += 1 }
        }
        categoriesThisMonth = categories

        let activeDays = Set(byDay.keys)
        var streak = 0
        var cursor = activeDays.contains(todayStart) ? todayStart : yesterdayStart
        while activeDays.contains(cursor) {
            streak += 1
            cursor = calendar.date(byAdding: .day, value: -1, to: cursor) ?? cursor
        }
        currentStreak = streak

        var best = 0
        var run = 0
        var previous: Date?
        for day in activeDays.sorted() {
            if let previous, calendar.date(byAdding: .day, value: 1, to: previous) == day {
                run += 1
            } else {
                run = 1
            }
            best = max(best, run)
            previous = day
        }
        bestStreak = best

        recent = Array(scans.sorted { $0.scannedAt > $1.scannedAt }.prefix(3))
    }

    private static func sum(_ days: [Totals], start: Date) -> Totals {
        var totals = Totals(start: start)
        for day in days {
            totals.scans += day.scans
            totals.recycled += day.recycled
            totals.points += day.points
            totals.wasteGrams += day.wasteGrams
            totals.co2Grams += day.co2Grams
        }
        return totals
    }

    /// Percent change from `previous` to `current`, or nil when there's
    /// nothing to compare with.
    static func percentChange(from previous: Double, to current: Double) -> Int? {
        guard previous > 0 else { return nil }
        return Int(((current - previous) / previous * 100).rounded())
    }
}
