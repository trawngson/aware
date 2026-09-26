import PhotosUI
import SwiftUI

/// A single post with all of its replies and a reply field.
struct PostThreadView: View {
    let postID: UUID

    @ObservedObject private var store = GalleryStore.shared
    @ObservedObject private var session = AppSession.shared
    @Environment(\.dismiss) private var dismiss
    @State private var replyText = ""
    @State private var photoItem: PhotosPickerItem?
    @State private var replyImage: UIImage?
    @State private var isSending = false
    @State private var isShowingTerms = false
    @FocusState private var isReplyFocused: Bool

    var body: some View {
        Group {
            if let post = store.post(id: postID) {
                thread(post)
            } else {
                ContentUnavailableView("Post not found", systemImage: "photo")
            }
        }
        .background { ForestBackdrop.feed }
        .forestNavigationBar("Post")
        .task { await store.loadReplies(for: postID) }
        // Deleted, or its author blocked: go back to the feed.
        .onChange(of: store.post(id: postID) == nil) { _, isGone in
            if isGone { dismiss() }
        }
        .sheet(isPresented: $isShowingTerms) {
            CommunityTermsSheet {
                if let post = store.post(id: postID) { send(post) }
            }
        }
    }

    private func thread(_ post: GalleryPost) -> some View {
        ScrollViewReader { proxy in
        TabScrollView {
            VStack(alignment: .leading, spacing: 14) {
                postCard(post)

                if !post.replies.isEmpty {
                    VStack(alignment: .leading, spacing: 12) {
                        SectionLabel(title: "^[\(post.replies.count) reply](inflect: true)")
                        VStack(spacing: 10) {
                            ForEach(post.replies) { reply in
                                ReplyBubble(reply: reply, postID: post.id)
                                    .id(reply.id)
                            }
                        }
                        .padding(.leading, 14)
                        .overlay(alignment: .leading) {
                            RoundedRectangle(cornerRadius: 1)
                                .fill(Theme.ink.opacity(0.14))
                                .frame(width: 2)
                                .padding(.vertical, 8)
                        }
                    }
                    .padding(.leading, 2)
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 6)
            .padding(.bottom, 16)
        }
        .scrollIndicators(.hidden)
        .scrollDismissesKeyboard(.interactively)
        .safeAreaInset(edge: .bottom) { replyBar(post) }
        .onChange(of: post.replies.count) { oldCount, newCount in
            guard newCount > oldCount, let last = post.replies.last else { return }
            withAnimation(.snappy) { proxy.scrollTo(last.id, anchor: .bottom) }
        }
        }
    }

    private func postCard(_ post: GalleryPost) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            PostAuthorRow(post: post, avatarSize: 44)
            if post.isHiddenForReview {
                HiddenForReviewNote()
            }
            Text(post.content)
                .font(.system(size: 15))
                .lineSpacing(4)
                .foregroundStyle(Theme.ink)
                .fixedSize(horizontal: false, vertical: true)
            if post.hasAttachment {
                PostImage(post: post, height: 260, cornerRadius: 18)
            }
            HStack(spacing: 20) {
                let liked = store.likedPostIDs.contains(post.id)
                let saved = store.savedPostIDs.contains(post.id)
                statButton(liked ? "heart.fill" : "heart", count: store.likeCounts[post.id] ?? post.likes,
                           tint: liked ? Theme.heart : nil) { store.toggleLike(post.id) }
                    .accessibilityLabel(liked ? "Unlike" : "Like")
                statButton("bubble.left", count: post.comments) { isReplyFocused = true }
                    .accessibilityLabel("Reply")
                statButton(saved ? "bookmark.fill" : "bookmark", count: store.savedCounts[post.id] ?? post.saved,
                           tint: saved ? Theme.amber : nil) { store.toggleSave(post.id) }
                    .accessibilityLabel(saved ? "Remove bookmark" : "Bookmark")
                Spacer(minLength: 0)
                ShareLink(item: post.content) {
                    HStack(spacing: 5) {
                        Image(systemName: "square.and.arrow.up").font(.system(size: 17))
                        if post.shares > 0 { Text("\(post.shares)") }
                    }
                }
                .accessibilityLabel("Share")
            }
            .font(.system(size: 14))
            .foregroundStyle(Theme.ink.opacity(0.6))
        }
        .padding(16)
        .glass(.cardStrong, cornerRadius: 26)
    }

    private func statButton(_ systemImage: String, count: Int, tint: Color? = nil,
                            action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 5) {
                Image(systemName: systemImage).font(.system(size: 17))
                Text(AwareFormat.grouped(count)).contentTransition(.numericText())
            }
            .foregroundStyle(tint ?? Theme.ink.opacity(0.6))
        }
        .buttonStyle(.plain)
        .animation(.snappy, value: count)
    }

    // MARK: - Reply bar

    private var canSend: Bool {
        !isSending && (!replyText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || replyImage != nil)
    }

    private func replyBar(_ post: GalleryPost) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            if let replyImage {
                Image(uiImage: replyImage)
                    .resizable()
                    .scaledToFill()
                    .frame(width: 64, height: 64)
                    .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                    .overlay(alignment: .topTrailing) {
                        Button {
                            self.replyImage = nil
                            photoItem = nil
                        } label: {
                            Image(systemName: "xmark.circle.fill")
                                .symbolRenderingMode(.palette)
                                .foregroundStyle(.white, .black.opacity(0.5))
                        }
                        .offset(x: 6, y: -6)
                        .accessibilityLabel("Remove photo")
                    }
                    .padding(.leading, 42)
            }
            HStack(spacing: 10) {
                MemberAvatar(member: Community.current, size: 32)
                HStack(spacing: 8) {
                    TextField("", text: $replyText,
                              prompt: Text("Add a reply…").foregroundStyle(Theme.ink.opacity(0.45)),
                              axis: .vertical)
                        .lineLimit(1...4)
                        .font(.system(size: 15))
                        .foregroundStyle(Theme.ink)
                        .tint(Theme.green)
                        .focused($isReplyFocused)
                        .environment(\.colorScheme, .light)
                    if isSending {
                        ProgressView()
                    } else if canSend {
                        Button { send(post) } label: {
                            Image(systemName: "arrow.up.circle.fill")
                                .font(.system(size: 24))
                                .foregroundStyle(Theme.green)
                        }
                        .accessibilityLabel("Send reply")
                    } else {
                        PhotosPicker(selection: $photoItem, matching: .images) {
                            Image(systemName: "camera")
                                .font(.system(size: 18))
                                .foregroundStyle(Theme.green)
                        }
                        .accessibilityLabel("Add photo")
                    }
                }
                .padding(.leading, 14)
                .padding(.trailing, 10)
                .padding(.vertical, 8)
                .frame(minHeight: 40)
                .glass(.cardStrong, cornerRadius: 20)
            }
        }
        .padding(.horizontal, 16)
        .padding(.top, 8)
        .padding(.bottom, 6)
        .background {
            LinearGradient(stops: [.init(color: Theme.mist.opacity(0), location: 0),
                                   .init(color: Theme.mist.opacity(0.94), location: 0.35)],
                           startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea()
        }
        .onChange(of: photoItem) { _, item in
            Task {
                guard let data = try? await item?.loadTransferable(type: Data.self) else { return }
                replyImage = UIImage(data: data)
            }
        }
    }

    private func send(_ post: GalleryPost) {
        // Replies to real posts are public, so the terms come first.
        if post.remote != nil && !session.hasAcceptedTerms {
            isShowingTerms = true
            return
        }
        let text = replyText.trimmingCharacters(in: .whitespacesAndNewlines)
        isSending = true
        Task {
            let sent = await store.reply(to: post.id, content: text, image: replyImage)
            isSending = false
            guard sent else { return }
            withAnimation(.snappy) {
                replyText = ""
                replyImage = nil
                photoItem = nil
            }
            isReplyFocused = false
        }
    }
}

private struct ReplyBubble: View {
    let reply: GalleryReply
    let postID: UUID

    @ObservedObject private var store = GalleryStore.shared
    @State private var isReporting = false
    @State private var isConfirmingBlock = false

    var body: some View {
        bubble
            .contextMenu {
                if store.isMine(reply.author) {
                    Button(role: .destructive) {
                        Task { await store.delete(reply, in: postID) }
                    } label: {
                        Label("Delete Reply", systemImage: "trash")
                    }
                } else {
                    Button {
                        isReporting = true
                    } label: {
                        Label("Report Reply", systemImage: "flag")
                    }
                    Button(role: .destructive) {
                        isConfirmingBlock = true
                    } label: {
                        Label("Block \(reply.author.shortName)", systemImage: "hand.raised")
                    }
                }
            }
            .reportDialog(isPresented: $isReporting) { reason in
                Task { await store.report(replyID: reply.id, reason: reason) }
            }
            .confirmationDialog(Text("Block \(reply.author.shortName)?"), isPresented: $isConfirmingBlock,
                                titleVisibility: .visible) {
                Button("Block", role: .destructive) {
                    Task { await store.block(reply.author) }
                }
            } message: {
                Text("You won't see their posts or replies anymore. You can unblock them in More.")
            }
    }

    private var bubble: some View {
        HStack(alignment: .top, spacing: 10) {
            MemberAvatar(member: reply.author, size: 30)
            VStack(alignment: .leading, spacing: 3) {
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    Text(reply.author.name)
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(Theme.ink)
                    Text(reply.time)
                        .font(.system(size: 12))
                        .foregroundStyle(Theme.ink.opacity(0.5))
                }
                if !reply.content.isEmpty {
                    Text(reply.content)
                        .font(.system(size: 14))
                        .lineSpacing(2)
                        .foregroundStyle(Theme.ink)
                        .fixedSize(horizontal: false, vertical: true)
                }
                if reply.isHiddenForReview {
                    HiddenForReviewNote()
                }
                if let image = reply.image {
                    Image(uiImage: image)
                        .resizable()
                        .scaledToFill()
                        .frame(maxWidth: 180, maxHeight: 180)
                        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                        .padding(.top, 4)
                } else if let url = reply.imageURL {
                    RemotePhoto(url: url)
                        .frame(width: 180, height: 180)
                        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                        .padding(.top, 4)
                }
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .glass(GlassStyle(top: 0.74, bottom: 0.56, border: 0.8, highlight: 0.9, material: nil,
                          shadow: Color(hex: 0x143A22, opacity: 0.07), shadowRadius: 8, shadowY: 6),
               cornerRadius: 20)
    }
}

#Preview {
    NavigationStack {
        PostThreadView(postID: GalleryPost.SampleID.fabricLamp)
    }
    .preferredColorScheme(.dark)
}
