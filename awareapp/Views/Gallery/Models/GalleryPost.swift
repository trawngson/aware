import SwiftUI

/// Main material of a shared project. Used for post tags and map filters.
enum MaterialTag: String, CaseIterable, Identifiable {
    case plastic, paper, glass, metal

    var id: String { rawValue }

    var title: LocalizedStringKey {
        switch self {
        case .plastic: "Plastic"
        case .paper: "Paper"
        case .glass: "Glass"
        case .metal: "Metal"
        }
    }

    var tint: Color {
        switch self {
        case .plastic: Theme.green
        case .paper: Theme.blue
        case .glass: Theme.cyanDeep
        case .metal: Theme.orangeDeep
        }
    }
}

struct GalleryPost: Identifiable, Equatable {
    let id: UUID
    let author: CommunityMember
    let time: String
    /// Short project name, shown on the recycling map.
    let title: String?
    let content: String
    let likes: Int
    let saved: Int
    let shares: Int
    let showTranslate: Bool
    let tag: MaterialTag?
    var replies: [GalleryReply]
    let attachmentAssetName: String?
    let attachmentImage: UIImage?  // For user-uploaded images

    var comments: Int { replies.count }
    var hasAttachment: Bool { attachmentAssetName != nil || attachmentImage != nil }

    init(
        id: UUID = UUID(),
        author: CommunityMember,
        time: String,
        title: String? = nil,
        content: String,
        likes: Int = 0,
        saved: Int = 0,
        shares: Int = 0,
        showTranslate: Bool = false,
        tag: MaterialTag? = nil,
        replies: [GalleryReply] = [],
        attachmentAssetName: String? = nil,
        attachmentImage: UIImage? = nil
    ) {
        self.id = id
        self.author = author
        self.time = time
        self.title = title
        self.content = content
        self.likes = likes
        self.saved = saved
        self.shares = shares
        self.showTranslate = showTranslate
        self.tag = tag
        self.replies = replies
        self.attachmentAssetName = attachmentAssetName
        self.attachmentImage = attachmentImage
    }

    // Custom Equatable implementation (UIImage is not Equatable)
    static func == (lhs: GalleryPost, rhs: GalleryPost) -> Bool {
        lhs.id == rhs.id &&
        lhs.content == rhs.content &&
        lhs.replies == rhs.replies &&
        lhs.attachmentAssetName == rhs.attachmentAssetName &&
        lhs.attachmentImage === rhs.attachmentImage
    }

    /// Stable IDs so the recycling map can link to the sample posts.
    enum SampleID {
        static let fabricLamp = UUID(uuidString: "6B1F2C8E-2D4A-4E61-9B4B-0A1D7E3C5F01")!
        static let eggCartonTurtle = UUID(uuidString: "6B1F2C8E-2D4A-4E61-9B4B-0A1D7E3C5F02")!
        static let bottleSpiral = UUID(uuidString: "6B1F2C8E-2D4A-4E61-9B4B-0A1D7E3C5F03")!
    }

    static let sample: [GalleryPost] = [
        GalleryPost(
            id: SampleID.fabricLamp,
            author: Community.dieuLinh,
            time: "2d",
            title: "Fabric lamp",
            content: "I just recycled my mom's old fabric into this beautiful lamp for my room's decor! I think this is by far my most beautiful project.\nAnyone hyped up for a tutorial?",
            likes: 2000,
            saved: 2,
            shares: 2,
            replies: [
                GalleryReply(author: Community.me, time: "1d", content: "YESS SHOW US HOW"),
                GalleryReply(author: Community.haChi, time: "22h", content: "i made something similar a while ago:))"),
            ],
            attachmentAssetName: "RecycleProject1"
        ),
        GalleryPost(
            id: SampleID.eggCartonTurtle,
            author: Community.anthony,
            time: "1d",
            title: "Egg carton turtle",
            content: "Yo, I'm so excited to share with you guys what I've been working on for the last few days: it's a DIY little turtle made from used egg carton.\nI was about to throw them away but then I suddenly had this amazing idea in my head. Do you guys think it looks good??",
            likes: 7,
            saved: 0,
            tag: .paper,
            replies: [
                GalleryReply(author: Community.me, time: "10m", content: "Hey that looks so cute!"),
            ],
            attachmentAssetName: "RecycleProject2"
        ),
        GalleryPost(
            id: SampleID.bottleSpiral,
            author: Community.max,
            time: "14h",
            title: "Bottle flower spiral",
            content: "I just followed one of @Anthony's tutorial and ended up with this cute-looking flower spiral, it's so adorable that I think I might keep it on my bedside from now on!",
            likes: 30,
            saved: 289,
            shares: 27,
            showTranslate: true,
            tag: .plastic,
            replies: [
                GalleryReply(author: Community.anthony, time: "10h", content: "Nice, yours look way better than mine actually :)"),
                GalleryReply(author: Community.max, time: "9h", content: "Keep posting more tutorials!"),
            ],
            attachmentAssetName: "RecycleProject3"
        ),
    ]
}
