import Foundation

// DEMO ONLY: remove this file once Home has a real implementation.
//
// Home's cards show fixed demo figures (see HomeCards.swift). So that a live
// demo can show a scan landing on Home, these helpers add the scans that
// earned points this session (`RewardLedger.awards`) on top of those figures.
// Nothing is saved, so it all resets on relaunch. The real implementation
// should store each scan and compute Home's figures from that history
// instead. Every place that uses this is marked "DEMO ONLY".
enum DemoSessionStats {
    /// Grams of material the session's recycled items kept out of other waste.
    static func wasteSavedGrams(_ awards: [AwardedScan]) -> Double {
        recycledLabels(awards).map(massGrams(of:)).reduce(0, +)
    }

    /// Grams of CO₂e the session's recycled items avoided, from `ImpactFactors`.
    static func co2SavedGrams(_ awards: [AwardedScan]) -> Double {
        recycledLabels(awards).map(co2Grams(of:)).reduce(0, +)
    }

    /// The session's scans per material, for "Items Scanned".
    static func itemCounts(_ awards: [AwardedScan]) -> [MaterialTag: Int] {
        awards.compactMap(\.label).reduce(into: [:]) { counts, label in
            counts[material(of: label), default: 0] += 1
        }
    }

    private static func recycledLabels(_ awards: [AwardedScan]) -> [CanonicalLabel] {
        awards.filter { $0.group == .recyclable }.compactMap(\.label)
    }

    private static func material(of label: CanonicalLabel) -> MaterialTag {
        switch label {
        // Most disposable cups here are plastic.
        case .plasticBottle, .plasticBag, .disposableCup, .styrofoam: .plastic
        case .cardboard: .paper
        case .glassContainer: .glass
        case .metalCan: .metal
        }
    }

    /// Weight of one item: the weights `ImpactFactors` assumes, or the
    /// default size where it asks for one.
    private static func massGrams(of label: CanonicalLabel) -> Double {
        switch label {
        case .plasticBottle: 10
        case .metalCan: 13
        case .disposableCup: 12  // A rough guess; ImpactFactors has no figure.
        case .plasticBag, .styrofoam: 0  // Never recycled in Hanoi, so never counted.
        case .glassContainer, .cardboard: defaultSize(of: label)?.massGrams ?? 0
        }
    }

    private static func co2Grams(of label: CanonicalLabel) -> Double {
        switch ImpactFactors.estimate(for: label) {
        case .perItem(let grams, _):
            grams
        case .perKilogram(let gramsPerKilogram, _, _):
            gramsPerKilogram * (defaultSize(of: label)?.massGrams ?? 0) / 1000
        case .unavailable:
            0
        }
    }

    private static func defaultSize(of label: CanonicalLabel) -> ItemSize? {
        guard case .perKilogram(_, let sizes, let defaultSizeID) = ImpactFactors.estimate(for: label) else { return nil }
        return sizes.first { $0.id == defaultSizeID }
    }
}
