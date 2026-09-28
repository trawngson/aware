import SwiftUI

private struct DeviceColorSchemeKey: EnvironmentKey {
    static let defaultValue: ColorScheme? = nil
}

extension EnvironmentValues {
    /// The device's Light/Dark setting. The tabs override `colorScheme` for
    /// their dark content, so `ContentView` also passes the setting down here.
    /// `nil` outside the tabs, e.g. in previews.
    var deviceColorScheme: ColorScheme? {
        get { self[DeviceColorSchemeKey.self] }
        set { self[DeviceColorSchemeKey.self] = newValue }
    }
}

/// A vertical scroll view for screens whose content scrolls under the tab bar.
/// On iOS 26+ the tab bar takes its Light/Dark style from the scroll view under
/// it, so the scroll view itself gets the device's setting, while its content
/// keeps the appearance around it (dark on the forest screens).
///
/// Built with the iOS 26 SDK, the bar instead takes the content's (dark) style
/// through the bottom scroll edge effect whenever content scrolls under it, so
/// that effect is hidden and the bar follows the device there too.
struct TabScrollView<Content: View>: View {
    private let content: Content
    @Environment(\.colorScheme) private var colorScheme
    @Environment(\.deviceColorScheme) private var deviceColorScheme

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        ScrollView {
            content
                .environment(\.colorScheme, colorScheme)
        }
        .hidingBottomScrollEdgeEffect()
        .environment(\.colorScheme, deviceColorScheme ?? colorScheme)
    }
}

private extension View {
    @ViewBuilder
    func hidingBottomScrollEdgeEffect() -> some View {
        if #available(iOS 26, *) {
            scrollEdgeEffectHidden(true, for: .bottom)
        } else {
            self
        }
    }
}
