import Foundation

enum BackendError: Error, Equatable {
    /// No backend is configured; the app runs on its own.
    case notConfigured
    /// The phone is offline or the server can't be reached. Try again later.
    case unreachable
    /// The server refused this request for good (bad input, not allowed).
    case rejected(String)
    /// Anything else the server reported. Try again later.
    case server(String)
}

/// Everything the app asks of the community backend. `SupabaseBackend` talks
/// to a Supabase project; `NoBackend` is used when none is configured.
protocol CommunityBackend: AnyObject, Sendable {
    /// False for `NoBackend`: nothing is signed in, synced or fetched.
    var isConfigured: Bool { get }

    /// The signed-in user's id from the stored session, if there is one.
    var currentUserID: UUID? { get }

    /// Makes sure there is a session, signing in as a guest when the phone has
    /// never signed in. Returns the user's id.
    func ensureSession() async throws -> UUID

    func fetchSettings() async throws -> RemoteSettings
    func fetchMyProfile() async throws -> RemoteProfile
    func updateDisplayName(_ name: String) async throws -> RemoteProfile

    /// Records a scan event and returns the points the server awarded.
    func awardScan(_ request: ScanAwardRequest) async throws -> ScanAwardResponse
    /// The user's own scan events, newest first.
    func fetchMyScanEvents(limit: Int) async throws -> [RemoteScanEvent]

    func fetchLeaderboard(period: LeaderboardPeriod, limit: Int) async throws -> [LeaderboardRow]
}

/// The backend used when none is configured. Every call fails with
/// `notConfigured`, and callers check `isConfigured` before calling at all.
final class NoBackend: CommunityBackend {
    var isConfigured: Bool { false }
    var currentUserID: UUID? { nil }

    func ensureSession() async throws -> UUID { throw BackendError.notConfigured }
    func fetchSettings() async throws -> RemoteSettings { throw BackendError.notConfigured }
    func fetchMyProfile() async throws -> RemoteProfile { throw BackendError.notConfigured }
    func updateDisplayName(_ name: String) async throws -> RemoteProfile { throw BackendError.notConfigured }
    func awardScan(_ request: ScanAwardRequest) async throws -> ScanAwardResponse { throw BackendError.notConfigured }
    func fetchMyScanEvents(limit: Int) async throws -> [RemoteScanEvent] { throw BackendError.notConfigured }
    func fetchLeaderboard(period: LeaderboardPeriod, limit: Int) async throws -> [LeaderboardRow] {
        throw BackendError.notConfigured
    }
}
