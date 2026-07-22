import SwiftUI
import PhotosUI
import AudioToolbox

struct PostComposerCard: View {
    @Binding var posts: [GalleryPost]
    
    @State private var isExpanded = false
    @State private var postContent = ""
    @State private var selectedImage: UIImage?
    @State private var showingImagePicker = false
    @State private var isPosting = false
    
    // Current user info (placeholder - would come from user profile)
    private let currentUserName = "You"
    private let currentUserLeafCount = "1,400"
    private let currentUserAvatarSymbol = "person.fill"
    private let currentUserAvatarColor = Color.green
    
    var body: some View {
        VStack(spacing: 12) {
            // Header row
            if isExpanded {
                expandedHeader
                expandedContent
            } else {
                Button {
                    withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                        isExpanded = true
                    }
                } label: {
                    collapsedHeader
                }
                .buttonStyle(.plain)
            }
        }
        .padding()
        .background(CardBackground())
        .sheet(isPresented: $showingImagePicker) {
            ImagePicker(image: $selectedImage)
        }
    }
    
    // MARK: - Collapsed Header
    
    private var collapsedHeader: some View {
        HStack(spacing: 12) {
            AvatarView(
                size: 44,
                systemName: currentUserAvatarSymbol,
                tint: currentUserAvatarColor
            )
            
            Text("What's new?")
                .foregroundStyle(.secondary)
            
            Spacer()
            
            Text("Post")
                .font(.headline)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Color(uiColor: .systemGray5))
                .clipShape(Capsule())
        }
    }
    
    // MARK: - Expanded Header
    
    private var expandedHeader: some View {
        HStack(spacing: 12) {
            AvatarView(
                size: 44,
                systemName: currentUserAvatarSymbol,
                tint: currentUserAvatarColor
            )
            
            VStack(alignment: .leading, spacing: 2) {
                Text(currentUserName)
                    .font(.headline)
                HStack(spacing: 4) {
                    Text(currentUserLeafCount)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    Image(systemName: "leaf.fill")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }
            Spacer()
        }
    }
    
    // MARK: - Expanded Content
    
    private var expandedContent: some View {
        VStack(spacing: 12) {
            // Text input - placeholder behind, TextEditor on top
            ZStack(alignment: .topLeading) {
                // Placeholder (rendered first = behind)
                if postContent.isEmpty {
                    Text("Share your recycling journey...")
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 16)
                }
                
                // TextEditor (rendered second = on top, receives touches)
                TextEditor(text: $postContent)
                    .scrollContentBackground(.hidden)
                    .frame(minHeight: 80)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
            }
            .background(Color(uiColor: .systemGray6))
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            
            // Selected image preview
            if let image = selectedImage {
                ZStack(alignment: .topTrailing) {
                    Image(uiImage: image)
                        .resizable()
                        .scaledToFill()
                        .frame(height: 200)
                        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                    
                    Button {
                        withAnimation {
                            selectedImage = nil
                        }
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .font(.title2)
                            .foregroundStyle(.white)
                            .shadow(radius: 2)
                    }
                    .padding(8)
                }
            }
            
            // Action buttons
            HStack(spacing: 12) {
                // Add photo button
                Button {
                    showingImagePicker = true
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "photo.badge.plus")
                        Text("Photo")
                    }
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(Color(uiColor: .systemGray6))
                    .clipShape(Capsule())
                }
                
                Spacer()
                
                // Cancel button
                Button("Cancel") {
                    withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                        isExpanded = false
                        postContent = ""
                        selectedImage = nil
                    }
                }
                .font(.subheadline.weight(.medium))
                .foregroundStyle(.secondary)
                
                // Post button
                Button {
                    createPost()
                } label: {
                    HStack(spacing: 6) {
                        if isPosting {
                            ProgressView()
                                .scaleEffect(0.8)
                        } else {
                            Text("Post")
                        }
                    }
                    .font(.headline)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 20)
                    .padding(.vertical, 10)
                    .background(canPost ? Color.green : Color.gray)
                    .clipShape(Capsule())
                }
                .disabled(!canPost || isPosting)
            }
        }
        .transition(.opacity.combined(with: .move(edge: .top)))
    }
    
    private var canPost: Bool {
        !postContent.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || selectedImage != nil
    }
    
    private func createPost() {
        guard canPost else { return }
        
        isPosting = true
        
        // Play post sound effect
        AudioServicesPlaySystemSound(1004) // "Sent" sound
        
        // Simulate network delay
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            let newPost = GalleryPost(
                userName: currentUserName,
                time: "Just now",
                content: postContent,
                likes: 0,
                comments: 0,
                saved: 0,
                shares: "",
                hasAttachment: selectedImage != nil,
                showTranslate: false,
                avatarSymbol: currentUserAvatarSymbol,
                avatarColor: currentUserAvatarColor,
                leafCount: currentUserLeafCount,
                replies: [],
                avatarAssetName: nil,
                attachmentAssetName: nil,
                attachmentImage: selectedImage
            )
            
            withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                posts.insert(newPost, at: 0)
                isExpanded = false
                postContent = ""
                selectedImage = nil
                isPosting = false
            }
        }
    }
}

// MARK: - Image Picker

struct ImagePicker: UIViewControllerRepresentable {
    @Binding var image: UIImage?
    @Environment(\.dismiss) private var dismiss
    
    func makeUIViewController(context: Context) -> PHPickerViewController {
        var config = PHPickerConfiguration()
        config.filter = .images
        config.selectionLimit = 1
        
        let picker = PHPickerViewController(configuration: config)
        picker.delegate = context.coordinator
        return picker
    }
    
    func updateUIViewController(_ uiViewController: PHPickerViewController, context: Context) {}
    
    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }
    
    class Coordinator: NSObject, PHPickerViewControllerDelegate {
        let parent: ImagePicker
        
        init(_ parent: ImagePicker) {
            self.parent = parent
        }
        
        func picker(_ picker: PHPickerViewController, didFinishPicking results: [PHPickerResult]) {
            parent.dismiss()
            
            guard let provider = results.first?.itemProvider,
                  provider.canLoadObject(ofClass: UIImage.self) else { return }
            
            provider.loadObject(ofClass: UIImage.self) { image, _ in
                DispatchQueue.main.async {
                    self.parent.image = image as? UIImage
                }
            }
        }
    }
}

#Preview {
    struct PreviewWrapper: View {
        @State private var posts = GalleryPost.sample
        
        var body: some View {
            PostComposerCard(posts: $posts)
                .padding()
        }
    }
    
    return PreviewWrapper()
}
