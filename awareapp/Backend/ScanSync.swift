import Foundation

/// The phone's list of scans, as the sync needs it. `RewardLedger` provides it.
@MainActor
protocol ScanSyncQueue: AnyObject {
    /// Scans the server hasn't accepted yet.
    func pendingScans() -> [ScanSnapshot]
    /// Stores the server's decision for a scan.
    func applyServerResult(_ response: ScanAwardResponse, to scanID: UUID)
    /// Marks a scan the server refused for good, so it stops blocking the queue.
    func markRejected(_ scanID: UUID)
    /// Adds scans the server knows but this phone doesn't (after a reinstall).
    func restore(_ events: [RemoteScanEvent])
}

/// Sends scans saved on the phone to the server, oldest first, and brings
/// back scans the phone is missing. Points always come from the server: a
/// scan's local points are only an estimate until it is synced.
@MainActor
final class ScanSync {
    private let backend: CommunityBackend
    private unowned let queue: ScanSyncQueue
    private(set) var isRunning = false

    init(backend: CommunityBackend, queue: ScanSyncQueue) {
        self.backend = backend
        self.queue = queue
    }

    /// Sends every pending scan. Stops at the first failure that may go away
    /// (offline, server trouble) and throws it; the rest wait for next time.
    /// Returns how many scans the server answered.
    @discardableResult
    func pushPending() async throws -> Int {
        guard backend.isConfigured, !isRunning else { return 0 }
        isRunning = true
        defer { isRunning = false }

        var answered = 0
        for scan in queue.pendingScans().sorted(by: { $0.scannedAt < $1.scannedAt }) {
            do {
                let response = try await backend.awardScan(scan.awardRequest)
                queue.applyServerResult(response, to: scan.id)
                answered += 1
            } catch BackendError.rejected {
                queue.markRejected(scan.id)
            }
        }
        return answered
    }

    /// Adds the user's server-side scans that aren't on this phone.
    func restoreHistory(limit: Int = 1_000) async throws {
        guard backend.isConfigured else { return }
        let events = try await backend.fetchMyScanEvents(limit: limit)
        queue.restore(events)
    }
}
