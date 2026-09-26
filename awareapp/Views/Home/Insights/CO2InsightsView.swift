import Charts
import SwiftUI

struct CO2InsightsView: View {
    @State private var period: InsightPeriod = .week

    private var savingsData: [DataPoint] {
        period == .week ? SampleData.co2Weekly : SampleData.co2Monthly
    }

    private let impact: [(icon: String, tint: Color, value: Int, label: LocalizedStringKey)] = [
        ("tree.fill", Theme.green, 24, "Trees equivalent"),
        ("car.fill", Theme.blue, 3_200, "km not driven"),
        ("drop.fill", Theme.cyan, 8_400, "Liters water"),
        ("bolt.fill", Theme.gold, 520, "kWh energy"),
    ]

    var body: some View {
        TabScrollView {
            VStack(spacing: 16) {
                InsightHeroCard(systemImage: "cloud.fill", title: "CO₂ emissions saved", value: 1_250, unit: "kg",
                                trendIcon: "arrow.down.right", trend: "−9% emissions vs. average")
                PeriodPicker(period: $period)
                savingsCard
                InsightSection(title: "Environmental impact") {
                    LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)], spacing: 10) {
                        ForEach(impact, id: \.icon) { item in
                            VStack(spacing: 6) {
                                Image(systemName: item.icon).font(.system(size: 26)).foregroundStyle(item.tint)
                                Text(AwareFormat.grouped(item.value))
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
                    StatGrid(stats: SampleData.co2Stats)
                }
                InsightSection(title: "Did you know?") {
                    VStack(spacing: 10) {
                        InsightTipRow(systemImage: "globe.asia.australia.fill", tint: Theme.blue,
                                      text: "The average person produces about 4 tons of CO₂ per year. You've offset 31% of that.")
                        InsightTipRow(systemImage: "leaf.fill", tint: Theme.green,
                                      text: "One tree absorbs about 22kg of CO₂ per year — your savings equal 57 trees working for a year.")
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
