import CoreLocation
import SwiftUI

/// A composer draft started from a scan result ("Add to Gallery").
struct ScanPostDraft: Identifiable {
    let id = UUID()
    let text: String
    let image: UIImage?
}

/// Shows `GalleryMessage`s from one place (`ContentView`), so a screen that
/// appears in two tabs (a post thread) never presents the same alert twice.
@MainActor
final class MessageCenter: ObservableObject {
    static let shared = MessageCenter()
    @Published var message: GalleryMessage?

    func show(_ message: GalleryMessage) {
        self.message = message
    }
}

/// A short message after a Gallery action: a thank-you, or why it failed.
struct GalleryMessage: Identifiable, Equatable {
    let id = UUID()
    let title: String
    let text: String

    static func failure(_ error: Error) -> GalleryMessage {
        switch error as? BackendError {
        case .unreachable:
            GalleryMessage(title: String(localized: "You're offline"),
                           text: String(localized: "This needs an internet connection. Try again when you're back online."))
        case .contentNotAllowed:
            GalleryMessage(title: String(localized: "Let's keep it friendly"),
                           text: String(localized: "Some words in there aren't allowed in the community. Please reword it and try again."))
        case .rejected:
            GalleryMessage(title: String(localized: "That didn't work"),
                           text: String(localized: "Your account can't do that right now."))
        default:
            GalleryMessage(title: String(localized: "Something went wrong"),
                           text: String(localized: "Please try again in a moment."))
        }
    }

    static let reported = GalleryMessage(
        title: String(localized: "Thanks for telling us"),
        text: String(localized: "We'll take a look. You won't see it here anymore."))
}

/// The Gallery's posts: real ones from the backend, newest first (the last
/// fetched ones are kept on the phone for offline use), followed by the
/// built-in sample posts while samples are on. Without a backend, posts made
/// in the app stay on the phone for the session, as before.
@MainActor
class GalleryStore: ObservableObject {
    static let shared = GalleryStore()

    /// Samples, and posts made without a backend.
    @Published private(set) var localPosts: [GalleryPost] = GalleryPost.sample
    /// Real posts, newest first.
    @Published private(set) var remotePosts: [RemotePost] = []
    /// Full reply threads loaded for real posts.
    @Published private(set) var remoteReplies: [UUID: [RemoteReply]] = [:]
    /// Real posts opened from the map that aren't in the feed.
    @Published private(set) var openedPosts: [UUID: RemotePost] = [:]
    @Published var likedPostIDs: Set<UUID> = []
    @Published var likeCounts: [UUID: Int] = [:]
    @Published var savedPostIDs: Set<UUID> = []
    @Published var savedCounts: [UUID: Int] = [:]
    /// Posts and replies the user reported, and authors they blocked (sample
    /// people included), hidden on this phone.
    @Published private(set) var hiddenIDs: Set<UUID> = []
    @Published private(set) var hiddenAuthorIDs: Set<String> = []
    @Published private(set) var canLoadMore = false
    /// A draft from "Add to Gallery" on a scan result, for the Gallery tab to open.
    @Published var scanDraft: ScanPostDraft?

    private let session: AppSession
    private var backend: CommunityBackend { session.backend }
    private let store: LocalStore
    private let defaults: UserDefaults
    private var isRefreshing = false

    private static let pageSize = 30
    private static let cacheKey = "gallery.feed.v1"
    private static let hiddenKey = "gallery.hiddenIDs.v1"
    private static let hiddenAuthorsKey = "gallery.hiddenAuthors.v1"

    private init(session: AppSession = .shared, store: LocalStore = .shared, defaults: UserDefaults = .standard) {
        self.session = session
        self.store = store
        self.defaults = defaults
        likeCounts = Dictionary(uniqueKeysWithValues: localPosts.map { ($0.id, $0.likes) })
        savedCounts = Dictionary(uniqueKeysWithValues: localPosts.map { ($0.id, $0.saved) })
        hiddenIDs = Set((defaults.stringArray(forKey: Self.hiddenKey) ?? []).compactMap(UUID.init(uuidString:)))
        hiddenAuthorIDs = Set(defaults.stringArray(forKey: Self.hiddenAuthorsKey) ?? [])
        if session.isBackendConfigured, let data = store.cachedContent(Self.cacheKey),
           let cached = try? JSONDecoder().decode([RemotePost].self, from: data) {
            apply(cached, replacing: true)
        }
    }

    // MARK: - Reading

    /// The feed: real posts first, then samples (while they show).
    var posts: [GalleryPost] {
        let visibleLocal = localPosts.filter(isVisible)
        guard session.isBackendConfigured else { return visibleLocal }
        let real = remotePosts.map(galleryPost).filter(isVisible)
        return real + (session.showSamples ? visibleLocal : [])
    }

    /// A post that may show (not reported or blocked on this phone).
    func post(id: UUID) -> GalleryPost? {
        if let remote = remotePosts.first(where: { $0.id == id }) ?? openedPosts[id] {
            let post = galleryPost(remote)
            return isVisible(post) ? post : nil
        }
        return localPosts.first { $0.id == id && isVisible($0) }
    }

    func isRemote(_ id: UUID) -> Bool {
        remotePosts.contains { $0.id == id } || openedPosts[id] != nil
    }

    /// True for the user's own posts and replies.
    func isMine(_ author: CommunityMember) -> Bool {
        author.id == Community.current.id
    }

    private func isVisible(_ post: GalleryPost) -> Bool {
        !hiddenIDs.contains(post.id) && !hiddenAuthorIDs.contains(post.author.id)
    }

    private func galleryPost(_ remote: RemotePost) -> GalleryPost {
        let replies = (remoteReplies[remote.id] ?? remote.replies ?? [])
            .map(galleryReply)
            .filter { !hiddenIDs.contains($0.id) && !hiddenAuthorIDs.contains($0.author.id) }
        return GalleryPost(
            id: remote.id,
            author: member(remote.author),
            time: Self.age(of: remote.createdAt),
            title: remote.title,
            content: remote.body,
            likes: remote.likeCount,
            saved: remote.saveCount,
            tag: remote.material.flatMap(MaterialTag.init(rawValue:)),
            replies: replies,
            attachmentURL: remote.imagePath.flatMap { backend.imageURL(for: $0) },
            remote: remote
        )
    }

    private func galleryReply(_ remote: RemoteReply) -> GalleryReply {
        GalleryReply(id: remote.id, author: member(remote.author), time: Self.age(of: remote.createdAt),
                     content: remote.body, imageURL: remote.imagePath.flatMap { backend.imageURL(for: $0) },
                     remote: remote)
    }

    private func member(_ author: PostAuthor) -> CommunityMember {
        let current = Community.current
        if author.id.uuidString.lowercased() == current.id { return current }
        return CommunityMember(author: author)
    }

    /// "Just now", "5m", "3h", "2d", then the date.
    static func age(of date: Date, now: Date = .now) -> String {
        let seconds = max(0, now.timeIntervalSince(date))
        switch seconds {
        case ..<60: return String(localized: "Just now")
        case ..<3_600: return "\(Int(seconds / 60))m"
        case ..<86_400: return "\(Int(seconds / 3_600))h"
        case ..<604_800: return "\(Int(seconds / 86_400))d"
        default: return date.formatted(.dateTime.day().month(.abbreviated))
        }
    }

    // MARK: - Fetching

    /// Fetches the newest posts and the user's likes and saves. Offline, the
    /// cached posts stay.
    func refresh() async {
        guard session.isBackendConfigured, !isRefreshing else { return }
        isRefreshing = true
        defer { isRefreshing = false }
        do {
            let page = try await backend.fetchFeed(before: nil, limit: Self.pageSize)
            let reactions = try await backend.fetchMyReactions()
            apply(page, replacing: true)
            let localIDs = Set(localPosts.map(\.id))
            likedPostIDs = reactions.liked.union(likedPostIDs.intersection(localIDs))
            savedPostIDs = reactions.saved.union(savedPostIDs.intersection(localIDs))
            canLoadMore = page.count == Self.pageSize
            saveCache()
        } catch {
            // Offline or server trouble: keep showing what we have.
        }
    }

    /// Fetches older posts after the last one shown.
    func loadMore() async {
        guard session.isBackendConfigured, canLoadMore, !isRefreshing, let last = remotePosts.last else { return }
        isRefreshing = true
        defer { isRefreshing = false }
        do {
            let page = try await backend.fetchFeed(before: last.createdAt, limit: Self.pageSize)
            apply(page, replacing: false)
            canLoadMore = page.count == Self.pageSize
        } catch {
            canLoadMore = false
        }
    }

    /// Loads a real post that isn't in the feed (opened from the map).
    func loadPost(_ id: UUID) async {
        guard session.isBackendConfigured, post(id: id) == nil else { return }
        if let post = try? await backend.fetchPost(id) {
            openedPosts[id] = post
            likeCounts[id] = post.likeCount
            savedCounts[id] = post.saveCount
        }
    }

    /// Loads every reply of a real post.
    func loadReplies(for postID: UUID) async {
        guard isRemote(postID) else { return }
        do {
            remoteReplies[postID] = try await backend.fetchReplies(postID: postID)
        } catch {
            // The first replies from the feed stay.
        }
    }

    private func apply(_ page: [RemotePost], replacing: Bool) {
        if replacing {
            remotePosts = page
        } else {
            let known = Set(remotePosts.map(\.id))
            remotePosts += page.filter { !known.contains($0.id) }
        }
        for post in page {
            likeCounts[post.id] = post.likeCount
            savedCounts[post.id] = post.saveCount
        }
    }

    private func saveCache() {
        if let data = try? JSONEncoder().encode(remotePosts) {
            store.saveContent(data, for: Self.cacheKey)
        }
    }

    // MARK: - Posting

    /// Adds a post on the phone only (no backend, or a sample thread).
    func addPost(_ post: GalleryPost) {
        localPosts.insert(post, at: 0)
        likeCounts[post.id] = post.likes
        savedCounts[post.id] = post.saved
    }

    /// Creates a post by the current user from the composer. With a backend it
    /// is uploaded (photo first). Returns why it failed, or nil. The community
    /// terms must already be accepted.
    func publish(content: String, image: UIImage?, tag: MaterialTag?,
                 location: CLLocationCoordinate2D? = nil) async -> GalleryMessage? {
        guard session.isBackendConfigured else {
            addPost(GalleryPost(author: Community.current, time: String(localized: "Just now"),
                                content: content, tag: tag, attachmentImage: image))
            return nil
        }
        do {
            var imagePath: String?
            if let image, let jpeg = ImageUpload.jpeg(from: image) {
                imagePath = try await backend.uploadImage(jpeg)
            }
            // The database rounds the location to about 500 m.
            let post = try await backend.createPost(PostDraft(title: nil, body: content, material: tag?.rawValue,
                                                              imagePath: imagePath, latitude: location?.latitude,
                                                              longitude: location?.longitude))
            remotePosts.insert(post, at: 0)
            likeCounts[post.id] = 0
            savedCounts[post.id] = 0
            saveCache()
            if location != nil {
                Task { await MapStore.shared.refresh() }
            }
            return nil
        } catch {
            return .failure(error)
        }
    }

    /// Starts a post from a scan result. Without a backend the post is added
    /// straight away, as before; with one, the Gallery opens the composer so
    /// the user can check it before it goes public.
    func addPostFromScan(image: UIImage?, itemName: String, leafPoints: Int) {
        let text = String(localized: "I just scanned and sorted: \(itemName) 🌱♻️")
        if session.isBackendConfigured {
            scanDraft = ScanPostDraft(text: text, image: image)
        } else {
            addPost(GalleryPost(author: Community.current, time: String(localized: "Just now"),
                                content: text, attachmentImage: image))
        }
    }

    /// Adds a reply. Real posts get it on the server (terms already accepted);
    /// samples and local posts keep it on the phone. Returns false, after
    /// showing why, if that failed.
    func reply(to postID: UUID, content: String, image: UIImage?) async -> Bool {
        guard isRemote(postID) else {
            addLocalReply(to: postID, content: content, image: image)
            return true
        }
        do {
            var imagePath: String?
            if let image, let jpeg = ImageUpload.jpeg(from: image) {
                imagePath = try await backend.uploadImage(jpeg)
            }
            let reply = try await backend.createReply(postID: postID, body: content, imagePath: imagePath)
            remoteReplies[postID, default: remotePosts.first { $0.id == postID }?.replies ?? []].append(reply)
            if let index = remotePosts.firstIndex(where: { $0.id == postID }) {
                remotePosts[index].replyCount += 1
            }
            return true
        } catch {
            MessageCenter.shared.show(.failure(error))
            return false
        }
    }

    private func addLocalReply(to postID: UUID, content: String, image: UIImage?) {
        guard let index = localPosts.firstIndex(where: { $0.id == postID }) else { return }
        localPosts[index].replies.append(GalleryReply(
            author: Community.current,
            time: String(localized: "Just now"),
            content: content,
            image: image
        ))
    }

    /// Deletes the user's own post (and its photos).
    func delete(_ post: GalleryPost) async {
        guard let remote = post.remote else {
            localPosts.removeAll { $0.id == post.id }
            return
        }
        do {
            try await backend.deletePost(remote)
            remotePosts.removeAll { $0.id == post.id }
            saveCache()
        } catch {
            MessageCenter.shared.show(.failure(error))
        }
    }

    /// Deletes the user's own reply.
    func delete(_ reply: GalleryReply, in postID: UUID) async {
        guard let remote = reply.remote else {
            if let index = localPosts.firstIndex(where: { $0.id == postID }) {
                localPosts[index].replies.removeAll { $0.id == reply.id }
            }
            return
        }
        do {
            try await backend.deleteReply(remote)
            remoteReplies[postID]?.removeAll { $0.id == reply.id }
            if let index = remotePosts.firstIndex(where: { $0.id == postID }) {
                remotePosts[index].replies?.removeAll { $0.id == reply.id }
                remotePosts[index].replyCount = max(0, remotePosts[index].replyCount - 1)
            }
        } catch {
            MessageCenter.shared.show(.failure(error))
        }
    }

    // MARK: - Reactions

    func toggleLike(_ id: UUID) {
        let liked = !likedPostIDs.contains(id)
        setLocally(liked, id, in: \.likedPostIDs, counts: \.likeCounts)
        guard isRemote(id) else { return }
        Task {
            do {
                try await backend.setLiked(liked, postID: id)
            } catch {
                setLocally(!liked, id, in: \.likedPostIDs, counts: \.likeCounts)
                MessageCenter.shared.show(.failure(error))
            }
        }
    }

    func toggleSave(_ id: UUID) {
        let saved = !savedPostIDs.contains(id)
        setLocally(saved, id, in: \.savedPostIDs, counts: \.savedCounts)
        guard isRemote(id) else { return }
        Task {
            do {
                try await backend.setSaved(saved, postID: id)
            } catch {
                setLocally(!saved, id, in: \.savedPostIDs, counts: \.savedCounts)
                MessageCenter.shared.show(.failure(error))
            }
        }
    }

    private func setLocally(_ on: Bool, _ id: UUID,
                            in set: ReferenceWritableKeyPath<GalleryStore, Set<UUID>>,
                            counts: ReferenceWritableKeyPath<GalleryStore, [UUID: Int]>) {
        guard self[keyPath: set].contains(id) != on else { return }
        if on {
            self[keyPath: set].insert(id)
            self[keyPath: counts][id] = (self[keyPath: counts][id] ?? 0) + 1
        } else {
            self[keyPath: set].remove(id)
            self[keyPath: counts][id] = max(0, (self[keyPath: counts][id] ?? 0) - 1)
        }
    }

    // MARK: - Moderation

    /// Reports a post or reply and hides it on this phone. Sample content is
    /// only hidden.
    func report(postID: UUID? = nil, replyID: UUID? = nil, reason: String) async {
        let target: ReportTarget
        let id: UUID
        let isReal: Bool
        if let postID {
            target = .post(postID)
            id = postID
            isReal = isRemote(postID)
        } else if let replyID {
            target = .reply(replyID)
            id = replyID
            isReal = isRemoteReply(replyID)
        } else {
            return
        }
        if isReal {
            do {
                try await backend.report(target, reason: reason)
            } catch {
                MessageCenter.shared.show(.failure(error))
                return
            }
        }
        hide(id)
        MessageCenter.shared.show(.reported)
    }

    /// Blocks a person: their posts and replies disappear. Sample people are
    /// hidden on this phone only.
    func block(_ member: CommunityMember) async {
        if session.isBackendConfigured, let userID = UUID(uuidString: member.id) {
            do {
                try await backend.block(userID)
            } catch {
                MessageCenter.shared.show(.failure(error))
                return
            }
            remotePosts.removeAll { $0.author.id == userID }
            saveCache()
        }
        hiddenAuthorIDs.insert(member.id)
        defaults.set(Array(hiddenAuthorIDs), forKey: Self.hiddenAuthorsKey)
    }

    /// Shows a person's content again after unblocking them in settings.
    func unblocked(_ userID: UUID) {
        hiddenAuthorIDs.remove(userID.uuidString.lowercased())
        defaults.set(Array(hiddenAuthorIDs), forKey: Self.hiddenAuthorsKey)
        Task { await refresh() }
    }

    private func isRemoteReply(_ id: UUID) -> Bool {
        remoteReplies.values.contains { $0.contains { $0.id == id } }
            || remotePosts.contains { $0.replies?.contains { $0.id == id } ?? false }
    }

    private func hide(_ id: UUID) {
        hiddenIDs.insert(id)
        defaults.set(hiddenIDs.map(\.uuidString), forKey: Self.hiddenKey)
    }

    /// Forgets everything cached on this phone (after deleting the account).
    func reset() {
        remotePosts = []
        remoteReplies = [:]
        likedPostIDs = []
        savedPostIDs = []
        hiddenIDs = []
        hiddenAuthorIDs = []
        defaults.removeObject(forKey: Self.hiddenKey)
        defaults.removeObject(forKey: Self.hiddenAuthorsKey)
        store.deleteCachedContent()
    }
}

extension CommunityMember {
    /// A real post or reply author, with their points when the leaderboard
    /// has them.
    @MainActor
    init(author: PostAuthor) {
        let points = LeaderboardStore.shared.allTimeRows.first { $0.userID == author.id }?.points ?? 0
        self.init(
            id: author.id.uuidString.lowercased(),
            name: author.displayName,
            shortName: author.displayName,
            points: points,
            avatar: .initials(author.avatarInitials,
                              top: Color(hex: UInt32(clamping: author.avatarTop)),
                              bottom: Color(hex: UInt32(clamping: author.avatarBottom)))
        )
    }
}

/// Photos for upload: at most 1,600 px on the long side, as JPEG, and well
/// under the bucket's 5 MB limit.
enum ImageUpload {
    static let maxDimension: CGFloat = 1_600
    static let maxBytes = 4_500_000

    static func jpeg(from image: UIImage) -> Data? {
        let longest = max(image.size.width, image.size.height)
        let scale = longest > maxDimension ? maxDimension / longest : 1
        let size = CGSize(width: (image.size.width * scale).rounded(), height: (image.size.height * scale).rounded())
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        let resized = UIGraphicsImageRenderer(size: size, format: format).image { _ in
            image.draw(in: CGRect(origin: .zero, size: size))
        }
        for quality in [0.8, 0.6, 0.4] {
            if let data = resized.jpegData(compressionQuality: quality), data.count <= maxBytes {
                return data
            }
        }
        return nil
    }
}
