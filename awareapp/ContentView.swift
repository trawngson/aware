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
    @ObservedObject private var messages = MessageCenter.shared
    @AppStorage("hasSeenOnboarding") private var hasSeenOnboarding = false
    /// The device's Light/Dark setting; the tabs below override it for their content.
    @Environment(\.colorScheme) private var deviceColorScheme
    @Environment(\.scenePhase) private var scenePhase

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
        // Signs in as a guest and syncs, only when a backend is configured.
        .task { AppSession.shared.start() }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active {
                Task {
                    await AppSession.shared.refresh()
                    // Reminders and push registration, only if the user allowed them.
                    await NotificationManager.shared.refresh()
                }
            }
        }
        // Gallery results (thanks for reporting, offline, not allowed), from any tab.
        .alert(messages.message?.title ?? "",
               isPresented: Binding(get: { messages.message != nil }, set: { if !$0 { messages.message = nil } }),
               presenting: messages.message) { _ in
            Button("OK") {}
        } message: { message in
            Text(message.text)
        }
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
