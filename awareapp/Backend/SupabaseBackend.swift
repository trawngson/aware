import Foundation
import Supabase

/// `CommunityBackend` on a Supabase project, through the official
/// supabase-swift client. Row-level security on the server decides what each
/// call may read or change; this class only shapes the requests.
final class SupabaseBackend: CommunityBackend, @unchecked Sendable {
    let client: SupabaseClient

    /// `authStorage` keeps the session between launches (the Keychain in the
    /// app, memory in tests).
    init(config: BackendConfig, authStorage: any AuthLocalStorage) {
        client = SupabaseClient(
            supabaseURL: config.url,
            supabaseKey: config.anonKey,
            options: SupabaseClientOptions(
                auth: .init(storage: authStorage, autoRefreshToken: true,
                            emitLocalSessionAsInitialSession: true)
            )
        )
    }

    var isConfigured: Bool { true }

    var currentUserID: UUID? { client.auth.currentUser?.id }

    func ensureSession() async throws -> UUID {
        if client.auth.currentSession != nil {
            do {
                return try await client.auth.session.user.id
            } catch {
                // A network problem keeps the stored session for next time; only
                // a session the server no longer knows is replaced by a new guest.
                guard Self.isSessionGone(error) else { throw Self.map(error) }
                try? await client.auth.signOut(scope: .local)
            }
        }
        do {
            return try await client.auth.signInAnonymously().user.id
        } catch {
            throw Self.map(error)
        }
    }

    func fetchSettings() async throws -> RemoteSettings {
        try await run {
            try await client.from("app_settings")
                .select("show_samples, daily_point_cap, report_threshold")
                .single()
                .execute()
                .value
        }
    }

    func fetchMyProfile() async throws -> RemoteProfile {
        let userID = try await ensureSession()
        return try await run {
            try await client.from("profiles")
                .select(Self.profileColumns)
                .eq("id", value: userID)
                .single()
                .execute()
                .value
        }
    }

    func updateDisplayName(_ name: String) async throws -> RemoteProfile {
        let userID = try await ensureSession()
        return try await run {
            try await client.from("profiles")
                .update(["display_name": name])
                .eq("id", value: userID)
                .select(Self.profileColumns)
                .single()
                .execute()
                .value
        }
    }

    func awardScan(_ request: ScanAwardRequest) async throws -> ScanAwardResponse {
        _ = try await ensureSession()
        return try await run {
            try await client.rpc("award_scan", params: request)
                .execute()
                .value
        }
    }

    func fetchMyScanEvents(limit: Int) async throws -> [RemoteScanEvent] {
        let userID = try await ensureSession()
        return try await run {
            try await client.from("scan_events")
                .select("id, label, choice_id, policy_version, disposal_group, points_awarded, reward_state, reason_code, scanned_at")
                .eq("user_id", value: userID)
                .order("scanned_at", ascending: false)
                .limit(limit)
                .execute()
                .value
        }
    }

    func fetchLeaderboard(period: LeaderboardPeriod, limit: Int) async throws -> [LeaderboardRow] {
        _ = try await ensureSession()
        return try await run {
            try await client.rpc("leaderboard", params: LeaderboardParams(period: period.rawValue, limit: limit))
                .execute()
                .value
        }
    }

    // MARK: - Helpers

    private static let profileColumns =
        "id, display_name, avatar_initials, avatar_top, avatar_bottom, role, banned_at, terms_accepted_at"

    private struct LeaderboardParams: Encodable {
        let period: String
        let limit: Int

        enum CodingKeys: String, CodingKey {
            case period = "p_period"
            case limit = "p_limit"
        }
    }

    /// Runs a request and turns its failure into a `BackendError`.
    private func run<T>(_ body: () async throws -> T) async throws -> T {
        do {
            return try await body()
        } catch {
            throw Self.map(error)
        }
    }

    /// True when the stored session can never be used again.
    static func isSessionGone(_ error: Error) -> Bool {
        guard let error = error as? AuthError else { return false }
        return [.sessionNotFound, .refreshTokenNotFound, .userNotFound].contains(error.errorCode)
    }

    static func map(_ error: Error) -> BackendError {
        if let error = error as? BackendError { return error }
        if error is URLError { return .unreachable }
        if let error = error as? PostgrestError {
            // Invalid input, not allowed, or a broken rule: repeating won't help.
            let permanent: Set<String> = ["22023", "22P02", "23502", "23505", "23514", "42501", "P0001", "PGRST116"]
            if let code = error.code, permanent.contains(code) { return .rejected(error.message) }
            return .server(error.message)
        }
        if let error = error as? AuthError { return .server(error.localizedDescription) }
        if let error = error as? HTTPError {
            let status = error.response.statusCode
            return (400..<500).contains(status) && status != 408 && status != 429
                ? .rejected(error.localizedDescription) : .server(error.localizedDescription)
        }
        if error is DecodingError { return .server("Unexpected response") }
        return .server(error.localizedDescription)
    }
}
