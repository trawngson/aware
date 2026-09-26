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
        .environment(\.colorScheme, deviceColorScheme ?? colorScheme)
    }
}
