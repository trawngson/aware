import SwiftUI

struct AvatarView: View {
    let size: CGFloat
    let systemName: String
    let tint: Color
    let assetName: String?

    init(size: CGFloat, systemName: String, tint: Color, assetName: String? = nil) {
        self.size = size
        self.systemName = systemName
        self.tint = tint
        self.assetName = assetName
    }

    var body: some View {
        Circle()
            .fill(tint.opacity(0.25))
            .frame(width: size, height: size)
            .overlay(avatarContent)
            .clipShape(Circle())
    }

    @ViewBuilder
    private var avatarContent: some View {
        if let assetName {
            Image(assetName)
                .resizable()
                .scaledToFill()
        } else {
            Image(systemName: systemName)
                .font(.system(size: size * 0.5))
                .foregroundStyle(tint)
        }
    }
}

#Preview {
    HStack(spacing: 16) {
        AvatarView(size: 44, systemName: "face.smiling.fill", tint: .green)
        AvatarView(size: 44, systemName: "face.dashed", tint: .blue)
        AvatarView(size: 44, systemName: "face.smiling.inverse", tint: .purple)
    }
    .padding()
}
