import SwiftUI

/// Shared data store for passing data between tabs
@MainActor
class GalleryStore: ObservableObject {
    static let shared = GalleryStore()

    @Published private(set) var posts: [GalleryPost] = GalleryPost.sample
    @Published var likedPostIDs: Set<UUID> = []
    @Published var likeCounts: [UUID: Int] = [:]
    @Published var savedPostIDs: Set<UUID> = []
    @Published var savedCounts: [UUID: Int] = [:]

    private init() {
        likeCounts = Dictionary(uniqueKeysWithValues: posts.map { ($0.id, $0.likes) })
        savedCounts = Dictionary(uniqueKeysWithValues: posts.map { ($0.id, $0.saved) })
    }

    func post(id: UUID) -> GalleryPost? {
        posts.first { $0.id == id }
    }

    func addPost(_ post: GalleryPost) {
        posts.insert(post, at: 0)
        likeCounts[post.id] = post.likes
        savedCounts[post.id] = post.saved
    }

    /// Creates a post by the current user from the composer.
    func addPost(content: String, image: UIImage?, tag: MaterialTag?) {
        addPost(GalleryPost(
            author: Community.me,
            time: String(localized: "Just now"),
            content: content,
            tag: tag,
            attachmentImage: image
        ))
    }

    /// Creates and adds a post from scan results
    func addPostFromScan(image: UIImage?, itemName: String, leafPoints: Int) {
        addPost(GalleryPost(
            author: Community.me,
            time: String(localized: "Just now"),
            content: String(localized: "I just scanned and sorted: \(itemName) 🌱♻️"),
            attachmentImage: image
        ))
    }

    func addReply(to postID: UUID, content: String, image: UIImage?) {
        guard let index = posts.firstIndex(where: { $0.id == postID }) else { return }
        posts[index].replies.append(GalleryReply(
            author: Community.me,
            time: String(localized: "Just now"),
            content: content,
            image: image
        ))
    }

    func toggleLike(_ id: UUID) {
        if likedPostIDs.contains(id) {
            likedPostIDs.remove(id)
            likeCounts[id] = max(0, (likeCounts[id] ?? 0) - 1)
        } else {
            likedPostIDs.insert(id)
            likeCounts[id] = (likeCounts[id] ?? 0) + 1
        }
    }

    func toggleSave(_ id: UUID) {
        if savedPostIDs.contains(id) {
            savedPostIDs.remove(id)
            savedCounts[id] = max(0, (savedCounts[id] ?? 0) - 1)
        } else {
            savedPostIDs.insert(id)
            savedCounts[id] = (savedCounts[id] ?? 0) + 1
        }
    }
}
