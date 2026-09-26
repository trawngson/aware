import Foundation

enum BackendError: Error, Equatable {
    /// No backend is configured; the app runs on its own.
    case notConfigured
    /// The phone is offline or the server can't be reached. Try again later.
    case unreachable
    /// The server refused this request for good (bad input, not allowed).
    case rejected(String)
    /// The text contains words the community filter doesn't allow.
    case contentNotAllowed
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
    func fetchCommunityStats() async throws -> CommunityStats

    // Gallery
    /// Visible posts, newest first, each with its first two replies.
    func fetchFeed(before: Date?, limit: Int) async throws -> [RemotePost]
    func fetchReplies(postID: UUID) async throws -> [RemoteReply]
    /// The posts the user liked and saved.
    func fetchMyReactions() async throws -> (liked: Set<UUID>, saved: Set<UUID>)
    func setLiked(_ liked: Bool, postID: UUID) async throws
    func setSaved(_ saved: Bool, postID: UUID) async throws
    /// Records that the user accepted the community terms.
    func acceptTerms() async throws -> Date
    /// Uploads a JPEG into the user's folder and returns its storage path.
    func uploadImage(_ jpeg: Data) async throws -> String
    func createPost(_ draft: PostDraft) async throws -> RemotePost
    func createReply(postID: UUID, body: String, imagePath: String?) async throws -> RemoteReply
    /// Deletes the user's own post and its photos.
    func deletePost(_ post: RemotePost) async throws
    func deleteReply(_ reply: RemoteReply) async throws
    func report(_ target: ReportTarget, reason: String?) async throws
    func block(_ userID: UUID) async throws
    func unblock(_ userID: UUID) async throws
    func fetchBlockedUsers() async throws -> [PostAuthor]
    /// Where a stored photo can be downloaded.
    func imageURL(for path: String) -> URL?

    // Map
    /// Visible posts with a location inside `bounds`, newest first.
    func fetchMapPosts(in bounds: MapBounds, material: String?) async throws -> [MapPost]
    /// How many visible posts with a location are within `radius` meters.
    func fetchNearbyCount(latitude: Double, longitude: Double, radius: Double, material: String?) async throws -> Int
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
    func fetchCommunityStats() async throws -> CommunityStats { throw BackendError.notConfigured }
    func fetchFeed(before: Date?, limit: Int) async throws -> [RemotePost] { throw BackendError.notConfigured }
    func fetchReplies(postID: UUID) async throws -> [RemoteReply] { throw BackendError.notConfigured }
    func fetchMyReactions() async throws -> (liked: Set<UUID>, saved: Set<UUID>) { throw BackendError.notConfigured }
    func setLiked(_ liked: Bool, postID: UUID) async throws { throw BackendError.notConfigured }
    func setSaved(_ saved: Bool, postID: UUID) async throws { throw BackendError.notConfigured }
    func acceptTerms() async throws -> Date { throw BackendError.notConfigured }
    func uploadImage(_ jpeg: Data) async throws -> String { throw BackendError.notConfigured }
    func createPost(_ draft: PostDraft) async throws -> RemotePost { throw BackendError.notConfigured }
    func createReply(postID: UUID, body: String, imagePath: String?) async throws -> RemoteReply {
        throw BackendError.notConfigured
    }
    func deletePost(_ post: RemotePost) async throws { throw BackendError.notConfigured }
    func deleteReply(_ reply: RemoteReply) async throws { throw BackendError.notConfigured }
    func report(_ target: ReportTarget, reason: String?) async throws { throw BackendError.notConfigured }
    func block(_ userID: UUID) async throws { throw BackendError.notConfigured }
    func unblock(_ userID: UUID) async throws { throw BackendError.notConfigured }
    func fetchBlockedUsers() async throws -> [PostAuthor] { throw BackendError.notConfigured }
    func imageURL(for path: String) -> URL? { nil }
    func fetchMapPosts(in bounds: MapBounds, material: String?) async throws -> [MapPost] {
        throw BackendError.notConfigured
    }
    func fetchNearbyCount(latitude: Double, longitude: Double, radius: Double, material: String?) async throws -> Int {
        throw BackendError.notConfigured
    }
}
