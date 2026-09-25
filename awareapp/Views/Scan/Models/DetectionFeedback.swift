import Foundation

/// The user's answer to "Was this detection correct?" for one scan event.
struct DetectionFeedback: Equatable {
    enum Verdict: Equatable {
        case confirmed
        /// A canonical label, or `DetectionFeedback.somethingElse`.
        case corrected(to: String)
    }

    static let somethingElse = "something_else"

    let scanEventID: UUID
    let predictedLabel: String
    let confidence: Double
    let verdict: Verdict
    let date: Date
}

/// Keeps detection feedback for the session. Like the Gallery, it is in
/// memory only: nothing is uploaded or used for training yet.
@MainActor
final class DetectionFeedbackLog {
    static let shared = DetectionFeedbackLog()

    private(set) var entries: [DetectionFeedback] = []

    func record(_ feedback: DetectionFeedback) {
        entries.removeAll { $0.scanEventID == feedback.scanEventID }
        entries.append(feedback)
    }
}
