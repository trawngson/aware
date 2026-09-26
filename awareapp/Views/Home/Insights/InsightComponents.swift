import SwiftUI

/// The hero card's week-over-week line for the user's own numbers.
enum InsightTrend {
    static func weekly(current: Double, previous: Double) -> (icon: String, text: Text) {
        guard let change = PersonalStats.percentChange(from: previous, to: current) else {
            return ("sparkles", Text("Keep scanning to see your trend"))
        }
        let signed = change >= 0 ? "+\(change)%" : "\(change)%"
        return (change >= 0 ? "arrow.up.right" : "arrow.down.right", Text("\(signed) from last week"))
    }
}

/// Big glass summary at the top of an insights screen.
struct InsightHeroCard: View {
    let systemImage: String
    let title: LocalizedStringKey
    let valueText: String
    let unit: String
    let trendIcon: String
    let trend: Text

    init(systemImage: String, title: LocalizedStringKey, value: Int, unit: String, trendIcon: String,
         trend: LocalizedStringKey) {
        self.init(systemImage: systemImage, title: title, valueText: AwareFormat.grouped(value), unit: unit,
                  trendIcon: trendIcon, trend: Text(trend))
    }

    init(systemImage: String, title: LocalizedStringKey, valueText: String, unit: String, trendIcon: String,
         trend: Text) {
        self.systemImage = systemImage
        self.title = title
        self.valueText = valueText
        self.unit = unit
        self.trendIcon = trendIcon
        self.trend = trend
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label {
                Text(title)
            } icon: {
                Image(systemName: systemImage).foregroundStyle(Theme.mint)
            }
            .font(.system(size: 14, weight: .semibold))
            .foregroundStyle(.white.opacity(0.85))

            HStack(alignment: .firstTextBaseline, spacing: 5) {
                Text(valueText).displayNumber(58, color: .white)
                Text(unit).font(.system(size: 22, weight: .medium)).foregroundStyle(.white.opacity(0.72))
            }

            Label {
                trend
            } icon: {
                Image(systemName: trendIcon)
            }
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(Theme.mint)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 20)
        .padding(.top, 18)
        .padding(.bottom, 20)
        .glass(.frosted, cornerRadius: 28)
    }
}

/// Native segmented control, kept light on the pale background.
struct PeriodPicker: View {
    @Binding var period: InsightPeriod

    var body: some View {
        Picker("Period", selection: $period.animation(.snappy)) {
            ForEach(InsightPeriod.allCases) { Text($0.title).tag($0) }
        }
        .pickerStyle(.segmented)
        .environment(\.colorScheme, .light)
    }
}

struct InsightSection<Content: View>: View {
    let title: LocalizedStringKey
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title)
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(Theme.ink)
                .padding(.leading, 2)
            content
        }
    }
}

struct StatGrid: View {
    let stats: [InsightStat]

    var body: some View {
        LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)], spacing: 10) {
            ForEach(stats) { stat in
                VStack(alignment: .leading, spacing: 5) {
                    Label {
                        Text(stat.title)
                    } icon: {
                        Image(systemName: stat.icon).foregroundStyle(stat.color)
                    }
                    .font(.system(size: 13))
                    .foregroundStyle(Theme.ink.opacity(0.6))
                    Text(AwareFormat.grouped(stat.value) + stat.unit)
                        .font(.system(size: 22, weight: .bold))
                        .tracking(-0.55)
                        .foregroundStyle(Theme.ink)
                    Label(stat.trend, systemImage: stat.trendUp ? "arrow.up.right" : "arrow.down.right")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(Theme.greenDeep)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(14)
                .glass(.card, cornerRadius: 20)
                .accessibilityElement(children: .combine)
            }
        }
    }
}

/// Icon + text card used for tips and facts.
struct InsightTipRow: View {
    let systemImage: String
    let tint: Color
    var title: LocalizedStringKey? = nil
    let text: Text

    init(systemImage: String, tint: Color, title: LocalizedStringKey? = nil, text: LocalizedStringKey) {
        self.init(systemImage: systemImage, tint: tint, title: title, text: Text(text))
    }

    init(systemImage: String, tint: Color, title: LocalizedStringKey? = nil, text: Text) {
        self.systemImage = systemImage
        self.tint = tint
        self.title = title
        self.text = text
    }

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: systemImage)
                .font(.system(size: 17))
                .foregroundStyle(tint)
                .frame(width: 36, height: 36)
                .background(Circle().fill(tint.opacity(0.15)))
            VStack(alignment: .leading, spacing: 3) {
                if let title {
                    Text(title).font(.system(size: 15, weight: .semibold)).foregroundStyle(Theme.ink)
                }
                text
                    .font(.system(size: 13))
                    .lineSpacing(2)
                    .foregroundStyle(Theme.ink.opacity(title == nil ? 0.68 : 0.62))
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 0)
        }
        .padding(14)
        .glass(.card, cornerRadius: 20)
    }
}
