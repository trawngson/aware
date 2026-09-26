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

    func fetchCommunityStats() async throws -> CommunityStats {
        _ = try await ensureSession()
        return try await run {
            try await client.rpc("community_stats")
                .execute()
                .value
        }
    }

    // MARK: - Gallery

    static let imageBucket = "post-images"

    func fetchFeed(before: Date?, limit: Int) async throws -> [RemotePost] {
        _ = try await ensureSession()
        return try await run {
            var query = client.from("posts")
                .select("\(RemotePost.columns), replies(\(RemoteReply.columns))")
            if let before {
                query = query.lt("created_at", value: before)
            }
            return try await query
                .order("created_at", ascending: false)
                .order("created_at", ascending: true, referencedTable: "replies")
                .limit(limit)
                .limit(2, referencedTable: "replies")
                .execute()
                .value
        }
    }

    func fetchReplies(postID: UUID) async throws -> [RemoteReply] {
        _ = try await ensureSession()
        return try await run {
            try await client.from("replies")
                .select(RemoteReply.columns)
                .eq("post_id", value: postID)
                .order("created_at", ascending: true)
                .execute()
                .value
        }
    }

    private struct PostRef: Decodable {
        let postID: UUID
        enum CodingKeys: String, CodingKey { case postID = "post_id" }
    }

    func fetchMyReactions() async throws -> (liked: Set<UUID>, saved: Set<UUID>) {
        let userID = try await ensureSession()
        return try await run {
            let liked: [PostRef] = try await client.from("likes").select("post_id")
                .eq("user_id", value: userID).limit(1_000).execute().value
            let saved: [PostRef] = try await client.from("saves").select("post_id")
                .eq("user_id", value: userID).limit(1_000).execute().value
            return (Set(liked.map(\.postID)), Set(saved.map(\.postID)))
        }
    }

    func setLiked(_ liked: Bool, postID: UUID) async throws {
        try await setReaction("likes", on: liked, postID: postID)
    }

    func setSaved(_ saved: Bool, postID: UUID) async throws {
        try await setReaction("saves", on: saved, postID: postID)
    }

    private func setReaction(_ table: String, on: Bool, postID: UUID) async throws {
        let userID = try await ensureSession()
        try await run {
            if on {
                // Already there is fine: the user tapped twice.
                try await client.from(table)
                    .upsert(["post_id": postID], onConflict: "post_id,user_id", returning: .minimal, ignoreDuplicates: true)
                    .execute()
            } else {
                try await client.from(table).delete()
                    .eq("post_id", value: postID).eq("user_id", value: userID)
                    .execute()
            }
        }
    }

    func acceptTerms() async throws -> Date {
        _ = try await ensureSession()
        return try await run {
            try await client.rpc("accept_terms").execute().value
        }
    }

    func uploadImage(_ jpeg: Data) async throws -> String {
        let userID = try await ensureSession()
        let path = "\(userID.uuidString.lowercased())/\(UUID().uuidString.lowercased()).jpg"
        return try await run {
            _ = try await client.storage.from(Self.imageBucket)
                .upload(path, data: jpeg, options: FileOptions(cacheControl: "31536000", contentType: "image/jpeg"))
            return path
        }
    }

    func createPost(_ draft: PostDraft) async throws -> RemotePost {
        _ = try await ensureSession()
        return try await run {
            try await client.from("posts")
                .insert(draft, returning: .representation)
                .select(RemotePost.columns)
                .single()
                .execute()
                .value
        }
    }

    private struct ReplyDraft: Encodable {
        let postID: UUID
        let body: String
        let imagePath: String?
        enum CodingKeys: String, CodingKey {
            case postID = "post_id"
            case body
            case imagePath = "image_path"
        }
    }

    func createReply(postID: UUID, body: String, imagePath: String?) async throws -> RemoteReply {
        _ = try await ensureSession()
        return try await run {
            try await client.from("replies")
                .insert(ReplyDraft(postID: postID, body: body, imagePath: imagePath), returning: .representation)
                .select(RemoteReply.columns)
                .single()
                .execute()
                .value
        }
    }

    private struct ImageRef: Decodable {
        let imagePath: String?
        enum CodingKeys: String, CodingKey { case imagePath = "image_path" }
    }

    func deletePost(_ post: RemotePost) async throws {
        _ = try await ensureSession()
        try await run {
            // Photos first: other people's reply photos can only be removed
            // while the post (and so its replies) still exists.
            let replies: [ImageRef] = try await client.from("replies").select("image_path")
                .eq("post_id", value: post.id).execute().value
            let paths = ([post.imagePath] + replies.map(\.imagePath)).compactMap { $0 }
            if !paths.isEmpty {
                _ = try? await client.storage.from(Self.imageBucket).remove(paths: paths)
            }
            try await client.from("posts").delete().eq("id", value: post.id).execute()
        }
    }

    func deleteReply(_ reply: RemoteReply) async throws {
        _ = try await ensureSession()
        try await run {
            try await client.from("replies").delete().eq("id", value: reply.id).execute()
            if let path = reply.imagePath {
                _ = try? await client.storage.from(Self.imageBucket).remove(paths: [path])
            }
        }
    }

    private struct ReportDraft: Encodable {
        let postID: UUID?
        let replyID: UUID?
        let reportedUserID: UUID?
        let reason: String?
        enum CodingKeys: String, CodingKey {
            case postID = "post_id"
            case replyID = "reply_id"
            case reportedUserID = "reported_user_id"
            case reason
        }
    }

    func report(_ target: ReportTarget, reason: String?) async throws {
        _ = try await ensureSession()
        let draft: ReportDraft
        switch target {
        case .post(let id): draft = ReportDraft(postID: id, replyID: nil, reportedUserID: nil, reason: reason)
        case .reply(let id): draft = ReportDraft(postID: nil, replyID: id, reportedUserID: nil, reason: reason)
        case .user(let id): draft = ReportDraft(postID: nil, replyID: nil, reportedUserID: id, reason: reason)
        }
        do {
            try await run {
                try await client.from("reports").insert(draft).execute()
            }
        } catch BackendError.rejected(let message) where message.contains("duplicate") {
            // Reported before: once is enough.
        }
    }

    func block(_ userID: UUID) async throws {
        _ = try await ensureSession()
        try await run {
            try await client.from("blocks")
                .upsert(["blocked_id": userID], onConflict: "blocker_id,blocked_id", returning: .minimal, ignoreDuplicates: true)
                .execute()
        }
    }

    func unblock(_ userID: UUID) async throws {
        let me = try await ensureSession()
        try await run {
            try await client.from("blocks").delete()
                .eq("blocker_id", value: me).eq("blocked_id", value: userID)
                .execute()
        }
    }

    private struct BlockRow: Decodable {
        let blocked: PostAuthor
    }

    func fetchBlockedUsers() async throws -> [PostAuthor] {
        let me = try await ensureSession()
        return try await run {
            let rows: [BlockRow] = try await client.from("blocks")
                .select("blocked:profiles!blocked_id(\(PostAuthor.columns))")
                .eq("blocker_id", value: me)
                .order("created_at", ascending: false)
                .execute()
                .value
            return rows.map(\.blocked)
        }
    }

    func imageURL(for path: String) -> URL? {
        try? client.storage.from(Self.imageBucket).getPublicURL(path: path)
    }

    // MARK: - Map

    private struct MapParams: Encodable {
        let minLatitude: Double
        let minLongitude: Double
        let maxLatitude: Double
        let maxLongitude: Double
        let material: String?
        enum CodingKeys: String, CodingKey {
            case minLatitude = "p_min_latitude"
            case minLongitude = "p_min_longitude"
            case maxLatitude = "p_max_latitude"
            case maxLongitude = "p_max_longitude"
            case material = "p_material"
        }
    }

    func fetchMapPosts(in bounds: MapBounds, material: String?) async throws -> [MapPost] {
        _ = try await ensureSession()
        let params = MapParams(minLatitude: bounds.minLatitude, minLongitude: bounds.minLongitude,
                               maxLatitude: bounds.maxLatitude, maxLongitude: bounds.maxLongitude,
                               material: material)
        return try await run {
            try await client.rpc("map_posts", params: params).execute().value
        }
    }

    private struct NearbyParams: Encodable {
        let latitude: Double
        let longitude: Double
        let radius: Double
        let material: String?
        enum CodingKeys: String, CodingKey {
            case latitude = "p_latitude"
            case longitude = "p_longitude"
            case radius = "p_radius_meters"
            case material = "p_material"
        }
    }

    func fetchNearbyCount(latitude: Double, longitude: Double, radius: Double, material: String?) async throws -> Int {
        _ = try await ensureSession()
        let params = NearbyParams(latitude: latitude, longitude: longitude, radius: radius, material: material)
        return try await run {
            try await client.rpc("nearby_count", params: params).execute().value
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
    @discardableResult
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
        if let error = error as? PostgrestError, error.message == "content_not_allowed" {
            return .contentNotAllowed
        }
        if let error = error as? StorageError {
            let status = Int(error.statusCode ?? "") ?? 0
            return (400..<500).contains(status) ? .rejected(error.message) : .server(error.message)
        }
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
