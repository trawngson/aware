import SwiftUI

struct GalleryTabView: View {
    /// What the composer opens with: empty, or a draft from a scan.
    private struct Composer: Identifiable {
        let id = UUID()
        var draft: ScanPostDraft?
    }

    @ObservedObject private var store = GalleryStore.shared
    @ObservedObject private var session = AppSession.shared
    @State private var composer: Composer?
    @State private var openedPostID: UUID?

    var body: some View {
        NavigationStack {
            TabScrollView {
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
                        .onAppear { Task { await store.loadMore() } }
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
            .fullScreenCover(item: $composer) { composer in
                NewPostView(initialText: composer.draft?.text ?? "", initialImage: composer.draft?.image)
            }
            .task { await store.refresh() }
            .refreshable { await store.refresh() }
            .onAppear(perform: openScanDraft)
            .onChange(of: store.scanDraft?.id) { _, _ in openScanDraft() }
        }
        .tint(.white)
    }

    /// "Add to Gallery" on a scan result: open the composer with its photo.
    private func openScanDraft() {
        guard let draft = store.scanDraft else { return }
        store.scanDraft = nil
        composer = Composer(draft: draft)
    }

    // MARK: - Composer

    private var composerRow: some View {
        Button {
            composer = Composer()
        } label: {
            HStack(spacing: 10) {
                MemberAvatar(member: Community.current, size: 38, borderColor: .white.opacity(0.8), borderWidth: 1.5)
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
