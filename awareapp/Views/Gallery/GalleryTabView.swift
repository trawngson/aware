import SwiftUI

struct GalleryTabView: View {
    @ObservedObject private var store = GalleryStore.shared

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                PostComposerCard(posts: $store.posts)
                
                ForEach(store.posts) { post in
                    let postId = post.id
                    PostCard(
                        post: post,
                        isLiked: store.likedPostIDs.contains(postId),
                        likeCount: store.likeCounts[postId] ?? post.likes,
                        isSaved: store.savedPostIDs.contains(postId),
                        savedCount: store.savedCounts[postId] ?? post.saved,
                        onToggleLike: { [postId] in store.toggleLike(postId) },
                        onToggleSave: { [postId] in store.toggleSave(postId) }
                    )
                }
                
                Text("You've reached the end of the feed. Come back again soon?")
                    .foregroundStyle(.secondary)
            }
            .padding(.horizontal)
            .padding(.top, 8)
            .padding(.bottom, 24)
        }
        .background(feedBackground)
    }

    // MARK: - Background
    
    private var feedBackground: some View {
        ZStack(alignment: .top) {
            Color(uiColor: .systemGroupedBackground)
            LinearGradient(
                stops: [
                    .init(color: Color.green.opacity(0.35), location: 0.0),
                    .init(color: Color.green.opacity(0.2), location: 0.15),
                    .init(color: Color.green.opacity(0.0), location: 0.3)
                ],
                startPoint: .top,
                endPoint: .bottom
            )
        }
        .ignoresSafeArea()
    }
}

#Preview {
    GalleryTabView()
}
