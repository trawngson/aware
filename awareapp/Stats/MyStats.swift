import Foundation

/// Which numbers Home and the insight screens show.
@MainActor
enum MyStats {
    /// The user's own numbers, or nil while the demo's sample numbers should
    /// show instead: samples are on and nothing has been scanned yet.
    static var current: PersonalStats? {
        let scans = RewardLedger.shared.scans
        if scans.isEmpty && AppSession.shared.showSamples { return nil }
        return PersonalStats(scans: scans)
    }
}
