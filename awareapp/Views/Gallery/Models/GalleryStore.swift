import SwiftUI

/// Shared data store for passing data between tabs
@MainActor
class GalleryStore: ObservableObject {
    static let shared = GalleryStore()
    
    @Published var posts: [GalleryPost] = GalleryPost.sample {
        didSet {
            // Initialize counts for any new posts
            for post in posts {
                if likeCounts[post.id] == nil {
                    likeCounts[post.id] = post.likes
                }
                if savedCounts[post.id] == nil {
                    savedCounts[post.id] = post.saved
                }
            }
        }
    }
    @Published var likedPostIDs: Set<UUID> = []
    @Published var likeCounts: [UUID: Int] = [:]
    @Published var savedPostIDs: Set<UUID> = []
    @Published var savedCounts: [UUID: Int] = [:]
    
    // Pending attachment for post composer (set from scan results)
    @Published var pendingAttachmentImage: UIImage?
    @Published var pendingItemName: String?
    @Published var shouldExpandComposer: Bool = false
    
    private init() {
        initializeCounts()
    }
    
    func initializeCounts() {
        if likeCounts.isEmpty {
            likeCounts = Dictionary(uniqueKeysWithValues: posts.map { ($0.id, $0.likes) })
        }
        if savedCounts.isEmpty {
            savedCounts = Dictionary(uniqueKeysWithValues: posts.map { ($0.id, $0.saved) })
        }
    }
    
    func addPost(_ post: GalleryPost) {
        posts.insert(post, at: 0)
        likeCounts[post.id] = post.likes
        savedCounts[post.id] = post.saved
    }
    
    /// Creates and adds a post from scan results
    func addPostFromScan(image: UIImage?, itemName: String, leafPoints: Int) {
        let newPost = GalleryPost(
            userName: "You",
            time: "Just now",
            content: "I just scanned and recycled a \(itemName)! 🌱♻️",
            likes: 0,
            comments: 0,
            saved: 0,
            shares: "",
            hasAttachment: image != nil,
            showTranslate: false,
            avatarSymbol: "person.fill",
            avatarColor: .green,
            leafCount: "1,400",
            replies: [],
            avatarAssetName: nil,
            attachmentAssetName: nil,
            attachmentImage: image
        )
        addPost(newPost)
    }
    
    /// Sets a pending attachment from scan results to be added to post composer
    func setPendingAttachment(image: UIImage?, itemName: String) {
        pendingAttachmentImage = image
        pendingItemName = itemName
        shouldExpandComposer = true
    }
    
    /// Clears pending attachment after it's been consumed by the composer
    func clearPendingAttachment() {
        pendingAttachmentImage = nil
        pendingItemName = nil
        shouldExpandComposer = false
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
