import SwiftUI

// MARK: - Pulsing Viewfinder

struct PulsingViewfinder: View {
    @State private var isPulsing = false
    
    var body: some View {
        Image(systemName: "viewfinder")
            .font(.system(size: 64, weight: .thin))
            .foregroundStyle(.white.opacity(0.6))
            .scaleEffect(isPulsing ? 1.1 : 1.0)
            .opacity(isPulsing ? 0.8 : 0.6)
            .onAppear {
                withAnimation(
                    .easeInOut(duration: 1.2)
                    .repeatForever(autoreverses: true)
                ) {
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
