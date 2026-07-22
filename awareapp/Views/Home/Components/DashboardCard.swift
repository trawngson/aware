import SwiftUI

// MARK: - Base Dashboard Card

struct DashboardCard<Content: View>: View {
    let content: Content
    
    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }
    
    var body: some View {
        content
            .padding()
            .frame(maxWidth: .infinity, minHeight: 140, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .fill(.thickMaterial)
            )
    }
}

// MARK: - Card Header

struct CardHeader: View {
    let icon: String
    let title: String
    let iconColor: Color
    let subtitle: String?
    let showChevron: Bool
    
    init(icon: String, title: String, iconColor: Color, subtitle: String? = nil, showChevron: Bool = true) {
        self.icon = icon
        self.title = title
        self.iconColor = iconColor
        self.subtitle = subtitle
        self.showChevron = showChevron
    }
    
    var body: some View {
        HStack {
            Image(systemName: icon)
                .foregroundStyle(iconColor)
            Text(title)
                .font(.headline)
                .foregroundStyle(iconColor)
            Spacer()
            if let subtitle {
                Text(subtitle)
                    .foregroundStyle(.secondary)
            }
            if showChevron {
                Image(systemName: "chevron.right")
                    .foregroundStyle(.secondary)
            }
        }
    }
}

// MARK: - Trend Indicator

struct TrendIndicator: View {
    let value: String
    let isPositive: Bool
    
    var body: some View {
        HStack(spacing: 2) {
            Image(systemName: isPositive ? "chevron.up.2" : "chevron.down.2")
                .imageScale(.small)
            Text(value)
        }
        .foregroundStyle(isPositive ? .green : .red)
    }
}

#Preview {
    VStack {
        DashboardCard {
            VStack(alignment: .leading) {
                CardHeader(icon: "leaf.fill", title: "Test Card", iconColor: .green, subtitle: "Today")
                Spacer()
                Text("Sample Content")
            }
        }
    }
    .padding()
}
