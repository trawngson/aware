import AudioToolbox
import PhotosUI
import SwiftUI

/// Full-screen composer for a Gallery post.
struct NewPostView: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject private var store = GalleryStore.shared

    @State private var text = ""
    @State private var image: UIImage?
    @State private var photoItem: PhotosPickerItem?
    @State private var tag: MaterialTag?
    @FocusState private var isEditorFocused: Bool

    private var canPost: Bool {
        !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || image != nil
    }

    private var hasSteps: Bool {
        text.contains("\n1. ") || text.hasPrefix("1. ")
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    TextField("", text: $text,
                              prompt: Text("Share what you made…").foregroundStyle(Theme.ink.opacity(0.4)),
                              axis: .vertical)
                        .font(.system(size: 16))
                        .lineSpacing(4)
                        .foregroundStyle(Theme.ink)
                        .focused($isEditorFocused)

                    if let image {
                        attachedImage(image)
                    }

                    if let tag {
                        tagChip(tag)
                    }

                    if !hasSteps {
                        stepsSuggestion
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, 14)
                .padding(.bottom, 10)
            }
            .scrollDismissesKeyboard(.interactively)
            .safeAreaInset(edge: .bottom) { accessoryChips }
            .background(Theme.page.ignoresSafeArea())
            .navigationTitle("New Post")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                        .tint(Theme.ink.opacity(0.7))
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Post", action: post)
                        .buttonStyle(.borderedProminent)
                        .buttonBorderShape(.capsule)
                        .tint(Theme.green)
                        .disabled(!canPost)
                }
            }
        }
        .tint(Theme.green)
        .lightSheetAppearance()
        .onAppear { isEditorFocused = true }
        .onChange(of: photoItem) { _, item in
            Task {
                guard let data = try? await item?.loadTransferable(type: Data.self) else { return }
                withAnimation(.snappy) { image = UIImage(data: data) }
            }
        }
    }

    // MARK: - Pieces

    private func attachedImage(_ image: UIImage) -> some View {
        Image(uiImage: image)
            .resizable()
            .scaledToFill()
            .frame(maxWidth: .infinity)
            .frame(height: 240)
            .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
            .overlay(alignment: .topTrailing) {
                Button {
                    withAnimation(.snappy) {
                        self.image = nil
                        photoItem = nil
                    }
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 24))
                        .symbolRenderingMode(.palette)
                        .foregroundStyle(.white, .black.opacity(0.45))
                }
                .padding(10)
                .accessibilityLabel("Remove photo")
            }
    }

    private func tagChip(_ tag: MaterialTag) -> some View {
        HStack(spacing: 6) {
            Image(systemName: "tag.fill").font(.system(size: 12))
            Text(tag.title)
            Button {
                withAnimation(.snappy) { self.tag = nil }
            } label: {
                Image(systemName: "xmark").font(.system(size: 10, weight: .bold))
            }
            .accessibilityLabel("Remove tag")
        }
        .font(.system(size: 13, weight: .semibold))
        .foregroundStyle(tag.tint)
        .padding(.horizontal, 12)
        .padding(.vertical, 7)
        .background(Capsule().fill(tag.tint.opacity(0.12)))
    }

    private var stepsSuggestion: some View {
        HStack(spacing: 10) {
            IconTile(systemImage: "sparkles", size: 28, cornerRadius: 10, iconSize: 14)
            VStack(alignment: .leading, spacing: 1) {
                Text("Add some instructions?")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(Theme.ink)
                Text("Posts with steps get 3× more saves")
                    .font(.system(size: 12))
                    .foregroundStyle(Theme.ink.opacity(0.58))
            }
            Spacer(minLength: 0)
            Button(action: addSteps) {
                PillButtonLabel(title: "Add", fontSize: 13, horizontal: 13, vertical: 6)
            }
            .buttonStyle(PressableStyle())
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .background(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .fill(LinearGradient(colors: [.white.opacity(0.72), .white.opacity(0.5)], startPoint: .top, endPoint: .bottom))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .strokeBorder(Theme.green.opacity(0.45), style: StrokeStyle(lineWidth: 0.75, dash: [4, 3]))
        )
    }

    private var accessoryChips: some View {
        ScrollView(.horizontal) {
            HStack(spacing: 8) {
                PhotosPicker(selection: $photoItem, matching: .images) {
                    chipLabel("Add image", systemImage: "photo.badge.plus", tint: Theme.green)
                }
                Menu {
                    ForEach(MaterialTag.allCases) { option in
                        Button {
                            withAnimation(.snappy) { tag = option }
                        } label: {
                            if option == tag {
                                Label(option.title, systemImage: "checkmark")
                            } else {
                                Text(option.title)
                            }
                        }
                    }
                } label: {
                    chipLabel("Tag", systemImage: "tag", tint: Theme.ink.opacity(0.72))
                }
                Button(action: addSteps) {
                    chipLabel("Steps", systemImage: "list.number", tint: Theme.ink.opacity(0.72))
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
        }
        .scrollIndicators(.hidden)
    }

    private func chipLabel(_ title: LocalizedStringKey, systemImage: String, tint: Color) -> some View {
        Label(title, systemImage: systemImage)
            .font(.system(size: 13, weight: .semibold))
            .foregroundStyle(tint)
            .padding(.horizontal, 14)
            .padding(.vertical, 9)
            .glassCapsule(.chrome)
    }

    // MARK: - Actions

    private func addSteps() {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if hasSteps {
            let count = text.components(separatedBy: "\n").filter { $0.range(of: #"^\d+\. "#, options: .regularExpression) != nil }.count
            text = trimmed + "\n\(count + 1). "
        } else {
            text = trimmed.isEmpty ? "1. " : trimmed + "\n\n1. "
        }
        isEditorFocused = true
    }

    private func post() {
        guard canPost else { return }
        AudioServicesPlaySystemSound(1004) // "Sent" sound
        withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
            store.addPost(content: text.trimmingCharacters(in: .whitespacesAndNewlines), image: image, tag: tag)
        }
        dismiss()
    }
}

#Preview {
    NewPostView()
}
