import SwiftUI
import Translation

/// A post in the Gallery feed. Tapping the card opens its thread.
struct PostCard: View {
    let post: GalleryPost
    let onOpen: () -> Void

    @ObservedObject private var store = GalleryStore.shared
    @State private var showTranslation = false

    private let previewReplies = 2

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            PostAuthorRow(post: post, avatarSize: 40)

            Text(post.content)
                .font(.system(size: 15))
                .lineSpacing(3)
                .foregroundStyle(Theme.ink.opacity(0.85))
                .fixedSize(horizontal: false, vertical: true)

            if post.hasAttachment {
                PostImage(post: post, height: 340, cornerRadius: 20)
            }

            if post.showTranslate {
                Button("Translate") { showTranslation = true }
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(Theme.green)
                    .translationPresentation(isPresented: $showTranslation, text: post.content)
            }

            HStack(spacing: 8) {
                ReactionPill(
                    systemImage: store.likedPostIDs.contains(post.id) ? "heart.fill" : "heart",
                    count: store.likeCounts[post.id] ?? post.likes,
                    tint: store.likedPostIDs.contains(post.id) ? Theme.heart : nil
                ) { store.toggleLike(post.id) }
                .accessibilityLabel(store.likedPostIDs.contains(post.id) ? "Unlike" : "Like")

                ReactionPill(systemImage: "bubble.left", count: post.comments, action: onOpen)
                    .accessibilityLabel("Replies")

                ReactionPill(
                    systemImage: store.savedPostIDs.contains(post.id) ? "bookmark.fill" : "bookmark",
                    count: store.savedCounts[post.id] ?? post.saved,
                    tint: store.savedPostIDs.contains(post.id) ? Theme.amber : nil
                ) { store.toggleSave(post.id) }
                .accessibilityLabel(store.savedPostIDs.contains(post.id) ? "Remove bookmark" : "Bookmark")
            }

            if !post.replies.isEmpty {
                VStack(alignment: .leading, spacing: 12) {
                    ForEach(post.replies.prefix(previewReplies)) { reply in
                        ReplyPreviewRow(reply: reply)
                    }
                    if post.replies.count > previewReplies {
                        Text("View all \(post.replies.count) replies")
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundStyle(Theme.green)
                    }
                }
                .padding(.leading, 12)
                .overlay(alignment: .leading) {
                    Rectangle().fill(Theme.green.opacity(0.2)).frame(width: 2)
                }
            }
        }
        .padding(16)
        .glass(.cardStrong, cornerRadius: 26)
        .contentShape(RoundedRectangle(cornerRadius: 26))
        .onTapGesture(perform: onOpen)
    }
}

// MARK: - Shared post pieces

struct PostAuthorRow: View {
    let post: GalleryPost
    var avatarSize: CGFloat = 40

    var body: some View {
        HStack(spacing: 10) {
            MemberAvatar(member: post.author, size: avatarSize)
            VStack(alignment: .leading, spacing: 1) {
                Text(post.author.name)
                    .font(.system(size: avatarSize > 40 ? 16 : 15, weight: .semibold))
                    .foregroundStyle(Theme.ink)
                HStack(spacing: 4) {
                    LeafAmount(value: post.author.id == Community.me.id ? Community.myPoints : post.author.points,
                               size: 12, color: Theme.ink.opacity(0.55))
                    Text("· \(post.time)")
                        .font(.system(size: 12))
                        .foregroundStyle(Theme.ink.opacity(0.55))
                }
            }
            Spacer(minLength: 0)
            Menu {
                ShareLink(item: post.content) {
                    Label("Share", systemImage: "square.and.arrow.up")
                }
                Button {
                    UIPasteboard.general.string = post.content
                } label: {
                    Label("Copy Text", systemImage: "doc.on.doc")
                }
            } label: {
                Image(systemName: "ellipsis")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(Theme.ink.opacity(0.4))
                    .frame(width: 32, height: 32)
                    .contentShape(Rectangle())
            }
            .accessibilityLabel("More")
        }
    }
}

struct PostImage: View {
    let post: GalleryPost
    let height: CGFloat
    var cornerRadius: CGFloat = 20

    var body: some View {
        Color(hex: 0x11291C, opacity: 0.06)
            .frame(height: height)
            .overlay {
                if let image = post.attachmentImage {
                    Image(uiImage: image).resizable().scaledToFill()
                } else if let name = post.attachmentAssetName {
                    Image(name).resizable().scaledToFill()
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
            .accessibilityHidden(true)
    }
}

/// Gray capsule with an icon and a count (like, reply, bookmark).
struct ReactionPill: View {
    let systemImage: String
    let count: Int
    var tint: Color? = nil
    let action: () -> Void

    @State private var bounce = 0

    var body: some View {
        Button {
            bounce += 1
            action()
        } label: {
            HStack(spacing: 6) {
                Image(systemName: systemImage)
                    .font(.system(size: 15, weight: .medium))
                    .symbolEffect(.bounce, value: bounce)
                Text(CountFormatter.format(count))
                    .font(.system(size: 13, weight: .semibold))
                    .contentTransition(.numericText())
            }
            .foregroundStyle(tint ?? Theme.ink.opacity(0.7))
            .padding(.horizontal, 13)
            .padding(.vertical, 8)
            .background(Capsule().fill(Theme.ink.opacity(0.05)))
            .contentShape(Capsule())
        }
        .buttonStyle(.plain)
        .animation(.snappy, value: count)
    }
}

struct ReplyPreviewRow: View {
    let reply: GalleryReply

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            MemberAvatar(member: reply.author, size: 26)
            VStack(alignment: .leading, spacing: 2) {
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    Text(reply.author.name)
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(Theme.ink)
                    Text(reply.time)
                        .font(.system(size: 11))
                        .foregroundStyle(Theme.ink.opacity(0.5))
                }
                Text(reply.content)
                    .font(.system(size: 14))
                    .foregroundStyle(Theme.ink.opacity(0.8))
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}

#Preview {
    ScrollView {
        PostCard(post: GalleryPost.sample[0]) {}
            .padding()
    }
    .background(Theme.page)
}
