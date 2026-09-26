import Charts
import SwiftUI

struct WasteInsightsView: View {
    @State private var period: InsightPeriod = .week

    private var trendData: [DataPoint] {
        period == .week ? SampleData.wasteWeekly : SampleData.wasteMonthly
    }

    var body: some View {
        TabScrollView {
            VStack(spacing: 16) {
                InsightHeroCard(systemImage: "trash.fill", title: "Total waste saved", value: 6_700, unit: "g",
                                trendIcon: "arrow.up.right", trend: "+12% from last week")
                PeriodPicker(period: $period)
                trendCard
                InsightSection(title: "Statistics") {
                    StatGrid(stats: SampleData.wasteStats)
                }
                breakdownCard
                InsightSection(title: "Tips to improve") {
                    VStack(spacing: 10) {
                        InsightTipRow(systemImage: "lightbulb.fill", tint: Theme.orangeDeep, title: "Reduce plastic usage",
                                      text: "Bring reusable bags when shopping to cut plastic waste by up to 40%.")
                        InsightTipRow(systemImage: "leaf.arrow.triangle.circlepath", tint: Theme.green, title: "Compost food scraps",
                                      text: "Start composting to divert organic waste from landfills.")
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 6)
            .padding(.bottom, 20)
        }
        .scrollIndicators(.hidden)
        .background { ForestBackdrop.detail }
        .forestNavigationBar("Waste Saved")
    }

    // MARK: - Trend

    private var trendCard: some View {
        let values = trendData.map(\.value)
        let low = (values.min() ?? 0)
        let high = (values.max() ?? 1)
        let floor = low - (high - low) * 0.02
        let peak = trendData.max { $0.value < $1.value }

        return VStack(alignment: .leading, spacing: 10) {
            Text("Trend").font(.system(size: 16, weight: .semibold)).foregroundStyle(Theme.ink)
            Chart(trendData) { point in
                AreaMark(x: .value("Period", point.label),
                         yStart: .value("Base", floor),
                         yEnd: .value("Waste", point.value))
                    .foregroundStyle(LinearGradient(colors: [Theme.green.opacity(0.32), Theme.green.opacity(0.04)],
                                                    startPoint: .top, endPoint: .bottom))
                LineMark(x: .value("Period", point.label), y: .value("Waste", point.value))
                    .foregroundStyle(Theme.green)
                    .lineStyle(StrokeStyle(lineWidth: 3, lineCap: .round, lineJoin: .round))
                if point.id == peak?.id {
                    PointMark(x: .value("Period", point.label), y: .value("Waste", point.value))
                        .symbol {
                            Circle().fill(Theme.green).frame(width: 10, height: 10)
                                .overlay(Circle().strokeBorder(.white, lineWidth: 2.5))
                        }
                }
            }
            .chartYScale(domain: floor...(high + (high - low) * 0.05))
            .chartYAxis {
                AxisMarks(values: .automatic(desiredCount: 4)) { _ in
                    AxisGridLine(stroke: StrokeStyle(lineWidth: 1, dash: [5, 5]))
                        .foregroundStyle(Theme.ink.opacity(0.14))
                }
            }
            .chartXAxis {
                AxisMarks { _ in
                    AxisValueLabel().font(.system(size: 11)).foregroundStyle(Theme.ink.opacity(0.55))
                }
            }
            .frame(height: 170)
            .environment(\.colorScheme, .light)
        }
        .padding(16)
        .glass(.card)
    }

    // MARK: - Breakdown

    private var breakdownCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Breakdown by category").font(.system(size: 16, weight: .semibold)).foregroundStyle(Theme.ink)
            HStack(spacing: 18) {
                Chart(Array(SampleData.wasteByCategory.enumerated()), id: \.offset) { _, category in
                    SectorMark(angle: .value("Share", category.value), innerRadius: .ratio(0.62))
                        .foregroundStyle(category.color)
                }
                .chartLegend(.hidden)
                .frame(width: 130, height: 130)
                .overlay {
                    VStack(spacing: 1) {
                        Text("Total").font(.system(size: 11)).foregroundStyle(Theme.ink.opacity(0.55))
                        Text("100%").font(.system(size: 20, weight: .bold)).foregroundStyle(Theme.ink)
                    }
                }
                VStack(spacing: 9) {
                    ForEach(Array(SampleData.wasteByCategory.enumerated()), id: \.offset) { _, category in
                        HStack(spacing: 8) {
                            Circle().fill(category.color).frame(width: 10, height: 10)
                            Text(category.label).font(.system(size: 14)).foregroundStyle(Theme.ink)
                            Spacer(minLength: 0)
                            Text("\(Int(category.value))%")
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundStyle(Theme.ink.opacity(0.62))
                        }
                    }
                }
            }
        }
        .padding(16)
        .glass(.card)
    }
}

#Preview {
    NavigationStack {
        WasteInsightsView()
    }
    .preferredColorScheme(.dark)
}
