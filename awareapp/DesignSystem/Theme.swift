import SwiftUI

// MARK: - Color tokens (from the "AWARE Liquid Glass" design)

extension Color {
    init(hex: UInt32, opacity: Double = 1) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: opacity
        )
    }
}

enum Theme {
    // Text and surfaces
    static let ink = Color(hex: 0x11291C)
    static let inkOnWhite = Color(hex: 0x0D2E1B)
    static let page = Color(hex: 0xEDF1EA)
    static let mist = Color(hex: 0xEAF0E8)
    static let forestShade = Color(hex: 0x07140D)
    static let forestDark = Color(hex: 0x0C1F14)
    static let scanDark = Color(hex: 0x0B1A11)
    static let scanShade = Color(hex: 0x06120B)

    // Brand greens
    static let green = Color(hex: 0x1F7A46)
    static let greenMid = Color(hex: 0x2E9E5B)
    static let greenBright = Color(hex: 0x34A862)
    static let greenDeep = Color(hex: 0x1C7442)
    static let mint = Color(hex: 0xBFF0CF)
    static let detectionGreen = Color(hex: 0x5BD98A)
    static let detectionYellow = Color(hex: 0xF2C94C)

    // Accents
    static let teal = Color(hex: 0x0E7C86)
    static let amber = Color(hex: 0xA66A00)
    static let orange = Color(hex: 0xE08C33)
    static let orangeDeep = Color(hex: 0xC47418)
    static let blue = Color(hex: 0x3E86C9)
    static let cyan = Color(hex: 0x4CBFD0)
    static let cyanDeep = Color(hex: 0x2C93A3)
    static let cyanText = Color(hex: 0x12717E)
    static let purple = Color(hex: 0x7B5BC4)
    static let gold = Color(hex: 0xC8901F)
    static let red = Color(hex: 0xB4462F)
    static let heart = Color(hex: 0xC7433A)
    static let slate = Color(hex: 0x5A6560)
    static let stone = Color(hex: 0x9AA69E)

    /// Filled buttons and the "+points" pill.
    static let primaryGradient = LinearGradient(
        colors: [greenMid, green], startPoint: .top, endPoint: .bottom
    )
    /// Selected tab, cluster bubbles, active chips.
    static let activeGradient = LinearGradient(
        colors: [greenBright, greenDeep], startPoint: .top, endPoint: .bottom
    )
    static let progressGradient = LinearGradient(
        colors: [greenMid, green], startPoint: .leading, endPoint: .trailing
    )
}

// MARK: - Typography helpers

extension View {
    /// Card titles: 15pt semibold, tight tracking.
    func cardTitleStyle(_ color: Color = Theme.ink) -> some View {
        font(.system(size: 15, weight: .semibold)).tracking(-0.15).foregroundStyle(color)
    }

    /// Big display numbers.
    func displayNumber(_ size: CGFloat, color: Color = Theme.ink) -> some View {
        font(.system(size: size, weight: .bold)).tracking(-size * 0.035).foregroundStyle(color)
    }
}

// MARK: - Number formatting

enum AwareFormat {
    static func grouped(_ value: Int) -> String {
        value.formatted(.number.grouping(.automatic))
    }

    /// Grams, switching to kilograms from 1 kg: "12 g", "1.8 kg".
    static func mass(grams: Double) -> (value: String, unit: String) {
        if grams >= 1000 {
            return ((grams / 1000).formatted(.number.precision(.fractionLength(1))), "kg")
        }
        return (grouped(Int(grams.rounded())), "g")
    }
}
