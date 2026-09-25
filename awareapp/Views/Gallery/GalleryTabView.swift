import SwiftUI

struct GalleryTabView: View {
    @ObservedObject private var store = GalleryStore.shared
    @State private var isComposing = false
    @State private var openedPostID: UUID?

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(spacing: 14) {
                    composerRow

                    ForEach(store.posts) { post in
                        PostCard(post: post) { openedPostID = post.id }
                    }

                    Text("You've reached the end of the feed. Come back again soon?")
                        .font(.system(size: 14))
                        .foregroundStyle(Theme.ink.opacity(0.5))
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 20)
                        .padding(.vertical, 4)
                }
                .padding(.horizontal, 16)
                .padding(.top, 4)
                .padding(.bottom, 20)
            }
            .scrollIndicators(.hidden)
            .background { ForestBackdrop.feed }
            .navigationTitle("Gallery")
            .toolbarColorScheme(.dark, for: .navigationBar)
            .navigationDestination(item: $openedPostID) { id in
                PostThreadView(postID: id)
            }
            .fullScreenCover(isPresented: $isComposing) {
                NewPostView()
            }
        }
        .tint(.white)
    }

    // MARK: - Composer

    private var composerRow: some View {
        Button {
            isComposing = true
        } label: {
            HStack(spacing: 10) {
                MemberAvatar(member: Community.me, size: 38, borderColor: .white.opacity(0.8), borderWidth: 1.5)
                Text("Share what you made…")
                    .font(.system(size: 15))
                    .foregroundStyle(Theme.ink.opacity(0.6))
                Spacer(minLength: 0)
                PillButtonLabel(title: "Post")
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .glass(GlassStyle(top: 0.52, bottom: 0.34, border: 0.6, highlight: 0.7, material: .ultraThinMaterial,
                              shadow: Color(hex: 0x081C10, opacity: 0.14), shadowRadius: 12, shadowY: 10),
                   cornerRadius: 22)
            .contentShape(RoundedRectangle(cornerRadius: 22))
        }
        .buttonStyle(PressableStyle())
    }
}

#Preview {
    GalleryTabView()
}
