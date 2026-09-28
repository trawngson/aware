import SwiftUI

// MARK: - Glass surfaces

/// One translucent "liquid glass" surface recipe from the design: a white
/// gradient fill, an optional backdrop blur, a hairline border, a top inner
/// highlight, and a soft drop shadow.
///
/// The app's demo device (iPhone XR) tops out at iOS 18, so the look is built
/// from materials and gradients rather than the iOS 26 `glassEffect` API.
struct GlassStyle {
    var top: Double
    var bottom: Double
    var border: Double
    var highlight: Double
    var material: Material?
    var materialScheme: ColorScheme = .light
    var shadow: Color
    var shadowRadius: CGFloat
    var shadowY: CGFloat

    /// Content cards on the light "mist" part of a screen.
    static let card = GlassStyle(top: 0.78, bottom: 0.58, border: 0.8, highlight: 0.9, material: nil,
                                 shadow: Color(hex: 0x143A22, opacity: 0.10), shadowRadius: 13, shadowY: 10)
    /// Title card on scan results and post cards.
    static let cardStrong = GlassStyle(top: 0.84, bottom: 0.66, border: 0.85, highlight: 0.95, material: nil,
                                       shadow: Color(hex: 0x143A22, opacity: 0.12), shadowRadius: 15, shadowY: 12)
    /// Cards sitting directly on the sharp forest photo.
    static let frosted = GlassStyle(top: 0.26, bottom: 0.12, border: 0.4, highlight: 0.45, material: .ultraThinMaterial,
                                    materialScheme: .dark, shadow: Color(hex: 0x081C10, opacity: 0.24), shadowRadius: 16, shadowY: 12)
    /// Controls floating over the map or the keyboard.
    static let chrome = GlassStyle(top: 0.5, bottom: 0.3, border: 0.75, highlight: 0.9, material: .ultraThinMaterial,
                                   shadow: Color(hex: 0x081C10, opacity: 0.16), shadowRadius: 12, shadowY: 10)
    /// Rows on the dark scan screen.
    static let dark = GlassStyle(top: 0.12, bottom: 0.08, border: 0.24, highlight: 0.3, material: .ultraThinMaterial,
                                 materialScheme: .dark, shadow: .clear, shadowRadius: 0, shadowY: 0)
}

private struct GlassBackground<S: InsettableShape>: View {
    let style: GlassStyle
    let shape: S

    var body: some View {
        ZStack {
            if let material = style.material {
                shape.fill(material).environment(\.colorScheme, style.materialScheme)
            }
            shape.fill(LinearGradient(
                colors: [.white.opacity(style.top), .white.opacity(style.bottom)],
                startPoint: .top, endPoint: .bottom
            ))
        }
        .overlay(shape.strokeBorder(.white.opacity(style.border), lineWidth: 0.5))
        .overlay(
            shape.strokeBorder(
                LinearGradient(
                    stops: [.init(color: .white.opacity(style.highlight), location: 0),
                            .init(color: .white.opacity(0), location: 0.18)],
                    startPoint: .top, endPoint: .bottom
                ),
                lineWidth: 1
            )
        )
        .shadow(color: style.shadow, radius: style.shadowRadius, y: style.shadowY)
    }
}

extension View {
    func glass(_ style: GlassStyle = .card, cornerRadius: CGFloat = 24) -> some View {
        background(GlassBackground(style: style, shape: RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)))
    }

    func glassCapsule(_ style: GlassStyle) -> some View {
        background(GlassBackground(style: style, shape: Capsule()))
    }

    func glassCircle(_ style: GlassStyle) -> some View {
        background(GlassBackground(style: style, shape: Circle()))
    }
}

// MARK: - Forest backdrop

/// The shared screen background: the forest photo, a blurred copy that fades
/// in lower down, and a scrim that turns the bottom into a pale green "mist".
struct ForestBackdrop: View {
    /// Where the blurred copy starts and becomes fully opaque (0 = top).
    var blurFrom: Double = 0.24
    var blurTo: Double = 0.44
    var scrim: [Gradient.Stop] = ForestBackdrop.homeScrim

    var body: some View {
        Theme.forestDark
            .overlay {
                Image("ForestBackground")
                    .resizable()
                    .scaledToFill()
            }
            .overlay {
                Image("ForestBackground")
                    .resizable()
                    .scaledToFill()
                    .blur(radius: 24, opaque: true)
                    .saturation(1.15)
                    .mask(LinearGradient(
                        stops: [.init(color: .clear, location: blurFrom), .init(color: .black, location: blurTo)],
                        startPoint: .top, endPoint: .bottom
                    ))
            }
            .overlay {
                LinearGradient(stops: scrim, startPoint: .top, endPoint: .bottom)
            }
            .clipped()
            .ignoresSafeArea()
            .accessibilityHidden(true)
    }

    static func scrim(dark: Double, darkEnd: Double, mistStart: Double, mistMid: Double) -> [Gradient.Stop] {
        [
            .init(color: Theme.forestShade.opacity(dark), location: 0),
            .init(color: Theme.forestShade.opacity(0.26), location: darkEnd),
            .init(color: Theme.mist.opacity(0.56), location: mistStart),
            .init(color: Theme.mist.opacity(0.82), location: mistMid),
            .init(color: Theme.mist.opacity(0.86), location: 1),
        ]
    }

    static let homeScrim: [Gradient.Stop] = [
        .init(color: Theme.forestShade.opacity(0.5), location: 0),
        .init(color: Theme.forestShade.opacity(0.24), location: 0.17),
        .init(color: Theme.mist.opacity(0.5), location: 0.38),
        .init(color: Theme.mist.opacity(0.76), location: 0.56),
        .init(color: Theme.mist.opacity(0.8), location: 1),
    ]

    /// Pushed detail screens with a short dark header.
    static let detail = ForestBackdrop(blurFrom: 0.2, blurTo: 0.38,
                                       scrim: scrim(dark: 0.5, darkEnd: 0.16, mistStart: 0.34, mistMid: 0.52))
    /// Screens whose content starts right under the title (Gallery, thread).
    static let feed = ForestBackdrop(blurFrom: 0.14, blurTo: 0.3,
                                     scrim: scrim(dark: 0.5, darkEnd: 0.12, mistStart: 0.28, mistMid: 0.44))
}

// MARK: - Buttons

/// Gentle press feedback for glass controls.
struct PressableStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.97 : 1)
            .opacity(configuration.isPressed ? 0.85 : 1)
            .animation(.spring(response: 0.25, dampingFraction: 0.7), value: configuration.isPressed)
    }
}

/// Full-width green call to action ("Add to Gallery", "Submit correction").
struct PrimaryButtonStyle: ButtonStyle {
    var cornerRadius: CGFloat = 22
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 17, weight: .semibold))
            .tracking(-0.17)
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 17)
            .background(
                RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                    .fill(isEnabled ? AnyShapeStyle(Theme.primaryGradient) : AnyShapeStyle(Theme.stone))
                    .overlay(
                        RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                            .strokeBorder(LinearGradient(colors: [.white.opacity(0.35), .clear],
                                                         startPoint: .top, endPoint: .center), lineWidth: 1)
                    )
                    .shadow(color: Theme.green.opacity(isEnabled ? 0.32 : 0), radius: 12, y: 10)
            )
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
            .animation(.spring(response: 0.25, dampingFraction: 0.7), value: configuration.isPressed)
    }
}

/// Small green capsule ("Post", "Add").
struct PillButtonLabel: View {
    let title: LocalizedStringKey
    var fontSize: CGFloat = 14
    var horizontal: CGFloat = 16
    var vertical: CGFloat = 8
    var enabled = true

    var body: some View {
        Text(title)
            .font(.system(size: fontSize, weight: .semibold))
            .foregroundStyle(.white)
            .padding(.horizontal, horizontal)
            .padding(.vertical, vertical)
            .background(Capsule().fill(enabled ? AnyShapeStyle(Theme.primaryGradient) : AnyShapeStyle(Theme.stone.opacity(0.7))))
            .shadow(color: Theme.green.opacity(enabled ? 0.3 : 0), radius: 5, y: 4)
    }
}

// MARK: - Labels

/// Uppercase group label above a list card ("GUIDANCE", "SOURCES").
struct SectionLabel: View {
    let title: LocalizedStringKey

    var body: some View {
        Text(title)
            .textCase(.uppercase)
            .font(.system(size: 13, weight: .semibold))
            .tracking(0.26)
            .foregroundStyle(Theme.ink.opacity(0.5))
            .padding(.leading, 14)
            .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Small building blocks

/// Rounded square with a tinted SF Symbol ("icon tile").
struct IconTile: View {
    let systemImage: String
    var tint: Color = Theme.green
    var background: Color? = nil
    var size: CGFloat = 26
    var cornerRadius: CGFloat = 9
    var iconSize: CGFloat = 13

    var body: some View {
        Image(systemName: systemImage)
            .font(.system(size: iconSize, weight: .semibold))
            .foregroundStyle(tint)
            .frame(width: size, height: size)
            .background(RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                .fill(background ?? tint.opacity(0.13)))
    }
}

/// Header row of a Home card: icon tile, title, trailing caption, chevron.
struct CardHeader: View {
    let systemImage: String
    let title: LocalizedStringKey
    var tint: Color = Theme.green
    var caption: LocalizedStringKey? = nil
    var showsChevron = true
    var titleColor: Color = Theme.ink
    var captionColor: Color = Theme.ink.opacity(0.55)
    var tileBackground: Color? = nil

    var body: some View {
        HStack(spacing: 8) {
            IconTile(systemImage: systemImage, tint: tint, background: tileBackground)
            Text(title).cardTitleStyle(titleColor)
            Spacer(minLength: 4)
            if let caption {
                Text(caption).font(.system(size: 13)).foregroundStyle(captionColor)
            }
            if showsChevron {
                Image(systemName: "chevron.right")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(Theme.ink.opacity(0.3))
            }
        }
    }
}

/// A number followed by the leaf-points glyph.
struct LeafAmount: View {
    let value: Int
    var size: CGFloat = 14
    var weight: Font.Weight = .regular
    var color: Color = Theme.ink.opacity(0.6)
    var leafColor: Color = Theme.green
    var leafScale: CGFloat = 1

    var body: some View {
        HStack(spacing: 3) {
            Text(AwareFormat.grouped(value))
                .font(.system(size: size, weight: weight))
                .foregroundStyle(color)
            Image(systemName: "leaf.fill")
                .font(.system(size: size * 0.86 * leafScale, weight: .semibold))
                .foregroundStyle(leafColor)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Text("\(AwareFormat.grouped(value)) leaves"))
    }
}

/// Tinted capsule with an arrow ("↑ 12% today").
struct TrendPill: View {
    let systemImage: String
    let text: String
    var tint: Color = Theme.green
    var fontSize: CGFloat = 12

    var body: some View {
        HStack(spacing: 2) {
            Image(systemName: systemImage).font(.system(size: fontSize - 1, weight: .bold))
            Text(text).font(.system(size: fontSize, weight: .semibold))
        }
        .foregroundStyle(tint)
        .padding(.horizontal, 8)
        .padding(.vertical, 3)
        .background(Capsule().fill(tint.opacity(0.12)))
    }
}

// MARK: - Native navigation over the forest

extension View {
    /// Pushed screens keep the system navigation bar (native back button and
    /// title); only its colors are adapted to the dark forest header. The tab bar
    /// stays visible, as the HIG asks and stock apps do.
    func forestNavigationBar(_ title: LocalizedStringKey) -> some View {
        navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbarColorScheme(.dark, for: .navigationBar)
    }

    /// Light sheets presented from the tabs. The tabs pass a dark environment
    /// down (see `ContentView`), which `preferredColorScheme` alone doesn't undo.
    func lightSheetAppearance() -> some View {
        environment(\.colorScheme, .light)
            .preferredColorScheme(.light)
    }
}
