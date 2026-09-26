import Combine
import Foundation

/// Real rankings and community totals from the backend, cached for offline
/// use. Without a backend it stays empty, so only the sample people show.
@MainActor
final class LeaderboardStore: ObservableObject {
    static let shared = LeaderboardStore()

    /// How many real people to fetch per ranking.
    static let limit = 50

    @Published private(set) var monthRows: [LeaderboardRow] = []
    @Published private(set) var allTimeRows: [LeaderboardRow] = []
    @Published private(set) var communityStats: CommunityStats?

    private let backend: CommunityBackend
    private let defaults: UserDefaults
    private var isRefreshing = false

    private struct Cache: Codable {
        var month: [LeaderboardRow]
        var allTime: [LeaderboardRow]
        var stats: CommunityStats?
    }
    private static let cacheKey = "community.leaderboard.v1"

    init(backend: CommunityBackend? = nil, defaults: UserDefaults = .standard) {
        self.backend = backend ?? AppSession.shared.backend
        self.defaults = defaults
        if self.backend.isConfigured, let data = defaults.data(forKey: Self.cacheKey),
           let cache = try? JSONDecoder().decode(Cache.self, from: data) {
            monthRows = cache.month
            allTimeRows = cache.allTime
            communityStats = cache.stats
        }
    }

    func rows(for period: LeaderboardPeriod) -> [LeaderboardRow] {
        period == .month ? monthRows : allTimeRows
    }

    /// Fetches both rankings and the community totals. Keeps the cached ones
    /// when offline.
    func refresh() async {
        guard backend.isConfigured, !isRefreshing else { return }
        isRefreshing = true
        defer { isRefreshing = false }
        do {
            let month = try await backend.fetchLeaderboard(period: .month, limit: Self.limit)
            let allTime = try await backend.fetchLeaderboard(period: .all, limit: Self.limit)
            let stats = try await backend.fetchCommunityStats()
            monthRows = month
            allTimeRows = allTime
            communityStats = stats
            if let data = try? JSONEncoder().encode(Cache(month: month, allTime: allTime, stats: stats)) {
                defaults.set(data, forKey: Self.cacheKey)
            }
        } catch {
            // Offline or server trouble: the cached rankings stay.
        }
    }
}
