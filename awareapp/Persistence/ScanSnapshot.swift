import Foundation

/// A rewarded scan saved on this phone, as the stats and the sync queue see
/// it. `ScanRecord` stores it with SwiftData.
struct ScanSnapshot: Identifiable, Equatable, Sendable {
    enum SyncState: String, Codable, Sendable {
        /// Saved on the phone, not yet accepted by the server.
        case pending
        /// The server has recorded it; `points` are the server's.
        case synced
        /// The server refused it for good; it stays for the history, with 0 points.
        case rejected
    }

    /// The scan event ID, shared with the server.
    let id: UUID
    /// Canonical label, e.g. "plastic_bottle".
    let label: String
    /// The user's answer for labels that need one ("paper", "clean").
    let choiceID: String?
    let policyVersion: String
    /// Disposal group raw value ("recyclable", "other").
    let group: String?
    /// Points shown to the user: the local estimate until the server answers.
    var points: Int
    /// Stable reason code of the latest reward decision.
    var reasonCode: String
    let scannedAt: Date
    var syncState: SyncState

    var canonicalLabel: CanonicalLabel? { CanonicalLabel(rawValue: label) }
    var isRecycled: Bool { group == DisposalGroup.recyclable.rawValue }

    var awardRequest: ScanAwardRequest {
        ScanAwardRequest(scanEventID: id, label: label, policyVersion: policyVersion,
                         confirmed: true, choiceID: choiceID, scannedAt: scannedAt)
    }
}
