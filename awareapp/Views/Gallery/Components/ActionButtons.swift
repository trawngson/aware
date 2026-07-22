import SwiftUI

struct LikeButton: View {
    let isLiked: Bool
    let count: Int
    let onToggleLike: () -> Void

    @State private var isAnimating = false

    var body: some View {
        Button(action: handleTap) {
            HStack(spacing: 6) {
                Image(systemName: isLiked ? "heart.fill" : "heart")
                    .scaleEffect(isAnimating ? 1.2 : 1.0)
                    .opacity(isAnimating ? 0.9 : 1.0)
                Text(CountFormatter.format(count))
            }
        }
        .buttonStyle(.plain)
        .foregroundStyle(isLiked ? .red : .secondary)
        .accessibilityLabel(isLiked ? "Unlike" : "Like")
    }

    private func handleTap() {
        onToggleLike()
        withAnimation(.spring(response: 0.3, dampingFraction: 0.55)) {
            isAnimating = true
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
            withAnimation(.spring(response: 0.3, dampingFraction: 0.75)) {
                isAnimating = false
            }
        }
    }
}

struct SaveButton: View {
    let isSaved: Bool
    let count: Int
    let onToggleSave: () -> Void

    @State private var isAnimating = false

    var body: some View {
        Button(action: handleTap) {
            HStack(spacing: 6) {
                Image(systemName: isSaved ? "bookmark.fill" : "bookmark")
                    .scaleEffect(isAnimating ? 1.15 : 1.0)
                    .opacity(isAnimating ? 0.9 : 1.0)
                Text(CountFormatter.format(count))
            }
        }
        .buttonStyle(.plain)
        .foregroundStyle(isSaved ? .yellow : .secondary)
        .accessibilityLabel(isSaved ? "Remove bookmark" : "Bookmark")
    }

    private func handleTap() {
        onToggleSave()
        withAnimation(.spring(response: 0.3, dampingFraction: 0.6)) {
            isAnimating = true
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
            withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                isAnimating = false
            }
        }
    }
}

struct ActionPill: View {
    let systemName: String
    let value: Int

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: systemName)
            Text(CountFormatter.format(value))
        }
    }
}

#Preview {
    HStack(spacing: 20) {
        LikeButton(isLiked: true, count: 2000, onToggleLike: {})
        ActionPill(systemName: "bubble.left", value: 5)
        SaveButton(isSaved: false, count: 100, onToggleSave: {})
    }
    .font(.subheadline)
    .foregroundStyle(.secondary)
    .padding()
}
