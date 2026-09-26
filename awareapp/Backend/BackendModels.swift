import Foundation

// Shapes of the rows and function results the app exchanges with the backend.
// Field names follow the database (supabase/migrations).

/// Server settings the admin page controls (`app_settings`).
struct RemoteSettings: Codable, Equatable, Sendable {
    /// Show the app's built-in sample people, posts and map spots.
    var showSamples: Bool
    /// Most points one user can earn per Vietnam calendar day.
    var dailyPointCap: Int
    /// Distinct reports that hide a post or reply until an admin looks.
    var reportThreshold: Int

    enum CodingKeys: String, CodingKey {
        case showSamples = "show_samples"
        case dailyPointCap = "daily_point_cap"
        case reportThreshold = "report_threshold"
    }
}

/// A user's profile (`profiles`).
struct RemoteProfile: Codable, Equatable, Sendable {
    let id: UUID
    var displayName: String
    var avatarInitials: String
    /// Avatar gradient colors as 0xRRGGBB.
    var avatarTop: Int
    var avatarBottom: Int
    var role: String
    var bannedAt: Date?
    var termsAcceptedAt: Date?

    var isAdmin: Bool { role == "admin" }
    var isBanned: Bool { bannedAt != nil }
    var hasAcceptedTerms: Bool { termsAcceptedAt != nil }

    enum CodingKeys: String, CodingKey {
        case id
        case displayName = "display_name"
        case avatarInitials = "avatar_initials"
        case avatarTop = "avatar_top"
        case avatarBottom = "avatar_bottom"
        case role
        case bannedAt = "banned_at"
        case termsAcceptedAt = "terms_accepted_at"
    }
}

/// One scan event sent to `award_scan()`. The server decides the points.
struct ScanAwardRequest: Encodable, Equatable, Sendable {
    let scanEventID: UUID
    /// Canonical label, e.g. "plastic_bottle".
    let label: String
    let policyVersion: String
    /// The user explicitly confirmed the result.
    let confirmed: Bool
    /// The user's answer for labels that need one, e.g. "paper" for a cup.
    let choiceID: String?
    let scannedAt: Date

    enum CodingKeys: String, CodingKey {
        case scanEventID = "p_scan_event_id"
        case label = "p_label"
        case policyVersion = "p_policy_version"
        case confirmed = "p_confirmed"
        case choiceID = "p_choice_id"
        case scannedAt = "p_scanned_at"
    }
}

/// The reward output of `award_scan()` (backend/SPECIFICATION.md 5.3).
struct ScanAwardResponse: Decodable, Equatable, Sendable {
    enum State: String, Decodable, Sendable {
        case eligible
        case ineligible
        case alreadyAwarded = "already_awarded"
        case confirmationRequired = "confirmation_required"
    }

    let state: State
    let points: Int
    /// Stable reason code, e.g. "sorted_recyclable" or "daily_cap_reached".
    let reasonCode: String
    let scanEventID: UUID

    enum CodingKeys: String, CodingKey {
        case state
        case points
        case reasonCode = "reason_code"
        case scanEventID = "scan_event_id"
    }
}

/// A scan event as stored on the server, used to restore history on a new
/// phone or after reinstalling.
struct RemoteScanEvent: Decodable, Equatable, Sendable {
    let id: UUID
    let label: String
    let choiceID: String?
    let policyVersion: String
    let disposalGroup: String?
    let pointsAwarded: Int
    let rewardState: String
    let reasonCode: String
    let scannedAt: Date

    enum CodingKeys: String, CodingKey {
        case id
        case label
        case choiceID = "choice_id"
        case policyVersion = "policy_version"
        case disposalGroup = "disposal_group"
        case pointsAwarded = "points_awarded"
        case rewardState = "reward_state"
        case reasonCode = "reason_code"
        case scannedAt = "scanned_at"
    }
}

enum LeaderboardPeriod: String, Sendable {
    /// This calendar month in Vietnam time.
    case month
    case all
}

/// One row of `leaderboard()`.
struct LeaderboardRow: Codable, Equatable, Sendable {
    let rank: Int
    let userID: UUID
    let displayName: String
    let avatarInitials: String
    let avatarTop: Int
    let avatarBottom: Int
    let points: Int
    /// The caller's own row (added after the top rows when it isn't among them).
    let isMe: Bool

    enum CodingKeys: String, CodingKey {
        case rank
        case userID = "user_id"
        case displayName = "display_name"
        case avatarInitials = "avatar_initials"
        case avatarTop = "avatar_top"
        case avatarBottom = "avatar_bottom"
        case points
        case isMe = "is_me"
    }
}

/// Community totals from `community_stats()`.
struct CommunityStats: Codable, Equatable, Sendable {
    /// People who have earned points (banned users left out).
    let recyclers: Int
    /// Recycled items that earned points, by canonical label.
    let recycledByLabel: [String: Int]

    enum CodingKeys: String, CodingKey {
        case recyclers
        case recycledByLabel = "recycled_by_label"
    }

    /// Estimated weight kept out of landfill, from typical item masses.
    var recycledGrams: Double {
        recycledByLabel.reduce(0) { total, entry in
            guard let label = CanonicalLabel(rawValue: entry.key) else { return total }
            return total + Double(entry.value) * PersonalStats.typicalMassGrams(for: label)
        }
    }
}

// MARK: - Gallery

/// The public part of a post or reply author's profile.
struct PostAuthor: Codable, Equatable, Sendable {
    let id: UUID
    let displayName: String
    let avatarInitials: String
    let avatarTop: Int
    let avatarBottom: Int

    enum CodingKeys: String, CodingKey {
        case id
        case displayName = "display_name"
        case avatarInitials = "avatar_initials"
        case avatarTop = "avatar_top"
        case avatarBottom = "avatar_bottom"
    }

    static let columns = "id, display_name, avatar_initials, avatar_top, avatar_bottom"
}

/// A reply (`replies`), with its author.
struct RemoteReply: Codable, Equatable, Sendable, Identifiable {
    let id: UUID
    let postID: UUID
    let body: String
    let imagePath: String?
    /// Set while it is hidden for review (only its author sees it then).
    let hiddenAt: Date?
    let createdAt: Date
    let author: PostAuthor

    enum CodingKeys: String, CodingKey {
        case id
        case postID = "post_id"
        case body
        case imagePath = "image_path"
        case hiddenAt = "hidden_at"
        case createdAt = "created_at"
        case author
    }

    static let columns = "id, post_id, body, image_path, hidden_at, created_at, author:profiles!author_id(\(PostAuthor.columns))"
}

/// A post (`posts`), with its author, counts and, from the feed, its first
/// replies.
struct RemotePost: Codable, Equatable, Sendable, Identifiable {
    let id: UUID
    let title: String?
    let body: String
    /// "plastic", "paper", "glass" or "metal".
    let material: String?
    let imagePath: String?
    var likeCount: Int
    var replyCount: Int
    var saveCount: Int
    let hiddenAt: Date?
    let createdAt: Date
    let author: PostAuthor
    var replies: [RemoteReply]?

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case body
        case material
        case imagePath = "image_path"
        case likeCount = "like_count"
        case replyCount = "reply_count"
        case saveCount = "save_count"
        case hiddenAt = "hidden_at"
        case createdAt = "created_at"
        case author
        case replies
    }

    static let columns = "id, title, body, material, image_path, like_count, reply_count, save_count, hidden_at, created_at, author:profiles!author_id(\(PostAuthor.columns))"
}

/// What the composer sends for a new post. The location is rounded to about
/// 500 m by the database.
struct PostDraft: Encodable, Equatable, Sendable {
    var title: String?
    var body: String
    var material: String?
    var imagePath: String?
    var latitude: Double?
    var longitude: Double?

    enum CodingKeys: String, CodingKey {
        case title
        case body
        case material
        case imagePath = "image_path"
        case latitude
        case longitude
    }
}

/// A post on the recycling map (`map_posts()`).
struct MapPost: Codable, Equatable, Sendable, Identifiable {
    let id: UUID
    let title: String?
    let body: String
    let material: String?
    let imagePath: String?
    let latitude: Double
    let longitude: Double
    let createdAt: Date
    let authorID: UUID
    let authorName: String
    let authorInitials: String
    let authorTop: Int
    let authorBottom: Int

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case body
        case material
        case imagePath = "image_path"
        case latitude
        case longitude
        case createdAt = "created_at"
        case authorID = "author_id"
        case authorName = "author_name"
        case authorInitials = "author_initials"
        case authorTop = "author_top"
        case authorBottom = "author_bottom"
    }
}

/// A map area, in degrees.
struct MapBounds: Equatable, Sendable {
    var minLatitude: Double
    var minLongitude: Double
    var maxLatitude: Double
    var maxLongitude: Double
}

/// Something a user can report.
enum ReportTarget: Equatable, Sendable {
    case post(UUID)
    case reply(UUID)
    case user(UUID)
}
