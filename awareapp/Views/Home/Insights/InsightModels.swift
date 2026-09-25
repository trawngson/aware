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
