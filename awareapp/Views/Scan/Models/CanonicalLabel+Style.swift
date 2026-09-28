import SwiftUI

/// Display-only helpers for the canonical labels (tags, colors, wording).
extension CanonicalLabel {
    /// Main material, shown as a tag on the results screen.
    var materialName: String {
        switch self {
        case .plasticBottle, .plasticBag: String(localized: "Plastic")
        case .glassContainer: String(localized: "Glass")
        case .metalCan: String(localized: "Metal")
        case .cardboard: String(localized: "Paper")
        case .disposableCup: String(localized: "Mixed material")
        case .styrofoam: String(localized: "Foam")
        }
    }

    var tint: Color {
        switch self {
        case .plasticBottle: Theme.green
        case .glassContainer: Theme.cyanDeep
        case .metalCan: Theme.orangeDeep
        case .cardboard: Theme.blue
        case .plasticBag: Theme.purple
        case .disposableCup: Theme.amber
        case .styrofoam: Theme.slate
        }
    }

    /// Text color for the material tag (a darker shade where needed).
    var tagTextColor: Color {
        switch self {
        case .glassContainer: Theme.cyanText
        default: tint
        }
    }

    /// Short name for comparison bars.
    var shortName: String {
        switch self {
        case .plasticBottle: String(localized: "Bottle")
        case .glassContainer: String(localized: "Glass")
        case .metalCan: String(localized: "Alu can")
        case .cardboard: String(localized: "Box")
        case .plasticBag: String(localized: "Bag")
        case .disposableCup: String(localized: "Cup")
        case .styrofoam: String(localized: "Foam")
        }
    }

    /// Title of the steps card, e.g. "How to recycle this bottle".
    func stepsTitle(recyclable: Bool) -> String {
        switch (self, recyclable) {
        case (.plasticBottle, true): String(localized: "How to recycle this bottle")
        case (.plasticBottle, false): String(localized: "How to dispose of this bottle")
        case (.glassContainer, true): String(localized: "How to recycle this glass")
        case (.glassContainer, false): String(localized: "How to dispose of this glass")
        case (.metalCan, true): String(localized: "How to recycle this can")
        case (.metalCan, false): String(localized: "How to dispose of this can")
        case (.cardboard, true): String(localized: "How to recycle this cardboard")
        case (.cardboard, false): String(localized: "How to dispose of this cardboard")
        case (.plasticBag, true): String(localized: "How to recycle this bag")
        case (.plasticBag, false): String(localized: "How to dispose of this bag")
        case (.disposableCup, true): String(localized: "How to recycle this cup")
        case (.disposableCup, false): String(localized: "How to dispose of this cup")
        case (.styrofoam, true): String(localized: "How to recycle this foam")
        case (.styrofoam, false): String(localized: "How to dispose of this foam")
        }
    }
}
