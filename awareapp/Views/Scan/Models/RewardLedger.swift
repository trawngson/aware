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

/// Reward layer (SPECIFICATION.md 5.3): decides whether a scan event earns
/// points and awards each scan event at most once. It never reads the
/// detector directly; it only sees the policy result.
///
/// Awarded scans are saved on the phone (`LocalStore`), so they survive
/// relaunches and work offline. With a backend, the server has the final say:
/// the points here are an estimate until `ScanSync` sends the scan and stores
/// the server's answer.
@MainActor
final class RewardLedger: ObservableObject {
    static let shared = RewardLedger(store: .shared)

    /// Rewarded scans, newest first.
    @Published private(set) var scans: [ScanSnapshot] = []

    /// Most points per day, applied on the phone as the server would. Nil
    /// (no cap) when there is no backend.
    var dailyCap: Int?

    /// Called after a scan is saved, so the app can sync it.
    var didRecordScan: (() -> Void)?

    private let store: LocalStore
    private let vietnamCalendar: Calendar = {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "Asia/Ho_Chi_Minh") ?? .current
        return calendar
    }()

    /// A ledger on its own in-memory store (tests and previews).
    convenience init() {
        self.init(store: LocalStore(inMemory: true))
    }

    init(store: LocalStore) {
        self.store = store
        scans = store.allScans()
    }

    var awardedEvents: [UUID: Int] {
        Dictionary(scans.map { ($0.id, $0.points) }, uniquingKeysWith: { first, _ in first })
    }

    var totalPoints: Int { scans.reduce(0) { $0 + $1.points } }

    func evaluate(_ policy: PolicyResult, scanEventID: UUID, at date: Date = .now) -> RewardResult {
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
            if let dailyCap, pointsEarned(onDayOf: date) + policy.rewardPoints > dailyCap {
                return RewardResult(state: .ineligible, points: 0, reason: "daily_cap_reached", scanEventID: scanEventID)
            }
            return RewardResult(state: .eligible, points: policy.rewardPoints, reason: "sorted_\(policy.group?.rawValue ?? "unknown")", scanEventID: scanEventID)
        }
    }

    /// Awards points for an eligible scan event. Returns the result after the
    /// attempt; a second call for the same event reports `alreadyAwarded`.
    @discardableResult
    func award(_ policy: PolicyResult, scanEventID: UUID, at date: Date = .now) -> RewardResult {
        let result = evaluate(policy, scanEventID: scanEventID, at: date)
        guard result.state == .eligible, let label = policy.label else { return result }
        let scan = ScanSnapshot(id: scanEventID, label: label.rawValue, choiceID: policy.choiceID,
                                policyVersion: policy.policyVersion, group: policy.group?.rawValue,
                                points: result.points, reasonCode: result.reason, scannedAt: date,
                                syncState: .pending)
        store.save([scan])
        scans.insert(scan, at: 0)
        didRecordScan?()
        return result
    }

    /// Points already earned on the Vietnam calendar day of `date`.
    private func pointsEarned(onDayOf date: Date) -> Int {
        scans.filter { vietnamCalendar.isDate($0.scannedAt, inSameDayAs: date) }.reduce(0) { $0 + $1.points }
    }

    /// Forgets every scan on this phone (after deleting the account).
    func removeAll() {
        store.deleteAllScans()
        scans = []
    }

    private func replace(_ scan: ScanSnapshot) {
        store.save([scan])
        if let index = scans.firstIndex(where: { $0.id == scan.id }) {
            scans[index] = scan
        }
    }
}

// MARK: - Sync queue

extension RewardLedger: ScanSyncQueue {
    func pendingScans() -> [ScanSnapshot] {
        scans.filter { $0.syncState == .pending }
    }

    func applyServerResult(_ response: ScanAwardResponse, to scanID: UUID) {
        guard var scan = scans.first(where: { $0.id == scanID }) else { return }
        switch response.state {
        case .eligible, .alreadyAwarded:
            scan.points = response.points
        case .ineligible, .confirmationRequired:
            scan.points = 0
        }
        scan.reasonCode = response.reasonCode
        scan.syncState = .synced
        replace(scan)
    }

    func markRejected(_ scanID: UUID) {
        guard var scan = scans.first(where: { $0.id == scanID }) else { return }
        scan.points = 0
        scan.reasonCode = "rejected"
        scan.syncState = .rejected
        replace(scan)
    }

    func restore(_ events: [RemoteScanEvent]) {
        let known = Set(scans.map(\.id))
        let missing = events
            .filter { !known.contains($0.id) && $0.rewardState != "confirmation_required" }
            .map { event in
                ScanSnapshot(id: event.id, label: event.label, choiceID: event.choiceID,
                             policyVersion: event.policyVersion, group: event.disposalGroup,
                             points: event.pointsAwarded, reasonCode: event.reasonCode,
                             scannedAt: event.scannedAt, syncState: .synced)
            }
        guard !missing.isEmpty else { return }
        store.save(missing)
        scans = (scans + missing).sorted { $0.scannedAt > $1.scannedAt }
    }
}
