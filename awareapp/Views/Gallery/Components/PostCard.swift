import SwiftUI

struct PostCard: View {
    let post: GalleryPost
    let isLiked: Bool
    let likeCount: Int
    let isSaved: Bool
    let savedCount: Int
    let onToggleLike: () -> Void
    let onToggleSave: () -> Void

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            AvatarView(
                size: 44,
                systemName: post.avatarSymbol,
                tint: post.avatarColor,
                assetName: post.avatarAssetName
            )

            VStack(alignment: .leading, spacing: 16) {
                VStack(alignment: .leading, spacing: 4) {
                    PostHeaderRow(post: post)

                    Text(post.content)
                        .font(.body)
                        .foregroundStyle(.primary)
                }

                if post.hasAttachment {
                    PostAttachmentCard(assetName: post.attachmentAssetName, image: post.attachmentImage)
                }

                if post.showTranslate {
                    Text("Translate")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                if post.replies.isEmpty {
                    PostActionRow(
                        post: post,
                        isLiked: isLiked,
                        likeCount: likeCount,
                        isSaved: isSaved,
                        savedCount: savedCount,
                        onToggleLike: onToggleLike,
                        onToggleSave: onToggleSave
                    )
                } else {
                    VStack(alignment: .leading, spacing: 8) {
                        ReplyThread(replies: post.replies)
                        PostActionRow(
                            post: post,
                            isLiked: isLiked,
                            likeCount: likeCount,
                            isSaved: isSaved,
                            savedCount: savedCount,
                            onToggleLike: onToggleLike,
                            onToggleSave: onToggleSave
                        )
                    }
                }
            }
        }
        .padding()
        .background(CardBackground())
    }
}

struct PostHeaderRow: View {
    let post: GalleryPost

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 6) {
            Text(post.userName)
                .font(.headline)
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text(post.leafCount)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                Image(systemName: "leaf.fill")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            Text(post.time)
                .font(.subheadline)
                .foregroundStyle(.secondary)

            Spacer()

            Image(systemName: "ellipsis")
                .foregroundStyle(.secondary)
                .alignmentGuide(.firstTextBaseline) { dimensions in
                    dimensions[.bottom]
                }
        }
    }
}

struct PostAttachmentCard: View {
    let assetName: String?
    let image: UIImage?
    
    init(assetName: String? = nil, image: UIImage? = nil) {
        self.assetName = assetName
        self.image = image
    }

    var body: some View {
        RoundedRectangle(cornerRadius: 14, style: .continuous)
            .fill(Color(uiColor: .systemGray6))
            .frame(height: 500)
            .overlay(attachmentContent)
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    @ViewBuilder
    private var attachmentContent: some View {
        if let image {
            Image(uiImage: image)
                .resizable()
                .scaledToFill()
                .overlay(Color.black.opacity(0.08))
        } else if let assetName {
            Image(assetName)
                .resizable()
                .scaledToFill()
                .overlay(Color.black.opacity(0.08))
        } else {
            VStack(spacing: 8) {
                Image(systemName: "photo")
                    .font(.title2)
                    .foregroundStyle(.secondary)
                Text("Attachment")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

struct PostActionRow: View {
    let post: GalleryPost
    let isLiked: Bool
    let likeCount: Int
    let isSaved: Bool
    let savedCount: Int
    let onToggleLike: () -> Void
    let onToggleSave: () -> Void

    var body: some View {
        HStack(spacing: 20) {
            LikeButton(isLiked: isLiked, count: likeCount, onToggleLike: onToggleLike)
            ActionPill(systemName: "bubble.left", value: post.comments)
            SaveButton(isSaved: isSaved, count: savedCount, onToggleSave: onToggleSave)
            Spacer()
        }
        .font(.subheadline)
        .foregroundStyle(.secondary)
    }
}

struct ReplyThread: View {
    let replies: [GalleryReply]

    private let lineWidth: CGFloat = 2
    private let lineSpacing: CGFloat = 12

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ForEach(replies) { reply in
                ReplyRow(reply: reply)
            }
        }
        .padding(.leading, lineWidth + lineSpacing)
        .overlay(alignment: .leading) {
            Rectangle()
                .fill(Color(uiColor: .systemGray4))
                .frame(width: lineWidth)
                .padding(.top, 6)
                .padding(.bottom, 6)
        }
    }
}

struct ReplyRow: View {
    let reply: GalleryReply

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            AvatarView(size: 28, systemName: reply.avatarSymbol, tint: reply.avatarColor)

            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 6) {
                    Text(reply.userName)
                        .font(.subheadline.weight(.semibold))
                    Text(reply.time)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Text(reply.content)
                    .font(.subheadline)
                    .foregroundStyle(.primary)
            }
        }
    }
}

#Preview {
    PostCard(
        post: GalleryPost.sample[0],
        isLiked: false,
        likeCount: 2000,
        isSaved: false,
        savedCount: 2,
        onToggleLike: {},
        onToggleSave: {}
    )
    .padding()
}
