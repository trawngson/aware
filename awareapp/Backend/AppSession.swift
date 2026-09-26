import Combine
import Foundation
import Network
import Supabase
import SwiftUI

/// The app's link to the community backend: who is signed in, the server
/// settings, and keeping the phone's scans in sync.
///
/// With no backend configured (`BackendConfig.plist` empty) it does nothing:
/// no sign-in, no network, samples always show, and the user is the demo's
/// "Truong Son". With a backend, the phone signs in as a guest on first launch
/// without asking anything, and everything keeps working offline.
@MainActor
final class AppSession: ObservableObject {
    static let shared = AppSession()

    let backend: CommunityBackend

    /// The user's profile, cached from the last fetch.
    @Published private(set) var profile: RemoteProfile?
    /// Server settings, cached from the last fetch.
    @Published private(set) var settings: RemoteSettings?
    /// False after a sync failed because the server couldn't be reached.
    @Published private(set) var isOnline = true

    private let defaults: UserDefaults
    private let ledger: RewardLedger
    private lazy var scanSync = ScanSync(backend: backend, queue: ledger)
    private var monitor: NWPathMonitor?
    private var isStarted = false
    private var isRefreshing = false
    private var needsAnotherRefresh = false
    private var hasRestoredHistory = false

    private enum Keys {
        static let settings = "community.settings.v1"
        static let profile = "community.profile.v1"
    }

    init(backend: CommunityBackend? = nil, defaults: UserDefaults = .standard, ledger: RewardLedger? = nil) {
        self.defaults = defaults
        self.ledger = ledger ?? .shared
        if let backend {
            self.backend = backend
        } else if let config = BackendConfig.load(defaults: defaults) {
            self.backend = SupabaseBackend(config: config, authStorage: KeychainLocalStorage())
        } else {
            self.backend = NoBackend()
        }
        if self.backend.isConfigured {
            settings = Self.cached(RemoteSettings.self, key: Keys.settings, in: defaults)
            profile = Self.cached(RemoteProfile.self, key: Keys.profile, in: defaults)
        }
    }

    var isBackendConfigured: Bool { backend.isConfigured }

    /// Whether the built-in sample people, posts and map spots show. Always on
    /// without a backend, or before the setting was ever fetched.
    var showSamples: Bool {
        guard backend.isConfigured else { return true }
        return settings?.showSamples ?? true
    }

    /// The person using the app, as shown on Home, posts and rankings.
    var currentMember: CommunityMember {
        guard backend.isConfigured else { return Community.me }
        guard let profile else {
            let name = String(localized: "Recycler")
            return CommunityMember(id: backend.currentUserID?.uuidString.lowercased() ?? "me", name: name,
                                   shortName: name, points: 0,
                                   avatar: .initials("R", top: Color(hex: 0x34A862), bottom: Color(hex: 0x1C7442)))
        }
        return CommunityMember(profile: profile)
    }

    // MARK: - Lifecycle

    /// Call once at launch. Starts watching the network and syncs.
    func start() {
        guard backend.isConfigured, !isStarted else { return }
        isStarted = true
        ledger.dailyCap = settings?.dailyPointCap ?? 200
        ledger.didRecordScan = { [weak self] in
            Task { await self?.refresh() }
        }
        let monitor = NWPathMonitor()
        monitor.pathUpdateHandler = { [weak self] path in
            guard path.status == .satisfied else { return }
            Task { @MainActor in await self?.refresh() }
        }
        monitor.start(queue: DispatchQueue(label: "AWARE.network"))
        self.monitor = monitor
        Task { await refresh() }
    }

    /// Signs in if needed, fetches settings and the profile, and sends
    /// pending scans. Safe to call often; overlapping calls are merged.
    func refresh() async {
        guard backend.isConfigured else { return }
        if isRefreshing {
            needsAnotherRefresh = true
            return
        }
        isRefreshing = true
        defer { isRefreshing = false }
        repeat {
            needsAnotherRefresh = false
            do {
                _ = try await backend.ensureSession()
                let settings = try await backend.fetchSettings()
                apply(settings)
                let profile = try await backend.fetchMyProfile()
                apply(profile)
                try await scanSync.pushPending()
                if !hasRestoredHistory {
                    try await scanSync.restoreHistory()
                    hasRestoredHistory = true
                }
                isOnline = true
                await LeaderboardStore.shared.refresh()
            } catch BackendError.unreachable {
                isOnline = false
            } catch {
                // Server trouble: keep what's cached and try again next time.
            }
        } while needsAnotherRefresh
    }

    /// Changes the user's display name.
    func rename(to name: String) async throws {
        let profile = try await backend.updateDisplayName(name)
        apply(profile)
    }

    // MARK: - Cache

    private func apply(_ settings: RemoteSettings) {
        self.settings = settings
        ledger.dailyCap = settings.dailyPointCap
        Self.store(settings, key: Keys.settings, in: defaults)
    }

    private func apply(_ profile: RemoteProfile) {
        self.profile = profile
        Self.store(profile, key: Keys.profile, in: defaults)
    }

    private static func cached<T: Decodable>(_ type: T.Type, key: String, in defaults: UserDefaults) -> T? {
        guard let data = defaults.data(forKey: key) else { return nil }
        return try? JSONDecoder().decode(T.self, from: data)
    }

    private static func store<T: Encodable>(_ value: T, key: String, in defaults: UserDefaults) {
        if let data = try? JSONEncoder().encode(value) {
            defaults.set(data, forKey: key)
        }
    }
}

extension CommunityMember {
    /// A real person on the leaderboard.
    init(row: LeaderboardRow) {
        self.init(
            id: row.userID.uuidString.lowercased(),
            name: row.displayName,
            shortName: row.displayName,
            points: row.points,
            avatar: .initials(row.avatarInitials,
                              top: Color(hex: UInt32(clamping: row.avatarTop)),
                              bottom: Color(hex: UInt32(clamping: row.avatarBottom)))
        )
    }

    /// A member drawn from a server profile: initials on their gradient.
    init(profile: RemoteProfile) {
        self.init(
            id: profile.id.uuidString.lowercased(),
            name: profile.displayName,
            shortName: profile.displayName,
            points: 0,
            avatar: .initials(profile.avatarInitials,
                              top: Color(hex: UInt32(clamping: profile.avatarTop)),
                              bottom: Color(hex: UInt32(clamping: profile.avatarBottom)))
        )
    }
}
