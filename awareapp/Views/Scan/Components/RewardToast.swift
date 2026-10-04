import SwiftUI

/// Shows "+20 leaves" at the top of every tab for a moment when a scan earns
/// points, with a success haptic.
struct RewardToastHost: View {
    @ObservedObject private var ledger = RewardLedger.shared
    @State private var shown: AwardedScan?

    private let duration: Duration = .seconds(2.5)

    var body: some View {
        // A clear base keeps the host on screen while no toast is showing.
        Color.clear
            .overlay(alignment: .top) {
                if let shown {
                    RewardToast(award: shown)
                        .transition(.move(edge: .top).combined(with: .opacity))
                }
            }
            .animation(.spring(response: 0.4, dampingFraction: 0.8), value: shown)
            .allowsHitTesting(false)
            .sensoryFeedback(.success, trigger: shown?.id) { _, new in new != nil }
            .onChange(of: ledger.awards.last) { _, award in
                if let award { shown = award }
            }
            .task(id: shown?.id) {
                guard shown != nil else { return }
                try? await Task.sleep(for: duration)
                guard !Task.isCancelled else { return }
                shown = nil
            }
    }
}

struct RewardToast: View {
    let award: AwardedScan

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: "leaf.fill")
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(Theme.green)
                .frame(width: 34, height: 34)
                .background(Circle().fill(.white))
            VStack(alignment: .leading, spacing: 1) {
                Text("+\(award.points) leaves")
                    .font(.system(size: 16, weight: .bold))
                    .tracking(-0.3)
                Text("\(award.displayName) sorted")
                    .font(.system(size: 13, weight: .medium))
                    .opacity(0.85)
                    .lineLimit(1)
            }
        }
        .foregroundStyle(.white)
        .padding(.leading, 6)
        .padding(.trailing, 20)
        .padding(.vertical, 6)
        .background(Capsule().fill(Theme.primaryGradient))
        .overlay(Capsule().strokeBorder(.white.opacity(0.3), lineWidth: 0.5))
        .shadow(color: Theme.green.opacity(0.35), radius: 12, y: 8)
        .padding(.top, 6)
        .accessibilityElement(children: .combine)
    }
}

#Preview {
    RewardToast(award: AwardedScan(id: UUID(), label: .plasticBottle, displayName: "Plastic bottle",
                                   group: .recyclable, points: 20, date: .now))
        .padding()
        .background(Theme.scanDark)
}
