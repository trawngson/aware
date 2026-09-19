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

/// Reward layer (SPECIFICATION.md 5.3): decides whether a scan event earns
/// points and awards each scan event at most once. It never reads the
/// detector directly; it only sees the policy result.
@MainActor
final class RewardLedger {
    static let shared = RewardLedger()

    private(set) var awardedEvents: [UUID: Int] = [:]

    var totalPoints: Int { awardedEvents.values.reduce(0, +) }

    func evaluate(_ policy: PolicyResult, scanEventID: UUID) -> RewardResult {
        if let points = awardedEvents[scanEventID] {
            return RewardResult(state: .alreadyAwarded, points: points, reason: "already_awarded", scanEventID: scanEventID)
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
        awardedEvents[scanEventID] = result.points
        return result
    }
}
