//
//  awareappApp.swift
//  awareapp
//
//  Created by Nguyen Truong Son on 16/2/26.
//

import SwiftUI

@main
struct awareappApp: App {
    /// Receives the push token and notification taps.
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate

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
