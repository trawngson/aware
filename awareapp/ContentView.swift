//
//  ContentView.swift
//  awareapp
//
//  Created by Nguyen Truong Son on 16/2/26.
//

import SwiftUI

enum AppTab: Int {
    case home = 0
    case scan = 1
    case gallery = 2
}

struct ContentView: View {
    @ObservedObject private var navigationManager = NavigationManager.shared
    @AppStorage("hasSeenOnboarding") private var hasSeenOnboarding = false
    /// The device's Light/Dark setting; the tabs below override it for their content.
    @Environment(\.colorScheme) private var deviceColorScheme

    var body: some View {
        // Screens open on the dark forest (or the camera), so their content and
        // navigation bars use the dark appearance. On iOS 27 the tab bar takes
        // its appearance from the screen under it: dark over the forest, light
        // over the always-light map, in either device setting.
        TabView(selection: $navigationManager.selectedTab) {
            HomeTabView()
                .environment(\.colorScheme, .dark)
                // In Dark mode the tab bar stays dark over the map too.
                .toolbarColorScheme(navigationManager.usesLightChrome && deviceColorScheme == .dark ? .dark : nil,
                                    for: .tabBar)
                .tabItem { Label("Home", systemImage: "house.fill") }
                .tag(AppTab.home)
            ScanTabView(isTabActive: navigationManager.selectedTab == .scan)
                .environment(\.colorScheme, .dark)
                .tabItem { Label("Scan", systemImage: "camera.fill") }
                .tag(AppTab.scan)
            GalleryTabView()
                .environment(\.colorScheme, .dark)
                .tabItem { Label("Gallery", systemImage: "photo.fill") }
                .tag(AppTab.gallery)
        }
        .tint(Theme.green)
        .fullScreenCover(isPresented: Binding(
            get: { !hasSeenOnboarding },
            set: { hasSeenOnboarding = !$0 }
        )) {
            OnboardingView()
        }
    }
}

#Preview {
    UserDefaults.standard.set(false, forKey: "hasSeenOnboarding")
    return ContentView()
}
