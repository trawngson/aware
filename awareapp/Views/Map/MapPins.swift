import SwiftUI

/// Photo card pin for a shared project.
struct PhotoPin: View {
    let spot: MapSpot
    var width: CGFloat = 88
    var imageHeight: CGFloat = 72
    var showsAuthor = true
    var isSelected = false

    var body: some View {
        VStack(spacing: 0) {
            VStack(spacing: 0) {
                SpotPhoto(spot: spot)
                    .frame(width: width, height: imageHeight)
                    .clipped()
                if showsAuthor {
                    HStack(spacing: 5) {
                        MemberAvatar(member: spot.author, size: 16)
                        Text(spot.author.shortName)
                            .font(.system(size: 10, weight: .semibold))
                            .foregroundStyle(Theme.ink)
                            .lineLimit(1)
                        Spacer(minLength: 0)
                    }
                    .padding(.horizontal, 6)
                    .padding(.vertical, 5)
                    .frame(width: width)
                }
            }
            .background(.white)
            .clipShape(RoundedRectangle(cornerRadius: showsAuthor ? 18 : 11, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: showsAuthor ? 18 : 11, style: .continuous)
                    .strokeBorder(isSelected ? Theme.greenBright : .white, lineWidth: showsAuthor ? 2.5 : 1.5)
            )
            .shadow(color: Color(hex: 0x081C10, opacity: 0.34), radius: showsAuthor ? 12 : 7, y: showsAuthor ? 10 : 6)

            if showsAuthor {
                RoundedRectangle(cornerRadius: 2)
                    .fill(isSelected ? Theme.greenBright : .white)
                    .frame(width: 12, height: 12)
                    .rotationEffect(.degrees(45))
                    .offset(y: -7)
                    .shadow(color: Color(hex: 0x081C10, opacity: 0.2), radius: 3, x: 3, y: 3)
            }
        }
        .scaleEffect(isSelected ? 1.08 : 1, anchor: .bottom)
        .animation(.spring(response: 0.3, dampingFraction: 0.7), value: isSelected)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Text("\(spot.title), \(spot.author.name)"))
        .accessibilityAddTraits(.isButton)
    }
}

/// A spot's photo: the sample's asset, or the real post's stored photo.
struct SpotPhoto: View {
    let spot: MapSpot

    var body: some View {
        if let name = spot.imageName {
            Image(name).resizable().scaledToFill()
        } else if let url = spot.imageURL {
            RemotePhoto(url: url)
        } else {
            ZStack {
                Theme.green.opacity(0.15)
                Image(systemName: spot.tag == nil ? "leaf.fill" : "arrow.3.trianglepath")
                    .foregroundStyle(Theme.green)
            }
        }
    }
}

/// Green numbered bubble for a cluster of recycled items.
struct ClusterBubble: View {
    let count: Int
    var size: CGFloat = 30

    var body: some View {
        Text("\(count)")
            .font(.system(size: size * 0.37, weight: .bold))
            .foregroundStyle(.white)
            .frame(width: size, height: size)
            .background(Circle().fill(Theme.activeGradient))
            .overlay(Circle().strokeBorder(.white, lineWidth: size > 24 ? 2.5 : 2))
            .shadow(color: Color(hex: 0x081C10, opacity: 0.32), radius: 8, y: 7)
            .accessibilityLabel(Text("\(count) recycled items"))
    }
}

/// "You are here" dot with a soft pulsing halo.
struct UserLocationDot: View {
    var size: CGFloat = 16
    @State private var pulsing = false

    var body: some View {
        Circle()
            .fill(Theme.greenMid)
            .frame(width: size, height: size)
            .overlay(Circle().strokeBorder(.white, lineWidth: size * 0.18))
            .background(
                Circle()
                    .fill(Theme.greenMid.opacity(0.22))
                    .frame(width: size * 2.1, height: size * 2.1)
                    .scaleEffect(pulsing ? 1.12 : 1)
                    .opacity(pulsing ? 0.85 : 0.55)
            )
            .onAppear {
                withAnimation(.easeInOut(duration: 1.5).repeatForever(autoreverses: true)) { pulsing = true }
            }
            .accessibilityLabel("Your location")
    }
}

#Preview {
    HStack(spacing: 24) {
        PhotoPin(spot: RecyclingMapData.spots[0], isSelected: true)
        PhotoPin(spot: RecyclingMapData.spots[1], width: 44, imageHeight: 34, showsAuthor: false)
        ClusterBubble(count: 12)
        UserLocationDot()
    }
    .padding()
    .background(Color.gray.opacity(0.3))
}
