import Foundation

// MARK: - Label Mappings

/// Display helpers for raw model labels. Only exact canonical labels
/// (see `CanonicalLabel`) get a localized name and icon; anything else is
/// shown as-is with a generic icon.
struct LabelMappings {
    static func formatLabel(_ label: String) -> String {
        CanonicalLabel(modelLabel: label)?.displayName
            ?? label.replacingOccurrences(of: "_", with: " ").capitalized
    }

    static func iconForLabel(_ label: String) -> String {
        CanonicalLabel(modelLabel: label)?.iconName ?? "questionmark.square.dashed"
    }
}
