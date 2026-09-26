import SwiftUI
import UserNotifications

/// Everything behind the Notifications switch in More: push notifications for
/// replies, likes and announcements (with a backend), and the weekly-goal and
/// streak reminders the phone schedules itself.
///
/// Permission is asked only when the user turns the switch on. Turning it
/// off cancels the reminders and tells the server to stop sending pushes.
@MainActor
final class NotificationManager: ObservableObject {
    static let shared = NotificationManager()

    /// The switch's value (its key predates this class).
    nonisolated static let enabledKey = "notificationsEnabled"

    private let center = UNUserNotificationCenter.current()
    private let defaults = UserDefaults.standard
    private var pendingToken: String?

    private static let tokenKey = "notifications.deviceToken"
    private static let streakID = "reminder.streak"
    private static let weeklyID = "reminder.weeklyGoal"

    var isEnabled: Bool { defaults.object(forKey: Self.enabledKey) as? Bool ?? true }

    /// Called when the user turns the switch on. Returns false when the user
    /// (now or earlier) declined notifications for AWARE.
    func enable() async -> Bool {
        let granted = (try? await center.requestAuthorization(options: [.alert, .sound, .badge])) ?? false
        guard granted else { return false }
        await refresh()
        return true
    }

    /// Called when the user turns the switch off.
    func disable() async {
        center.removePendingNotificationRequests(withIdentifiers: [Self.streakID, Self.weeklyID])
        UIApplication.shared.unregisterForRemoteNotifications()
        if let token = defaults.string(forKey: Self.tokenKey) {
            try? await AppSession.shared.backend.unregisterDevice(token: token)
            defaults.removeObject(forKey: Self.tokenKey)
        }
    }

    /// After the account was deleted: its tokens went with it, so register
    /// this phone again for the new guest.
    func forgetToken() async {
        defaults.removeObject(forKey: Self.tokenKey)
        pendingToken = nil
        await refresh()
    }

    /// At launch and when the app comes back: keeps the reminders current and
    /// the push registration fresh, only if the user allowed notifications.
    func refresh() async {
        guard isEnabled else { return }
        let settings = await center.notificationSettings()
        guard settings.authorizationStatus == .authorized || settings.authorizationStatus == .provisional else { return }
        await scheduleReminders()
        if AppSession.shared.isBackendConfigured {
            UIApplication.shared.registerForRemoteNotifications()
        }
    }

    /// APNs gave the phone a token: register it for this user.
    func didRegister(deviceToken: Data) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()
        pendingToken = token
        Task { await uploadToken() }
    }

    /// Sends the token after sign-in (it may arrive before the session).
    func uploadToken() async {
        guard let token = pendingToken, AppSession.shared.isBackendConfigured else { return }
        #if DEBUG
        let sandbox = true
        #else
        let sandbox = false
        #endif
        do {
            try await AppSession.shared.backend.registerDevice(token: token, sandbox: sandbox)
            defaults.set(token, forKey: Self.tokenKey)
            pendingToken = nil
        } catch {
            // Offline: try again on the next refresh.
        }
    }

    // MARK: - Reminders

    /// A streak reminder at 19:00 on the next day without a scan (today, if
    /// nothing is scanned yet), and a weekly goal nudge on Sundays at 18:00.
    private func scheduleReminders(now: Date = .now) async {
        center.removePendingNotificationRequests(withIdentifiers: [Self.streakID, Self.weeklyID])
        let calendar = Calendar.current
        let stats = PersonalStats(scans: RewardLedger.shared.scans, now: now)

        var day = calendar.startOfDay(for: now)
        if stats.today.scans > 0 || calendar.component(.hour, from: now) >= 19 {
            day = calendar.date(byAdding: .day, value: 1, to: day) ?? day
        }
        var streakTime = calendar.dateComponents([.year, .month, .day], from: day)
        streakTime.hour = 19
        let streak = UNMutableNotificationContent()
        streak.title = String(localized: "Keep your streak going 🔥")
        streak.body = stats.currentStreak > 0
            ? String(localized: "Scan one thing today to make it \(stats.currentStreak + 1) days in a row.")
            : String(localized: "Scan one thing today to start a recycling streak.")
        streak.sound = .default
        try? await center.add(UNNotificationRequest(
            identifier: Self.streakID, content: streak,
            trigger: UNCalendarNotificationTrigger(dateMatching: streakTime, repeats: false)))

        var sunday = DateComponents()
        sunday.weekday = 1
        sunday.hour = 18
        let weekly = UNMutableNotificationContent()
        weekly.title = String(localized: "How's your month going?")
        weekly.body = stats.pointsToGoal > 0
            ? String(localized: "You're \(stats.pointsToGoal) leaves away from this month's goal.")
            : String(localized: "You reached this month's goal. Nice work!")
        weekly.sound = .default
        try? await center.add(UNNotificationRequest(
            identifier: Self.weeklyID, content: weekly,
            trigger: UNCalendarNotificationTrigger(dateMatching: sunday, repeats: true)))
    }
}

/// Receives the APNs token and shows notifications while the app is open.
final class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        return true
    }

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        Task { @MainActor in NotificationManager.shared.didRegister(deviceToken: deviceToken) }
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        // Expected until the app has the Push Notifications capability (it
        // needs the paid Apple Developer Program); reminders still work.
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification)
        async -> UNNotificationPresentationOptions {
        [.banner, .sound]
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse) async {
        let kind = response.notification.request.content.userInfo["kind"] as? String
        await MainActor.run {
            switch kind {
            case "reply", "like", "announcement":
                NavigationManager.shared.switchToGallery()
            default:
                NavigationManager.shared.switchToHome()
            }
        }
    }
}
