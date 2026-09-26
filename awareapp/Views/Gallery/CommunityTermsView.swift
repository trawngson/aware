import SwiftUI

/// The short community rules. Shown once, before the first post or reply
/// (App Store guideline 1.2), and on the guidelines screen in More.
enum CommunityRules {
    static var rules: [(icon: String, text: String)] {
        [
            ("heart.fill", String(localized: "Be kind. No bullying, hate or harassment.")),
            ("arrow.3.trianglepath", String(localized: "Keep it about recycling, upcycling and caring for the planet.")),
            ("photo.fill", String(localized: "Only share photos you took, and never anyone's personal details.")),
            ("megaphone.fill", String(localized: "No ads or spam.")),
            ("flag.fill", String(localized: "Posts that break these rules get hidden, and people who keep breaking them can't post anymore.")),
        ]
    }
}

/// "Before you post": the rules and an "I agree" button. Calls `onAgree` once
/// the server has recorded the acceptance.
struct CommunityTermsSheet: View {
    var onAgree: () -> Void

    @Environment(\.dismiss) private var dismiss
    @ObservedObject private var session = AppSession.shared
    @State private var isSaving = false
    @State private var failure: GalleryMessage?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Our community is a friendly place to share what you made. Before your first post, please agree to a few simple rules:")
                        .font(.system(size: 15))
                        .foregroundStyle(Theme.ink.opacity(0.8))
                        .fixedSize(horizontal: false, vertical: true)
                    CommunityRulesList()
                    NavigationLink {
                        CommunityGuidelinesView()
                    } label: {
                        Label("Read the community guidelines", systemImage: "doc.text")
                            .font(.system(size: 14, weight: .semibold))
                    }
                }
                .padding(20)
            }
            .safeAreaInset(edge: .bottom) {
                Button(action: agree) {
                    if isSaving {
                        ProgressView().tint(.white)
                    } else {
                        Text("I agree")
                    }
                }
                .buttonStyle(PrimaryButtonStyle())
                .disabled(isSaving)
                .padding(.horizontal, 20)
                .padding(.bottom, 8)
            }
            .background(Theme.page.ignoresSafeArea())
            .navigationTitle("Before you post")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Not now") { dismiss() }
                }
            }
            .alert(failure?.title ?? "", isPresented: Binding(get: { failure != nil }, set: { if !$0 { failure = nil } }),
                   presenting: failure) { _ in
                Button("OK") {}
            } message: { failure in
                Text(failure.text)
            }
        }
        .tint(Theme.green)
        .lightSheetAppearance()
        .presentationDetents([.large])
    }

    private func agree() {
        isSaving = true
        Task {
            do {
                try await session.acceptTerms()
                isSaving = false
                dismiss()
                onAgree()
            } catch {
                isSaving = false
                failure = .failure(error)
            }
        }
    }
}

struct CommunityRulesList: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ForEach(CommunityRules.rules, id: \.icon) { rule in
                HStack(alignment: .top, spacing: 12) {
                    IconTile(systemImage: rule.icon, size: 30, cornerRadius: 10, iconSize: 14)
                    Text(rule.text)
                        .font(.system(size: 15))
                        .foregroundStyle(Theme.ink)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: 0)
                }
            }
        }
        .padding(16)
        .glass(.card, cornerRadius: 22)
    }
}

/// The community guidelines in full, with how reporting and blocking work.
struct CommunityGuidelinesView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                CommunityRulesList()
                VStack(alignment: .leading, spacing: 10) {
                    Text("If something isn't right")
                        .font(.system(size: 17, weight: .semibold))
                        .foregroundStyle(Theme.ink)
                    Text("Tap ••• on a post, or press and hold a reply, to report it or to block its author. When a few people report the same post, it's hidden until someone from AWARE looks at it. Blocked people's posts and replies disappear for you, and you can unblock them in More.")
                        .font(.system(size: 15))
                        .foregroundStyle(Theme.ink.opacity(0.8))
                        .fixedSize(horizontal: false, vertical: true)
                    Text("Your posts show your display name, never your email or location. Photos you share can be seen by everyone using AWARE.")
                        .font(.system(size: 15))
                        .foregroundStyle(Theme.ink.opacity(0.8))
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(16)
                .glass(.card, cornerRadius: 22)
            }
            .padding(20)
        }
        .background(Theme.page.ignoresSafeArea())
        .navigationTitle("Community guidelines")
        .navigationBarTitleDisplayMode(.inline)
    }
}

/// People the user blocked, with a way to unblock them.
struct BlockedPeopleView: View {
    @ObservedObject private var session = AppSession.shared
    @State private var people: [PostAuthor] = []
    @State private var isLoading = true
    @State private var failed = false

    var body: some View {
        List {
            if isLoading {
                ProgressView().frame(maxWidth: .infinity)
            } else if failed {
                Text("Couldn't load this list. Check your connection and try again.")
                    .foregroundStyle(Theme.ink.opacity(0.6))
            } else if people.isEmpty {
                Text("You haven't blocked anyone.")
                    .foregroundStyle(Theme.ink.opacity(0.6))
            }
            ForEach(people, id: \.id) { person in
                HStack(spacing: 12) {
                    MemberAvatar(member: CommunityMember(author: person), size: 34)
                    Text(person.displayName).foregroundStyle(Theme.ink)
                    Spacer()
                    Button("Unblock") { unblock(person) }
                        .buttonStyle(.bordered)
                        .tint(Theme.green)
                }
            }
        }
        .environment(\.colorScheme, .light)
        .navigationTitle("Blocked people")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
        .refreshable { await load() }
    }

    private func load() async {
        do {
            people = try await session.backend.fetchBlockedUsers()
            failed = false
        } catch {
            failed = true
        }
        isLoading = false
    }

    private func unblock(_ person: PostAuthor) {
        Task {
            do {
                try await session.backend.unblock(person.id)
                people.removeAll { $0.id == person.id }
                GalleryStore.shared.unblocked(person.id)
            } catch {
                MessageCenter.shared.show(.failure(error))
            }
        }
    }
}
