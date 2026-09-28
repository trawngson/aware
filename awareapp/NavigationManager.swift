import SwiftUI

/// Shared navigation manager for app-wide navigation events
@MainActor
class NavigationManager: ObservableObject {
    static let shared = NavigationManager()
    
    @Published var selectedTab: AppTab = .home
    /// True while a screen with a light top edge (the map, in Light mode) is
    /// showing, so the back buttons switch to dark.
    @Published var usesLightChrome = false

    /// Back-button and bar-item color for the tab navigation stacks.
    var chromeTint: Color { usesLightChrome ? Theme.ink : .white }
    
    private init() {}
    
    func switchToTab(_ tab: AppTab) {
        selectedTab = tab
    }
    
    func switchToGallery() {
        selectedTab = .gallery
    }
    
    func switchToScan() {
        selectedTab = .scan
    }
    
    func switchToHome() {
        selectedTab = .home
    }
}
