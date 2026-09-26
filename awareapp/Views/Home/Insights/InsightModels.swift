import SwiftUI

// MARK: - Data Models

struct DataPoint: Identifiable {
    let id = UUID()
    let label: String
    let value: Double
}

struct InsightStat: Identifiable {
    let id = UUID()
    let title: LocalizedStringKey
    let value: Int
    var unit: String = ""
    let trend: String
    let trendUp: Bool
    let icon: String
    let color: Color
}

enum InsightPeriod: String, CaseIterable, Identifiable {
    case week, month

    var id: String { rawValue }

    var title: LocalizedStringKey {
        switch self {
        case .week: "Week"
        case .month: "Month"
        }
    }
}

// MARK: - Sample Data

enum SampleData {
    static let wasteWeekly: [DataPoint] = [
        DataPoint(label: "Mon", value: 850),
        DataPoint(label: "Tue", value: 1200),
        DataPoint(label: "Wed", value: 950),
        DataPoint(label: "Thu", value: 1400),
        DataPoint(label: "Fri", value: 1100),
        DataPoint(label: "Sat", value: 1800),
        DataPoint(label: "Sun", value: 1400)
    ]

    static let wasteMonthly: [DataPoint] = [
        DataPoint(label: "Jan", value: 18500),
        DataPoint(label: "Feb", value: 22000),
        DataPoint(label: "Mar", value: 19800),
        DataPoint(label: "Apr", value: 24500),
        DataPoint(label: "May", value: 28000),
        DataPoint(label: "Jun", value: 31200)
    ]

    static let co2Weekly: [DataPoint] = [
        DataPoint(label: "Mon", value: 120),
        DataPoint(label: "Tue", value: 180),
        DataPoint(label: "Wed", value: 150),
        DataPoint(label: "Thu", value: 220),
        DataPoint(label: "Fri", value: 190),
        DataPoint(label: "Sat", value: 280),
        DataPoint(label: "Sun", value: 210)
    ]

    static let co2Monthly: [DataPoint] = [
        DataPoint(label: "Jan", value: 2800),
        DataPoint(label: "Feb", value: 3200),
        DataPoint(label: "Mar", value: 2950),
        DataPoint(label: "Apr", value: 3800),
        DataPoint(label: "May", value: 4200),
        DataPoint(label: "Jun", value: 4800)
    ]

    static let wasteByCategory: [(label: LocalizedStringKey, value: Double, color: Color)] = [
        ("Plastic", 42, Theme.green),
        ("Paper", 28, Theme.blue),
        ("Glass", 15, Theme.cyan),
        ("Metal", 10, Theme.orange),
        ("Other", 5, Theme.stone)
    ]

    static let wasteStats: [InsightStat] = [
        InsightStat(title: "Today", value: 1_400, unit: "g", trend: "+18%", trendUp: true, icon: "leaf.fill", color: Theme.green),
        InsightStat(title: "This week", value: 8_700, unit: "g", trend: "+12%", trendUp: true, icon: "calendar", color: Theme.blue),
        InsightStat(title: "This month", value: 32_400, unit: "g", trend: "+24%", trendUp: true, icon: "chart.line.uptrend.xyaxis", color: Theme.purple),
        InsightStat(title: "Items recycled", value: 847, trend: "+156", trendUp: true, icon: "arrow.3.trianglepath", color: Theme.orange)
    ]

    static let co2Stats: [InsightStat] = [
        InsightStat(title: "Today", value: 210, unit: "kg", trend: "+22%", trendUp: true, icon: "leaf.fill", color: Theme.green),
        InsightStat(title: "This week", value: 1_350, unit: "kg", trend: "+15%", trendUp: true, icon: "calendar", color: Theme.blue),
        InsightStat(title: "This month", value: 4_800, unit: "kg", trend: "+31%", trendUp: true, icon: "chart.line.uptrend.xyaxis", color: Theme.purple),
        InsightStat(title: "Trees equiv.", value: 24, trend: "+4", trendUp: true, icon: "tree.fill", color: Theme.green)
    ]
}

// MARK: - The user's own data

extension PersonalStats {
    /// Short weekday names, Monday first, in the user's language.
    static var weekdayLabels: [String] {
        let symbols = Calendar.current.shortWeekdaySymbols
        return Array(symbols[1...] + symbols[..<1])
    }

    private static func monthLabel(_ date: Date) -> String {
        date.formatted(.dateTime.month(.abbreviated))
    }

    /// "+12%", or "–" when there is nothing to compare with.
    static func trendText(from previous: Double, to current: Double) -> (text: String, up: Bool) {
        guard let change = percentChange(from: previous, to: current) else { return ("–", true) }
        return (change >= 0 ? "+\(change)%" : "\(change)%", change >= 0)
    }

    func wastePoints(for period: InsightPeriod) -> [DataPoint] {
        switch period {
        case .week:
            zip(Self.weekdayLabels, thisWeek).map { DataPoint(label: $0, value: $1.wasteGrams) }
        case .month:
            recentMonths.map { DataPoint(label: Self.monthLabel($0.start), value: $0.wasteGrams) }
        }
    }

    func co2Points(for period: InsightPeriod) -> [DataPoint] {
        switch period {
        case .week:
            zip(Self.weekdayLabels, thisWeek).map { DataPoint(label: $0, value: $1.co2Grams) }
        case .month:
            recentMonths.map { DataPoint(label: Self.monthLabel($0.start), value: $0.co2Grams) }
        }
    }

    private func stat(_ title: LocalizedStringKey, grams: Double, previous: Double, icon: String, color: Color) -> InsightStat {
        let trend = Self.trendText(from: previous, to: grams)
        return InsightStat(title: title, value: Int(grams.rounded()), unit: "g", trend: trend.text,
                           trendUp: trend.up, icon: icon, color: color)
    }

    var wasteStats: [InsightStat] {
        [
            stat("Today", grams: today.wasteGrams, previous: yesterday.wasteGrams, icon: "leaf.fill", color: Theme.green),
            stat("This week", grams: thisWeekTotals.wasteGrams, previous: lastWeekTotals.wasteGrams,
                 icon: "calendar", color: Theme.blue),
            stat("This month", grams: thisMonth.wasteGrams, previous: lastMonth.wasteGrams,
                 icon: "chart.line.uptrend.xyaxis", color: Theme.purple),
            InsightStat(title: "Items recycled", value: itemsRecycled,
                        trend: "+\(thisWeekTotals.recycled)",
                        trendUp: true, icon: "arrow.3.trianglepath", color: Theme.orange),
        ]
    }

    var co2Stats: [InsightStat] {
        [
            stat("Today", grams: today.co2Grams, previous: yesterday.co2Grams, icon: "leaf.fill", color: Theme.green),
            stat("This week", grams: thisWeekTotals.co2Grams, previous: lastWeekTotals.co2Grams,
                 icon: "calendar", color: Theme.blue),
            stat("This month", grams: thisMonth.co2Grams, previous: lastMonth.co2Grams,
                 icon: "chart.line.uptrend.xyaxis", color: Theme.purple),
            InsightStat(title: "Leaves earned", value: points, trend: "+\(thisWeekTotals.points)", trendUp: true,
                        icon: "leaf.circle.fill", color: Theme.green),
        ]
    }

    /// This month's items by material, as shares of 100.
    var categoryShares: [(label: LocalizedStringKey, value: Double, color: Color)] {
        let total = Double(max(itemsThisMonth, 1))
        func share(_ category: ItemCategory) -> Double {
            (Double(categoriesThisMonth[category] ?? 0) / total * 100).rounded()
        }
        return [
            ("Plastic", share(.plastic), Theme.green),
            ("Paper", share(.paper), Theme.blue),
            ("Glass", share(.glass), Theme.cyan),
            ("Metal", share(.metal), Theme.orange),
        ]
    }
}
