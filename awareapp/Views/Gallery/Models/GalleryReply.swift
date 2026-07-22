import SwiftUI

struct GalleryReply: Identifiable, Equatable {
    let id: UUID
    let userName: String
    let time: String
    let content: String
    let avatarSymbol: String
    let avatarColor: Color
    
    init(
        id: UUID = UUID(),
        userName: String,
        time: String,
        content: String,
        avatarSymbol: String = "face.smiling.fill",
        avatarColor: Color = .green
    ) {
        self.id = id
        self.userName = userName
        self.time = time
        self.content = content
        self.avatarSymbol = avatarSymbol
        self.avatarColor = avatarColor
    }
}
