import SwiftUI

struct CategoryPill: View {
    let icon: String
    let text: String
    let color: Color
    
    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .foregroundStyle(color)
            Text(text)
                .foregroundStyle(color)
        }
        .font(.subheadline)
        .fontWeight(.medium)
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(color.opacity(0.12))
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

#Preview {
    HStack {
        CategoryPill(icon: "tag.fill", text: "Plastic", color: .purple)
        CategoryPill(icon: "leaf.fill", text: "25", color: .green)
    }
    .padding()
}
