import Combine
import Foundation

enum RewardState: Equatable {
    case eligible
    case ineligible
    case alreadyAwarded
    case confirmationRequired
}

struct RewardResult: Equatable {
    let state: RewardState
    let points: Int
    /// Stable reason code for records and tests.
    let reason: String
    let scanEventID: UUID
}

/// A scan event that earned points.
struct AwardedScan: Identifiable, Equatable {
    /// The scan event's ID.
    let id: UUID
    let label: CanonicalLabel?
    let displayName: String
    let group: DisposalGroup?
    let points: Int
    let date: Date
}

/// Reward layer (SPECIFICATION.md 5.3): decides whether a scan event earns
/// points and awards each scan event at most once. It never reads the
/// detector directly; it only sees the policy result.
@MainActor
final class RewardLedger: ObservableObject {
    static let shared = RewardLedger()

    /// Scan events awarded this session, oldest first.
    @Published private(set) var awards: [AwardedScan] = []

    var totalPoints: Int { awards.map(\.points).reduce(0, +) }

    func evaluate(_ policy: PolicyResult, scanEventID: UUID) -> RewardResult {
        if let award = awards.first(where: { $0.id == scanEventID }) {
            return RewardResult(state: .alreadyAwarded, points: award.points, reason: "already_awarded", scanEventID: scanEventID)
        }
        switch policy.state {
        case .confirmationRequired:
            return RewardResult(state: .confirmationRequired, points: 0, reason: "confirmation_required", scanEventID: scanEventID)
        case .unsupported:
            return RewardResult(state: .ineligible, points: 0, reason: "unsupported_label", scanEventID: scanEventID)
        case .guidanceAvailable:
            guard policy.isRewardEligible else {
                return RewardResult(state: .ineligible, points: 0, reason: "no_reward_for_group", scanEventID: scanEventID)
            }
            return RewardResult(state: .eligible, points: policy.rewardPoints, reason: "sorted_\(policy.group?.rawValue ?? "unknown")", scanEventID: scanEventID)
        }
    }

    /// Awards points for an eligible scan event. Returns the result after the
    /// attempt; a second call for the same event reports `alreadyAwarded`.
    @discardableResult
    func award(_ policy: PolicyResult, scanEventID: UUID) -> RewardResult {
        let result = evaluate(policy, scanEventID: scanEventID)
        guard result.state == .eligible else { return result }
        awards.append(AwardedScan(id: scanEventID, label: policy.label, displayName: policy.displayName,
                                  group: policy.group, points: result.points, date: .now))
        return result
    }
}
