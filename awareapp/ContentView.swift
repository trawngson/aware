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
        // navigation bars use the dark appearance. On iOS 26+ the Liquid Glass
        // tab bar isn't styled here: it takes its Light/Dark style from what is
        // under it. Over a scroll view it matches the scroll view's appearance,
        // so the scrolling screens use `TabScrollView`, which keeps the scroll
        // view in the device's setting (passed down as `deviceColorScheme`).
        // Elsewhere the bar follows the device's setting. It stays unforced
        // because forcing its style turns the selected tab white instead of green.
        TabView(selection: $navigationManager.selectedTab) {
            HomeTabView()
                .environment(\.colorScheme, .dark)
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
        .environment(\.deviceColorScheme, deviceColorScheme)
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
