import SwiftUI

// MARK: - Stat Card

struct StatCardView: View {
    let stat: InsightStat
    
    @State private var appeared = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: stat.icon)
                    .font(.subheadline)
                    .foregroundStyle(stat.color)
                Text(stat.title)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            
            Text(stat.value)
                .font(.title2.weight(.bold))
            
            HStack(spacing: 4) {
                Image(systemName: stat.trendUp ? "arrow.up.right" : "arrow.down.right")
                    .font(.caption.weight(.semibold))
                Text(stat.trend)
                    .font(.caption.weight(.semibold))
            }
            .foregroundStyle(stat.trendUp ? .green : .red)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(.ultraThinMaterial)
        )
        .scaleEffect(appeared ? 1 : 0.9)
        .opacity(appeared ? 1 : 0)
        .onAppear {
            withAnimation(.spring(response: 0.5, dampingFraction: 0.7)) {
                appeared = true
            }
        }
    }
}

// MARK: - Preview

#Preview {
    StatCardView(stat: InsightStat(
        title: "This Week",
        value: "2.4kg",
        trend: "+12%",
        trendUp: true,
        icon: "leaf.fill",
        color: .green
    ))
    .padding()
}
