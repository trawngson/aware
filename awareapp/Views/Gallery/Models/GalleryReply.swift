import SwiftUI

struct GalleryReply: Identifiable, Equatable {
    let id: UUID
    let author: CommunityMember
    let time: String
    let content: String
    let image: UIImage?
    /// A photo stored on the backend.
    let imageURL: URL?
    /// The reply as the backend sent it; nil for samples and local replies.
    let remote: RemoteReply?

    init(
        id: UUID = UUID(),
        author: CommunityMember,
        time: String,
        content: String,
        image: UIImage? = nil,
        imageURL: URL? = nil,
        remote: RemoteReply? = nil
    ) {
        self.id = id
        self.author = author
        self.time = time
        self.content = content
        self.image = image
        self.imageURL = imageURL
        self.remote = remote
    }

    /// Hidden after reports until an admin looks; only its author sees it.
    var isHiddenForReview: Bool { remote?.hiddenAt != nil }

    static func == (lhs: GalleryReply, rhs: GalleryReply) -> Bool {
        lhs.id == rhs.id && lhs.content == rhs.content && lhs.image === rhs.image
            && lhs.imageURL == rhs.imageURL && lhs.remote == rhs.remote
    }
}
