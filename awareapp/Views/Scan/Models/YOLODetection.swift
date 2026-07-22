import SwiftUI

// MARK: - Detection Model

struct YOLODetection: Identifiable, Equatable {
    let id: Int // Stable ID based on rank (0, 1, 2)
    let label: String
    let confidence: Double
    let boundingBox: CGRect
}
