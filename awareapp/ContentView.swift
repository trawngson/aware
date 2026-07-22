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

    var body: some View {
        TabView(selection: $navigationManager.selectedTab) {
            HomeTabView()
                .tabItem { Label("Home", systemImage: "house.fill") }
                .tag(AppTab.home)
            ScanTabView(isTabActive: navigationManager.selectedTab == .scan)
                .tabItem { Label("Scan", systemImage: "camera.fill") }
                .tag(AppTab.scan)
            GalleryTabView()
                .tabItem { Label("Gallery", systemImage: "photo.fill") }
                .tag(AppTab.gallery)
        }
        .sheet(isPresented: Binding(
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
