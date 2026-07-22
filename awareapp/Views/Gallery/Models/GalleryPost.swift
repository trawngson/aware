import SwiftUI

struct GalleryPost: Identifiable, Equatable {
    let id: UUID
    let userName: String
    let time: String
    let content: String
    let likes: Int
    let comments: Int
    let saved: Int
    let shares: String
    let hasAttachment: Bool
    let showTranslate: Bool
    let avatarSymbol: String
    let avatarColor: Color
    let leafCount: String
    let replies: [GalleryReply]
    let avatarAssetName: String?
    let attachmentAssetName: String?
    let attachmentImage: UIImage?  // For user-uploaded images
    
    init(
        id: UUID = UUID(),
        userName: String,
        time: String,
        content: String,
        likes: Int = 0,
        comments: Int = 0,
        saved: Int = 0,
        shares: String = "",
        hasAttachment: Bool = false,
        showTranslate: Bool = false,
        avatarSymbol: String = "face.smiling.fill",
        avatarColor: Color = .green,
        leafCount: String = "0",
        replies: [GalleryReply] = [],
        avatarAssetName: String? = nil,
        attachmentAssetName: String? = nil,
        attachmentImage: UIImage? = nil
    ) {
        self.id = id
        self.userName = userName
        self.time = time
        self.content = content
        self.likes = likes
        self.comments = comments
        self.saved = saved
        self.shares = shares
        self.hasAttachment = hasAttachment
        self.showTranslate = showTranslate
        self.avatarSymbol = avatarSymbol
        self.avatarColor = avatarColor
        self.leafCount = leafCount
        self.replies = replies
        self.avatarAssetName = avatarAssetName
        self.attachmentAssetName = attachmentAssetName
        self.attachmentImage = attachmentImage
    }
    
    // Custom Equatable implementation (UIImage is not Equatable)
    static func == (lhs: GalleryPost, rhs: GalleryPost) -> Bool {
        lhs.id == rhs.id &&
        lhs.userName == rhs.userName &&
        lhs.time == rhs.time &&
        lhs.content == rhs.content &&
        lhs.likes == rhs.likes &&
        lhs.comments == rhs.comments &&
        lhs.saved == rhs.saved &&
        lhs.hasAttachment == rhs.hasAttachment &&
        lhs.attachmentAssetName == rhs.attachmentAssetName
    }

    static let sample: [GalleryPost] = [
        GalleryPost(
            userName: "Dieu Linh Do",
            time: "2d",
            content: "I just recycled my mom's old fabric into this beautiful lamp for my room's decor! I think this is by far my most beautiful project.\nAnyone hyped up for a tutorial?",
            likes: 2000,
            comments: 2,
            saved: 2,
            shares: "2",
            hasAttachment: true,
            showTranslate: false,
            avatarSymbol: "face.smiling.fill",
            avatarColor: .orange,
            leafCount: "2,460",
            replies: [
                GalleryReply(
                    userName: "Truong Son Nguyen",
                    time: "1d",
                    content: "YESS SHOW US HOW",
                    avatarSymbol: "face.smiling.fill",
                    avatarColor: .blue
                ),
                GalleryReply(
                    userName: "Ha Chi Pham",
                    time: "22h",
                    content: "i made something similar a while ago:))",
                    avatarSymbol: "face.smiling.inverse",
                    avatarColor: .purple
                )
            ],
            avatarAssetName: nil,
            attachmentAssetName: "RecycleProject1"
        ),
        GalleryPost(
            userName: "Anthony",
            time: "1d",
            content: "Yo, I'm so excited to share with you guys what I've been working on for the last few days: it's a DIY little turtle made from used egg carton.\nI was about to throw them away but then I suddenly had this amazing idea in my head. Do you guys think it looks good??",
            likes: 7,
            comments: 1,
            saved: 0,
            shares: "",
            hasAttachment: true,
            showTranslate: false,
            avatarSymbol: "face.smiling.inverse",
            avatarColor: .purple,
            leafCount: "1,980",
            replies: [
                GalleryReply(
                    userName: "Truong Son Nguyen",
                    time: "10m",
                    content: "Hey that looks so cute!",
                    avatarSymbol: "face.smiling.fill",
                    avatarColor: .blue
                )
            ],
            avatarAssetName: nil,
            attachmentAssetName: "RecycleProject2"
        ),
        GalleryPost(
            userName: "Max",
            time: "14h",
            content: "I just followed one of @Anthony's tutorial and ended up with this cute-looking flower spiral, it's so adorable that I think I might keep it on my bedside from now on!",
            likes: 30,
            comments: 2,
            saved: 289,
            shares: "27",
            hasAttachment: true,
            showTranslate: true,
            avatarSymbol: "face.dashed",
            avatarColor: .blue,
            leafCount: "820",
            replies: [
                GalleryReply(
                    userName: "Anthony",
                    time: "10h",
                    content: "Nice, yours look way better than mine actually :)",
                    avatarSymbol: "face.smiling.fill",
                    avatarColor: .green
                ),
                GalleryReply(
                    userName: "Max",
                    time: "9h",
                    content: "Keep posting more tutorials! 🤣",
                    avatarSymbol: "face.dashed",
                    avatarColor: .blue
                )
            ],
            avatarAssetName: nil,
            attachmentAssetName: "RecycleProject3"
        )
    ]
}
