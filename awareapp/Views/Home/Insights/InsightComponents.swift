import SwiftUI

/// Big glass summary at the top of an insights screen.
struct InsightHeroCard: View {
    let systemImage: String
    let title: LocalizedStringKey
    let value: Int
    let unit: String
    let trendIcon: String
    let trend: LocalizedStringKey

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
                Text(AwareFormat.grouped(value)).displayNumber(58, color: .white)
                Text(unit).font(.system(size: 22, weight: .medium)).foregroundStyle(.white.opacity(0.72))
            }

            Label(trend, systemImage: trendIcon)
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
    let text: LocalizedStringKey

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
                Text(text)
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
