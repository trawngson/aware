import SwiftUI

// MARK: - Pulsing Viewfinder

/// Corner brackets shown while nothing is detected.
struct PulsingViewfinder: View {
    @State private var isPulsing = false
    
    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: "viewfinder")
                .font(.system(size: 120, weight: .ultraLight))
                .foregroundStyle(.white.opacity(0.75))
                .scaleEffect(isPulsing ? 1.06 : 1.0)
                .opacity(isPulsing ? 0.9 : 0.6)
            Text("Point at an object")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.white)
                .padding(.horizontal, 14)
                .padding(.vertical, 8)
                .glassCapsule(.dark)
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 1.2).repeatForever(autoreverses: true)) {
                isPulsing = true
            }
        }
    }
}

// MARK: - Preview

#Preview {
    ZStack {
        Color.black
        PulsingViewfinder()
    }
}
