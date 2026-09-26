import SwiftUI
import UIKit

extension View {
    /// Keeps the enclosing window's tab bar in the device's Light/Dark setting,
    /// with a green selected tab in both. On iOS 27 the tab bar otherwise takes
    /// its appearance from the screen under it (dark over the forest, light over
    /// the map), and `toolbarColorScheme(_:for: .tabBar)` turns the selected tab
    /// white or black instead of green.
    func tabBarFollowsDevice(_ colorScheme: ColorScheme) -> some View {
        background(TabBarStyle(style: colorScheme == .dark ? .dark : .light))
    }
}

private struct TabBarStyle: UIViewRepresentable {
    let style: UIUserInterfaceStyle

    func makeUIView(context: Context) -> TabBarStyleView { TabBarStyleView() }

    func updateUIView(_ view: TabBarStyleView, context: Context) {
        view.style = style
        // The tab bar controller may join the window after this view does.
        DispatchQueue.main.async { view.apply() }
    }
}

private final class TabBarStyleView: UIView {
    var style: UIUserInterfaceStyle = .unspecified

    /// Green on light bars, mint on dark ones, like the unforced tab bar.
    private static let selectedColor = UIColor { traits in
        UIColor(traits.userInterfaceStyle == .dark ? Theme.mint : Theme.green)
    }

    override func didMoveToWindow() {
        super.didMoveToWindow()
        apply()
    }

    func apply() {
        guard style != .unspecified,
              let root = window?.rootViewController,
              let tabBar = Self.tabBarController(in: root)?.tabBar else { return }
        tabBar.overrideUserInterfaceStyle = style
        tabBar.tintColor = Self.selectedColor
        let appearance = tabBar.standardAppearance.copy()
        for layout in [appearance.stackedLayoutAppearance, appearance.inlineLayoutAppearance,
                       appearance.compactInlineLayoutAppearance] {
            layout.selected.iconColor = Self.selectedColor
            layout.selected.titleTextAttributes[.foregroundColor] = Self.selectedColor
        }
        tabBar.standardAppearance = appearance
        tabBar.scrollEdgeAppearance = appearance
    }

    private static func tabBarController(in controller: UIViewController) -> UITabBarController? {
        if let tabs = controller as? UITabBarController { return tabs }
        for child in controller.children {
            if let tabs = tabBarController(in: child) { return tabs }
        }
        return nil
    }
}
