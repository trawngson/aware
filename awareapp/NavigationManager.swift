import SwiftUI

/// Shared navigation manager for app-wide navigation events
@MainActor
class NavigationManager: ObservableObject {
    static let shared = NavigationManager()
    
    @Published var selectedTab: AppTab = .home
    
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
