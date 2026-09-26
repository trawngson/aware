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

            if post.isHiddenForReview {
                HiddenForReviewNote()
            }

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
                    if post.comments > previewReplies {
                        Text("View all \(post.comments) replies")
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

    @ObservedObject private var store = GalleryStore.shared
    @State private var isReporting = false
    @State private var isConfirmingBlock = false
    @State private var isConfirmingDelete = false

    var body: some View {
        let isMine = store.isMine(post.author)
        let points = post.author.id == Community.current.id ? Community.myPoints : post.author.points
        HStack(spacing: 10) {
            MemberAvatar(member: post.author, size: avatarSize)
            VStack(alignment: .leading, spacing: 1) {
                Text(post.author.name)
                    .font(.system(size: avatarSize > 40 ? 16 : 15, weight: .semibold))
                    .foregroundStyle(Theme.ink)
                HStack(spacing: 4) {
                    if points > 0 {
                        LeafAmount(value: points, size: 12, color: Theme.ink.opacity(0.55))
                        Text("· \(post.time)")
                            .font(.system(size: 12))
                            .foregroundStyle(Theme.ink.opacity(0.55))
                    } else {
                        Text(post.time)
                            .font(.system(size: 12))
                            .foregroundStyle(Theme.ink.opacity(0.55))
                    }
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
                if isMine {
                    Button(role: .destructive) {
                        isConfirmingDelete = true
                    } label: {
                        Label("Delete Post", systemImage: "trash")
                    }
                } else {
                    Button {
                        isReporting = true
                    } label: {
                        Label("Report Post", systemImage: "flag")
                    }
                    Button(role: .destructive) {
                        isConfirmingBlock = true
                    } label: {
                        Label("Block \(post.author.shortName)", systemImage: "hand.raised")
                    }
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
        .reportDialog(isPresented: $isReporting) { reason in
            Task { await store.report(postID: post.id, reason: reason) }
        }
        .confirmationDialog(Text("Block \(post.author.shortName)?"), isPresented: $isConfirmingBlock,
                            titleVisibility: .visible) {
            Button("Block", role: .destructive) {
                Task { await store.block(post.author) }
            }
        } message: {
            Text("You won't see their posts or replies anymore. You can unblock them in More.")
        }
        .confirmationDialog(Text("Delete this post?"), isPresented: $isConfirmingDelete, titleVisibility: .visible) {
            Button("Delete", role: .destructive) {
                Task { await store.delete(post) }
            }
        } message: {
            Text("It will be removed for everyone, with its photo and replies.")
        }
    }
}

/// Shown on the user's own post or reply while it is hidden after reports.
struct HiddenForReviewNote: View {
    var body: some View {
        Label("Hidden while we take a look", systemImage: "eye.slash")
            .font(.system(size: 13, weight: .semibold))
            .foregroundStyle(Theme.orangeDeep)
    }
}

extension View {
    /// Asks why something is being reported, then calls `onReport` with the reason.
    func reportDialog(isPresented: Binding<Bool>, onReport: @escaping (String) -> Void) -> some View {
        confirmationDialog(Text("Why are you reporting this?"), isPresented: isPresented, titleVisibility: .visible) {
            Button("It's mean or hurtful") { onReport("hurtful") }
            Button("It's spam or an ad") { onReport("spam") }
            Button("It shares someone's personal details") { onReport("personal_details") }
            Button("Something else") { onReport("other") }
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
                } else if let url = post.attachmentURL {
                    RemotePhoto(url: url)
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

/// A photo stored on the backend, with a quiet placeholder while it loads or
/// when the phone is offline.
struct RemotePhoto: View {
    let url: URL

    var body: some View {
        AsyncImage(url: url) { phase in
            if let image = phase.image {
                image.resizable().scaledToFill()
            } else if phase.error != nil {
                Image(systemName: "photo")
                    .font(.system(size: 28))
                    .foregroundStyle(Theme.ink.opacity(0.25))
            } else {
                ProgressView()
            }
        }
    }
}
