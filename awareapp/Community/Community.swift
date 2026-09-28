import SwiftUI

// MARK: - Demo community

/// How a member's avatar is drawn: a photo asset or initials on a gradient.
enum AvatarStyle: Equatable {
    case asset(String)
    case initials(String, top: Color, bottom: Color)
}

struct CommunityMember: Identifiable, Equatable {
    let id: String
    /// Full name, used on posts and replies ("Dieu Linh Do").
    let name: String
    /// Short name, used in rankings ("Dieu Linh").
    let shortName: String
    let points: Int
    let avatar: AvatarStyle
}

/// Hard-coded demo people shared by Home, the leaderboard, the Gallery and
/// the map, so the same person shows the same points everywhere. There are no
/// accounts or backend sync.
enum Community {
    static let me = CommunityMember(
        id: "me", name: "Truong Son Nguyen", shortName: "Truong Son", points: 24_100,
        avatar: .asset("PlaceholderAvatar")
    )
    static let dieuLinh = CommunityMember(
        id: "dieu-linh", name: "Dieu Linh Do", shortName: "Dieu Linh", points: 20_000,
        avatar: .initials("DL", top: Color(hex: 0x34A862), bottom: Color(hex: 0x1C7442))
    )
    static let haChi = CommunityMember(
        id: "ha-chi", name: "Ha Chi Pham", shortName: "Ha Chi", points: 15_000,
        avatar: .initials("HC", top: Color(hex: 0x9B7ADB), bottom: Color(hex: 0x6E4FB8))
    )
    static let anthony = CommunityMember(
        id: "anthony", name: "Anthony", shortName: "Anthony", points: 9_400,
        avatar: .initials("A", top: Color(hex: 0xE0A23A), bottom: Color(hex: 0xB56E12))
    )
    static let max = CommunityMember(
        id: "max", name: "Max", shortName: "Max", points: 8_100,
        avatar: .initials("M", top: Color(hex: 0x3FB3BE), bottom: Color(hex: 0x0E7C86))
    )
    static let minhKhoi = CommunityMember(
        id: "minh-khoi", name: "Minh Khoi", shortName: "Minh Khoi", points: 7_650,
        avatar: .initials("MK", top: Color(hex: 0x5B9BD8), bottom: Color(hex: 0x3E6FB0))
    )
    static let thuHa = CommunityMember(
        id: "thu-ha", name: "Thu Ha", shortName: "Thu Ha", points: 7_200,
        avatar: .initials("TH", top: Color(hex: 0xE07A9B), bottom: Color(hex: 0xB04A6E))
    )
    static let quangDuy = CommunityMember(
        id: "quang-duy", name: "Quang Duy", shortName: "Quang Duy", points: 6_850,
        avatar: .initials("QD", top: Color(hex: 0x7FA35B), bottom: Color(hex: 0x55773A))
    )
    static let baoNgoc = CommunityMember(
        id: "bao-ngoc", name: "Bao Ngoc", shortName: "Bao Ngoc", points: 6_300,
        avatar: .initials("BN", top: Color(hex: 0xD98B5F), bottom: Color(hex: 0xA85A34))
    )

    static let others = [dieuLinh, haChi, anthony, max, minhKhoi, thuHa, quangDuy, baoNgoc]

    /// Demo points plus anything earned from scans in this session.
    @MainActor
    static var myPoints: Int { me.points + RewardLedger.shared.totalPoints }

    /// Everyone this month, highest first, with the current user's live total.
    @MainActor
    static var ranking: [(member: CommunityMember, points: Int)] {
        ([(me, myPoints)] + others.map { ($0, $0.points) })
            .sorted { $0.1 > $1.1 }
            .map { (member: $0.0, points: $0.1) }
    }

    @MainActor
    static var myRank: Int {
        (ranking.firstIndex { $0.member.id == me.id } ?? 0) + 1
    }
}

// MARK: - Avatar

struct MemberAvatar: View {
    let member: CommunityMember
    var size: CGFloat = 40
    var borderColor: Color = .clear
    var borderWidth: CGFloat = 0

    var body: some View {
        Group {
            switch member.avatar {
            case .asset(let name):
                Image(name).resizable().scaledToFill()
            case .initials(let initials, let top, let bottom):
                LinearGradient(colors: [top, bottom], startPoint: .top, endPoint: .bottom)
                    .overlay(
                        Text(initials)
                            .font(.system(size: size * (initials.count > 1 ? 0.38 : 0.42), weight: .semibold))
                            .foregroundStyle(.white)
                    )
                    .overlay(Circle().strokeBorder(LinearGradient(colors: [.white.opacity(0.25), .clear],
                                                                  startPoint: .top, endPoint: .center), lineWidth: 1))
            }
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
        .overlay(Circle().strokeBorder(borderColor, lineWidth: borderWidth))
        .accessibilityHidden(true)
    }
}

#Preview {
    HStack {
        MemberAvatar(member: Community.me, size: 58)
        MemberAvatar(member: Community.dieuLinh, size: 58)
        MemberAvatar(member: Community.anthony, size: 40)
    }
    .padding()
}
