import Foundation

// MARK: - CO₂e impact factors

/// A typical item size for classes that only have a per-kilogram factor.
struct ItemSize: Identifiable, Equatable {
    let id: String
    let name: String
    let massGrams: Double
}

/// What the app can honestly say about the emissions avoided by recycling an
/// item instead of landfilling it.
enum ImpactEstimate: Equatable {
    /// One defensible value per item, with its published range if there is one.
    case perItem(grams: Double, range: ClosedRange<Double>?)
    /// Only a per-kilogram factor; the user picks the closest item size.
    case perKilogram(gramsPerKilogram: Double, sizes: [ItemSize], defaultSizeID: String)
    /// No sourceable figure for this class.
    case unavailable
}

/// Mirror of backend/records/impact-factors-v1.yaml (EPA WARM v16,
/// December 2023): avoided = (landfilling - recycling) factor x item mass.
///
/// Kept apart from the detector, the policy table and the reward layer. The
/// figure only applies when the policy sends the item to recycling.
enum ImpactFactors {
    static let recordVersion = "impact-factors-v1"

    static func estimate(for label: CanonicalLabel) -> ImpactEstimate {
        switch label {
        case .plasticBottle:
            // 500 mL PET bottle, 10 g (9.9-12.7 g) x 1.17 kg CO2e/kg.
            .perItem(grams: 12, range: 12...15)
        case .metalCan:
            // Aluminium drink can, 12.99 g x 10.09 kg CO2e/kg; 102 g from the
            // Aluminum Association recycling-rate sensitivity.
            .perItem(grams: 131, range: 102...131)
        case .plasticBag:
            // HDPE carrier bag, 8.12 g x 0.86 kg CO2e/kg. No published range.
            .perItem(grams: 7, range: nil)
        case .glassContainer:
            .perKilogram(gramsPerKilogram: 330, sizes: [
                ItemSize(id: "beer", name: String(localized: "Beer"), massGrams: 200),
                ItemSize(id: "jar", name: String(localized: "Jar"), massGrams: 350),
                ItemSize(id: "wine", name: String(localized: "Wine"), massGrams: 500),
            ], defaultSizeID: "jar")
        case .cardboard:
            .perKilogram(gramsPerKilogram: 3_660, sizes: [
                ItemSize(id: "small", name: String(localized: "Small box"), massGrams: 200),
                ItemSize(id: "medium", name: String(localized: "Medium box"), massGrams: 500),
                ItemSize(id: "large", name: String(localized: "Large box"), massGrams: 1_000),
            ], defaultSizeID: "small")
        case .disposableCup, .styrofoam:
            .unavailable
        }
    }

    /// The three classes with a per-item value, for the comparison bars.
    static let perItemReference: [(label: CanonicalLabel, grams: Double)] = [
        (.plasticBag, 7),
        (.plasticBottle, 12),
        (.metalCan, 131),
    ]

    /// Why a class has no figure, or what its figure assumes.
    static func explanation(for label: CanonicalLabel) -> String {
        switch label {
        case .plasticBottle:
            String(localized: "Based on a 500 mL PET water bottle weighing about 10 g.")
        case .metalCan:
            String(localized: "Based on an aluminium drink can weighing about 13 g. Steel food tins save less, and the scanner can't tell the two apart.")
        case .plasticBag:
            String(localized: "Based on a light supermarket carrier bag weighing about 8 g. This is the least certain of the per-item figures.")
        case .glassContainer:
            String(localized: "Glass saves about 0.33 kg CO₂e per kg recycled. Bottles and jars range from about 200 g to 500 g, so pick the closest size.")
        case .cardboard:
            String(localized: "Cardboard saves about 3.66 kg CO₂e per kg recycled. Boxes range from about 200 g to over 1 kg, so pick the closest size.")
        case .disposableCup:
            String(localized: "Cups can be paper, plastic, or foam, and published footprints for paper cups alone differ by 20 times, so there is no fair single number.")
        case .styrofoam:
            String(localized: "There is no published recycling factor for polystyrene foam, and foam items vary too much in weight.")
        }
    }
}
