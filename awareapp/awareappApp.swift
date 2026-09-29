//
//  awareappApp.swift
//  awareapp
//
//  Created by Nguyen Truong Son on 16/2/26.
//

import SwiftUI

@main
struct awareappApp: App {
    init() {
        // UI tests launch with this to start at onboarding. It resets the saved
        // flag rather than overriding it (as `-hasSeenOnboarding NO` would), so
        // "Got it!" can still close onboarding.
        if ProcessInfo.processInfo.arguments.contains("-AWAREShowOnboarding") {
            UserDefaults.standard.set(false, forKey: "hasSeenOnboarding")
        }
    }

    var body: some Scene {
        WindowGroup {
            if DeviceBenchmarkSettings.isRequested {
                DeviceBenchmarkView()
            } else {
                ContentView()
            }
        }
    }
}
