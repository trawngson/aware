import Charts
import SwiftUI

struct CO2InsightsView: View {
    @State private var period: InsightPeriod = .week
    @ObservedObject private var ledger = RewardLedger.shared
    @ObservedObject private var session = AppSession.shared

    /// The user's own numbers, or nil while the sample numbers show.
    private var stats: PersonalStats? { MyStats.current }

    private var savingsData: [DataPoint] {
        if let stats { return stats.co2Points(for: period) }
        return period == .week ? SampleData.co2Weekly : SampleData.co2Monthly
    }

    private static let sampleImpact: [(icon: String, tint: Color, value: String, label: LocalizedStringKey)] = [
        ("tree.fill", Theme.green, AwareFormat.grouped(24), "Trees equivalent"),
        ("car.fill", Theme.blue, AwareFormat.grouped(3_200), "km not driven"),
        ("drop.fill", Theme.cyan, AwareFormat.grouped(8_400), "Liters water"),
        ("bolt.fill", Theme.gold, AwareFormat.grouped(520), "kWh energy"),
    ]

    /// Only figures with a stated basis: trees use the 22 kg a year quoted below.
    private var impact: [(icon: String, tint: Color, value: String, label: LocalizedStringKey)] {
        guard let stats else { return Self.sampleImpact }
        return [
            ("tree.fill", Theme.green, stats.treesEquivalent.formatted(.number.precision(.fractionLength(0...1))),
             "Trees equivalent"),
            ("arrow.3.trianglepath", Theme.blue, AwareFormat.grouped(stats.itemsRecycled), "Items recycled"),
            ("flame.fill", Theme.orange, AwareFormat.grouped(stats.currentStreak), "Day streak"),
            ("leaf.fill", Theme.gold, AwareFormat.grouped(stats.points), "Leaves earned"),
        ]
    }

    var body: some View {
        let stats = self.stats
        TabScrollView {
            VStack(spacing: 16) {
                if let stats {
                    let total = AwareFormat.mass(grams: stats.co2Grams)
                    let trend = InsightTrend.weekly(current: stats.thisWeekTotals.co2Grams,
                                                    previous: stats.lastWeekTotals.co2Grams)
                    InsightHeroCard(systemImage: "cloud.fill", title: "CO₂ emissions saved", valueText: total.value,
                                    unit: total.unit, trendIcon: trend.icon, trend: trend.text)
                } else {
                    InsightHeroCard(systemImage: "cloud.fill", title: "CO₂ emissions saved", value: 1_250, unit: "kg",
                                    trendIcon: "arrow.down.right", trend: "−9% emissions vs. average")
                }
                PeriodPicker(period: $period)
                savingsCard
                InsightSection(title: "Environmental impact") {
                    LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)], spacing: 10) {
                        ForEach(impact, id: \.icon) { item in
                            VStack(spacing: 6) {
                                Image(systemName: item.icon).font(.system(size: 26)).foregroundStyle(item.tint)
                                Text(item.value)
                                    .font(.system(size: 20, weight: .bold))
                                    .tracking(-0.4)
                                    .foregroundStyle(Theme.ink)
                                Text(item.label)
                                    .font(.system(size: 12))
                                    .foregroundStyle(Theme.ink.opacity(0.6))
                                    .multilineTextAlignment(.center)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 16)
                            .glass(.card, cornerRadius: 20)
                            .accessibilityElement(children: .combine)
                        }
                    }
                }
                InsightSection(title: "Statistics") {
                    StatGrid(stats: stats?.co2Stats ?? SampleData.co2Stats)
                }
                InsightSection(title: "Did you know?") {
                    VStack(spacing: 10) {
                        if let stats {
                            let offset = (stats.co2Grams / 4_000_000).formatted(.percent.precision(.fractionLength(0...2)))
                            let trees = stats.treesEquivalent.formatted(.number.precision(.fractionLength(0...1)))
                            InsightTipRow(systemImage: "globe.asia.australia.fill", tint: Theme.blue,
                                          text: Text("The average person produces about 4 tons of CO₂ per year. You've offset \(offset) of that."))
                            InsightTipRow(systemImage: "leaf.fill", tint: Theme.green,
                                          text: Text("One tree absorbs about 22kg of CO₂ per year — your savings equal \(trees) trees working for a year."))
                        } else {
                            InsightTipRow(systemImage: "globe.asia.australia.fill", tint: Theme.blue,
                                          text: "The average person produces about 4 tons of CO₂ per year. You've offset 31% of that.")
                            InsightTipRow(systemImage: "leaf.fill", tint: Theme.green,
                                          text: "One tree absorbs about 22kg of CO₂ per year — your savings equal 57 trees working for a year.")
                        }
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 6)
            .padding(.bottom, 20)
        }
        .scrollIndicators(.hidden)
        .background {
            ForestBackdrop(blurFrom: 0.22, blurTo: 0.4,
                           scrim: ForestBackdrop.scrim(dark: 0.52, darkEnd: 0.18, mistStart: 0.36, mistMid: 0.54))
        }
        .forestNavigationBar("CO₂ Saved")
    }

    private var savingsCard: some View {
        let peak = savingsData.max { $0.value < $1.value }
        return VStack(alignment: .leading, spacing: 10) {
            Text("Daily savings").font(.system(size: 16, weight: .semibold)).foregroundStyle(Theme.ink)
            Chart(savingsData) { point in
                BarMark(x: .value("Period", point.label), y: .value("CO₂", point.value), width: .ratio(0.78))
                    .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
                    .foregroundStyle(point.id == peak?.id
                                     ? LinearGradient(colors: [Theme.green, Theme.green.opacity(0.7)], startPoint: .top, endPoint: .bottom)
                                     : LinearGradient(colors: [Theme.greenBright, Theme.greenBright.opacity(0.62)], startPoint: .top, endPoint: .bottom))
            }
            .chartYAxis(.hidden)
            .chartXAxis {
                AxisMarks { _ in
                    AxisValueLabel().font(.system(size: 11)).foregroundStyle(Theme.ink.opacity(0.55))
                }
            }
            .frame(height: 160)
        }
        .padding(16)
        .glass(.card)
    }
}

#Preview {
    NavigationStack {
        CO2InsightsView()
    }
    .preferredColorScheme(.dark)
}
