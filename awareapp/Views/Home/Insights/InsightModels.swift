import SwiftUI

// MARK: - Data Models

struct DataPoint: Identifiable {
    let id = UUID()
    let label: String
    let value: Double
}

struct InsightStat: Identifiable {
    let id = UUID()
    let title: String
    let value: String
    let trend: String
    let trendUp: Bool
    let icon: String
    let color: Color
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
    
    static let wasteByCategory: [DataPoint] = [
        DataPoint(label: "Plastic", value: 42),
        DataPoint(label: "Paper", value: 28),
        DataPoint(label: "Glass", value: 15),
        DataPoint(label: "Metal", value: 10),
        DataPoint(label: "Other", value: 5)
    ]
    
    static let wasteStats: [InsightStat] = [
        InsightStat(title: "Today", value: "1,400g", trend: "+18%", trendUp: true, icon: "leaf.fill", color: .green),
        InsightStat(title: "This Week", value: "8,700g", trend: "+12%", trendUp: true, icon: "calendar", color: .blue),
        InsightStat(title: "This Month", value: "32,400g", trend: "+24%", trendUp: true, icon: "chart.line.uptrend.xyaxis", color: .purple),
        InsightStat(title: "Items Recycled", value: "847", trend: "+156", trendUp: true, icon: "arrow.3.trianglepath", color: .orange)
    ]
    
    static let co2Stats: [InsightStat] = [
        InsightStat(title: "Today", value: "210kg", trend: "+22%", trendUp: true, icon: "leaf.fill", color: .green),
        InsightStat(title: "This Week", value: "1,350kg", trend: "+15%", trendUp: true, icon: "calendar", color: .blue),
        InsightStat(title: "This Month", value: "4,800kg", trend: "+31%", trendUp: true, icon: "chart.line.uptrend.xyaxis", color: .purple),
        InsightStat(title: "Trees Equivalent", value: "24", trend: "+4", trendUp: true, icon: "tree.fill", color: .green)
    ]
}
