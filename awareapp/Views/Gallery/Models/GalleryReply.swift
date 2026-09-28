import SwiftUI

struct GalleryReply: Identifiable, Equatable {
    let id: UUID
    let author: CommunityMember
    let time: String
    let content: String
    let image: UIImage?

    init(
        id: UUID = UUID(),
        author: CommunityMember,
        time: String,
        content: String,
        image: UIImage? = nil
    ) {
        self.id = id
        self.author = author
        self.time = time
        self.content = content
        self.image = image
    }

    static func == (lhs: GalleryReply, rhs: GalleryReply) -> Bool {
        lhs.id == rhs.id && lhs.content == rhs.content && lhs.image === rhs.image
    }
}
