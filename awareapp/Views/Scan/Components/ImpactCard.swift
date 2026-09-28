import SwiftUI

/// "Estimated CO₂e avoided" card on the results screen. Three variants:
/// a per-item figure with comparison bars, a per-kilogram figure with a size
/// picker, or a short "no estimate" row.
struct ImpactCard: View {
    let label: CanonicalLabel
    /// False when the policy sends the item to other waste: nothing is
    /// avoided because it isn't recycled.
    let isRecycled: Bool
    let onShowInfo: () -> Void

    @State private var selectedSizeID: String?

    var body: some View {
        switch (isRecycled, ImpactFactors.estimate(for: label)) {
        case (true, .perItem(let grams, let range)):
            perItemCard(grams: grams, range: range)
        case (true, .perKilogram(let perKilogram, let sizes, let defaultSizeID)):
            perKilogramCard(perKilogram: perKilogram, sizes: sizes, defaultSizeID: defaultSizeID)
        case (true, .unavailable):
            noEstimateRow(title: "No CO₂e estimate available", subtitle: "Sorting rules still apply")
        case (false, _):
            noEstimateRow(title: "No CO₂e saving here", subtitle: "It goes in other waste, not recycling")
        }
    }

    // MARK: - Per item

    private func perItemCard(grams: Double, range: ClosedRange<Double>?) -> some View {
        let maxGrams = ImpactFactors.perItemReference.map(\.grams).max() ?? grams
        return VStack(alignment: .leading, spacing: 14) {
            header
            HStack(alignment: .firstTextBaseline, spacing: 7) {
                bigValue(grams: grams)
                Spacer(minLength: 0)
                if let range {
                    captionChip("range \(Int(range.lowerBound))–\(Int(range.upperBound)) g")
                }
            }
            VStack(spacing: 7) {
                ForEach(ImpactFactors.perItemReference, id: \.label) { reference in
                    comparisonBar(
                        title: reference.label == label ? String(localized: "This item") : reference.label.shortName,
                        grams: reference.grams,
                        fraction: reference.grams / maxGrams,
                        highlighted: reference.label == label
                    )
                }
            }
            .padding(.top, 2)
        }
        .padding(18)
        .glass(.card, cornerRadius: 26)
    }

    private func comparisonBar(title: String, grams: Double, fraction: Double, highlighted: Bool) -> some View {
        HStack(spacing: 9) {
            Text(title)
                .font(.system(size: highlighted ? 13 : 12, weight: highlighted ? .semibold : .regular))
                .foregroundStyle(highlighted ? Theme.ink : Theme.ink.opacity(0.55))
                .frame(width: 64, alignment: .leading)
                .lineLimit(1)
                .minimumScaleFactor(0.8)
            GeometryReader { proxy in
                ZStack(alignment: .leading) {
                    Capsule().fill(highlighted ? Theme.green.opacity(0.12) : Theme.ink.opacity(0.07))
                    Capsule()
                        .fill(highlighted ? AnyShapeStyle(LinearGradient(colors: [Theme.greenBright, Theme.green],
                                                                         startPoint: .leading, endPoint: .trailing))
                                          : AnyShapeStyle(Theme.ink.opacity(0.28)))
                        .frame(width: max(6, proxy.size.width * fraction))
                }
            }
            .frame(height: 8)
            Text("\(Int(grams)) g")
                .font(.system(size: highlighted ? 13 : 12, weight: highlighted ? .semibold : .regular))
                .foregroundStyle(highlighted ? Theme.green : Theme.ink.opacity(0.55))
                .frame(width: 44, alignment: .trailing)
        }
        .accessibilityElement(children: .combine)
    }

    // MARK: - Per kilogram

    private func perKilogramCard(perKilogram: Double, sizes: [ItemSize], defaultSizeID: String) -> some View {
        let selected = sizes.first { $0.id == (selectedSizeID ?? defaultSizeID) } ?? sizes[0]
        let grams = perKilogram * selected.massGrams / 1000
        let low = perKilogram * (sizes.map(\.massGrams).min() ?? 0) / 1000
        let high = perKilogram * (sizes.map(\.massGrams).max() ?? 0) / 1000
        let lowText = AwareFormat.mass(grams: low)
        let highText = AwareFormat.mass(grams: high)

        return VStack(alignment: .leading, spacing: 14) {
            header
            HStack(alignment: .firstTextBaseline, spacing: 7) {
                bigValue(grams: grams)
                Spacer(minLength: 0)
                captionChip(lowText.unit == highText.unit
                            ? "\(lowText.value)–\(highText.value) \(highText.unit) across class"
                            : "\(lowText.value) \(lowText.unit)–\(highText.value) \(highText.unit) across class")
            }
            Text("Depends on weight — pick the closest size.")
                .font(.system(size: 13.5))
                .foregroundStyle(Theme.ink.opacity(0.66))
            HStack(spacing: 7) {
                ForEach(sizes) { size in
                    let isSelected = size.id == selected.id
                    Button {
                        withAnimation(.snappy) { selectedSizeID = size.id }
                    } label: {
                        VStack(spacing: 1) {
                            Text(size.name).font(.system(size: 12.5, weight: .semibold))
                            Text(AwareFormat.mass(grams: size.massGrams).value + " " + AwareFormat.mass(grams: size.massGrams).unit)
                                .font(.system(size: 12.5, weight: .medium))
                                .opacity(isSelected ? 0.82 : 0.7)
                        }
                        .foregroundStyle(isSelected ? .white : Theme.ink.opacity(0.7))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                        .padding(.horizontal, 5)
                        .background(
                            RoundedRectangle(cornerRadius: 13, style: .continuous)
                                .fill(isSelected ? AnyShapeStyle(Theme.primaryGradient) : AnyShapeStyle(Theme.ink.opacity(0.06)))
                                .shadow(color: Theme.green.opacity(isSelected ? 0.26 : 0), radius: 5, y: 4)
                        )
                    }
                    .buttonStyle(.plain)
                    .accessibilityAddTraits(isSelected ? .isSelected : [])
                }
            }
        }
        .padding(18)
        .glass(.card, cornerRadius: 26)
    }

    // MARK: - No estimate

    private func noEstimateRow(title: LocalizedStringKey, subtitle: LocalizedStringKey) -> some View {
        Button(action: onShowInfo) {
            HStack(spacing: 11) {
                IconTile(systemImage: "icloud.slash.fill", tint: Theme.ink.opacity(0.45), background: Theme.ink.opacity(0.07),
                         size: 30, cornerRadius: 10, iconSize: 14)
                VStack(alignment: .leading, spacing: 1) {
                    Text(title).cardTitleStyle()
                    Text(subtitle).font(.system(size: 13)).foregroundStyle(Theme.ink.opacity(0.6))
                }
                Spacer(minLength: 0)
                Image(systemName: "chevron.right")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(Theme.ink.opacity(0.3))
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 15)
            .glass(.card, cornerRadius: 22)
            .contentShape(Rectangle())
        }
        .buttonStyle(PressableStyle())
    }

    // MARK: - Shared

    private var header: some View {
        HStack(spacing: 8) {
            IconTile(systemImage: "cloud.fill")
            Text("Estimated CO₂e avoided")
                .font(.system(size: 16, weight: .semibold))
                .tracking(-0.24)
                .foregroundStyle(Theme.ink)
            Spacer(minLength: 0)
            Button(action: onShowInfo) {
                Image(systemName: "info.circle")
                    .font(.system(size: 17))
                    .foregroundStyle(Theme.ink.opacity(0.35))
            }
            .accessibilityLabel("About this estimate")
        }
    }

    private func bigValue(grams: Double) -> some View {
        let mass = AwareFormat.mass(grams: grams)
        return HStack(alignment: .firstTextBaseline, spacing: 7) {
            Text(mass.value).displayNumber(46).contentTransition(.numericText())
            Text(mass.unit).font(.system(size: 20, weight: .semibold)).foregroundStyle(Theme.ink.opacity(0.6))
        }
    }

    private func captionChip(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 13, weight: .semibold))
            .foregroundStyle(Theme.ink.opacity(0.55))
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(Capsule().fill(Theme.ink.opacity(0.06)))
    }
}

/// Explains where a CO₂e figure comes from, or why there isn't one.
struct ImpactInfoSheet: View {
    let label: CanonicalLabel
    let isRecycled: Bool
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if !isRecycled {
                        Text("This item goes in other waste, so recycling it saves nothing here.")
                            .font(.headline)
                    }
                    Text(ImpactFactors.explanation(for: label))
                    VStack(alignment: .leading, spacing: 8) {
                        Text("How it's worked out").font(.headline)
                        Text("The figure is the greenhouse gas avoided by recycling the item instead of sending it to landfill, using factors from the US EPA's Waste Reduction Model (WARM, version 16, December 2023).")
                        Text("The factors are US averages, so the real saving in Hanoi may differ. The number also assumes the item actually gets recycled.")
                    }
                    Link(destination: URL(string: "https://www.epa.gov/waste-reduction-model")!) {
                        Label("EPA Waste Reduction Model", systemImage: "arrow.up.right.square")
                    }
                    .font(.subheadline.weight(.semibold))
                    Text("Impact factors \(ImpactFactors.recordVersion)")
                        .font(.caption.monospaced())
                        .foregroundStyle(.secondary)
                }
                .font(.subheadline)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(20)
            }
            .navigationTitle("About this estimate")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
        .tint(Theme.green)
        .presentationDetents([.medium, .large])
        .lightSheetAppearance()
    }
}

#Preview {
    ScrollView {
        VStack(spacing: 14) {
            ImpactCard(label: .plasticBottle, isRecycled: true) {}
            ImpactCard(label: .glassContainer, isRecycled: true) {}
            ImpactCard(label: .disposableCup, isRecycled: true) {}
            ImpactCard(label: .plasticBag, isRecycled: false) {}
        }
        .padding()
    }
    .background(Theme.page)
}
