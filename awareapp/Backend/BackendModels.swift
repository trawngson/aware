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
struct LeaderboardRow: Decodable, Equatable, Sendable {
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
