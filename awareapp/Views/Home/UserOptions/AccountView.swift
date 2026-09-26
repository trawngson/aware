import AuthenticationServices
import CryptoKit
import SwiftUI

/// More → Account, only with a backend: the display name, Sign in with Apple
/// (so a guest keeps everything when changing phones) and deleting the account.
struct AccountView: View {
    @ObservedObject private var session = AppSession.shared
    @State private var name = ""
    @State private var isSaving = false
    @State private var isWorking = false
    @State private var isConfirmingDelete = false
    /// The Apple ID's token, kept while asking whether to switch to its account.
    @State private var existingAccount: AppleCredential?
    /// The raw nonce for the Sign in with Apple request in flight.
    @State private var nonce = ""

    private static let nameLimit = 40

    private var trimmedName: String { name.trimmingCharacters(in: .whitespacesAndNewlines) }
    private var canSaveName: Bool {
        !trimmedName.isEmpty && trimmedName.count <= Self.nameLimit
            && trimmedName != session.profile?.displayName && !isSaving
    }

    var body: some View {
        List {
            Section {
                HStack(spacing: 12) {
                    TextField("Display name", text: $name)
                        .textInputAutocapitalization(.words)
                        .submitLabel(.done)
                        .onSubmit(saveName)
                        .foregroundStyle(Theme.ink)
                    if isSaving {
                        ProgressView()
                    } else {
                        Button("Save", action: saveName)
                            .buttonStyle(.bordered)
                            .tint(Theme.green)
                            .disabled(!canSaveName)
                    }
                }
            } header: {
                sectionHeader("Name")
            } footer: {
                Text("Shown on your posts, replies and the leaderboard.")
            }

            Section {
                if session.isGuest {
                    Text("You're using AWARE as a guest. Sign in with Apple to keep your scans, points and posts if you change or reset your phone.")
                        .font(.system(size: 15))
                        .foregroundStyle(Theme.ink.opacity(0.8))
                        .fixedSize(horizontal: false, vertical: true)
                    SignInWithAppleButton(.signIn) { request in
                        nonce = Self.randomNonce()
                        request.requestedScopes = []
                        request.nonce = Self.sha256(nonce)
                    } onCompletion: { result in
                        handleApple(result)
                    }
                    .signInWithAppleButtonStyle(.black)
                    .frame(height: 46)
                    .disabled(isWorking)
                } else {
                    Label("Signed in with Apple", systemImage: "checkmark.seal.fill")
                        .foregroundStyle(Theme.ink)
                }
            } header: {
                sectionHeader("Sign in")
            }

            Section {
                Button(role: .destructive) {
                    isConfirmingDelete = true
                } label: {
                    HStack {
                        Text("Delete account")
                        Spacer()
                        if isWorking { ProgressView() }
                    }
                }
                .disabled(isWorking)
            } footer: {
                Text("Removes your scans, points, posts, replies and photos from AWARE.")
            }
        }
        .environment(\.colorScheme, .light)
        .navigationTitle("Account")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear { name = session.profile?.displayName ?? "" }
        .onChange(of: session.profile?.displayName) { _, newName in
            if !isSaving, let newName { name = newName }
        }
        .confirmationDialog("Delete your account?", isPresented: $isConfirmingDelete, titleVisibility: .visible) {
            Button("Delete account", role: .destructive, action: deleteAccount)
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Your scans, points, posts, replies and photos will be removed for good. This can't be undone.")
        }
        .alert("This Apple ID already has an account",
               isPresented: Binding(get: { existingAccount != nil }, set: { if !$0 { existingAccount = nil } }),
               presenting: existingAccount) { credential in
            Button("Switch account") { switchAccount(credential) }
            Button("Cancel", role: .cancel) {}
        } message: { _ in
            Text("Switch to it? Scans already saved to this guest account stay with the guest account.")
        }
    }

    private func sectionHeader(_ title: LocalizedStringKey) -> some View {
        Text(title)
            .font(.system(size: 13, weight: .semibold))
            .foregroundStyle(Theme.ink.opacity(0.5))
    }

    // MARK: - Actions

    private func saveName() {
        guard canSaveName else { return }
        isSaving = true
        Task {
            do {
                try await session.rename(to: trimmedName)
            } catch {
                MessageCenter.shared.show(.failure(error))
            }
            isSaving = false
            name = session.profile?.displayName ?? name
        }
    }

    private func handleApple(_ result: Result<ASAuthorization, Error>) {
        switch result {
        case .failure(let error):
            // Cancelling isn't an error worth a message.
            if (error as? ASAuthorizationError)?.code != .canceled {
                MessageCenter.shared.show(.appleSignInFailed)
            }
        case .success(let authorization):
            guard let credential = authorization.credential as? ASAuthorizationAppleIDCredential,
                  let tokenData = credential.identityToken,
                  let token = String(data: tokenData, encoding: .utf8) else {
                MessageCenter.shared.show(.appleSignInFailed)
                return
            }
            let apple = AppleCredential(idToken: token, nonce: nonce)
            isWorking = true
            Task {
                do {
                    try await session.linkApple(idToken: apple.idToken, nonce: apple.nonce)
                } catch BackendError.identityInUse {
                    existingAccount = apple
                } catch {
                    MessageCenter.shared.show(.failure(error))
                }
                isWorking = false
            }
        }
    }

    private func switchAccount(_ credential: AppleCredential) {
        isWorking = true
        Task {
            do {
                try await session.switchToApple(idToken: credential.idToken, nonce: credential.nonce)
            } catch {
                MessageCenter.shared.show(.failure(error))
            }
            isWorking = false
        }
    }

    private func deleteAccount() {
        isWorking = true
        Task {
            do {
                try await session.deleteAccount()
                await NotificationManager.shared.forgetToken()
                MessageCenter.shared.show(.accountDeleted)
            } catch {
                MessageCenter.shared.show(.failure(error))
            }
            isWorking = false
        }
    }

    // MARK: - Nonce

    /// A random string sent (hashed) to Apple and (raw) to the server, which
    /// checks they match, so a stolen token can't be replayed.
    private static func randomNonce(length: Int = 32) -> String {
        let characters = Array("0123456789ABCDEFGHIJKLMNOPQRSTUVXYZabcdefghijklmnopqrstuvwxyz-._")
        var generator = SystemRandomNumberGenerator()
        return String((0..<length).map { _ in characters.randomElement(using: &generator)! })
    }

    private static func sha256(_ input: String) -> String {
        SHA256.hash(data: Data(input.utf8)).map { String(format: "%02x", $0) }.joined()
    }
}

/// An Apple ID token and the nonce it was requested with.
struct AppleCredential: Equatable {
    let idToken: String
    let nonce: String
}

extension GalleryMessage {
    static let appleSignInFailed = GalleryMessage(
        title: String(localized: "Couldn't sign in with Apple"),
        text: String(localized: "Please try again in a moment."))

    static let accountDeleted = GalleryMessage(
        title: String(localized: "Account deleted"),
        text: String(localized: "Everything in your account was removed. You can keep using AWARE as a new guest."))
}
