//
//  LeaderboardView.swift
//  awareapp
//
//  Created by Nguyen Truong Son on 26/2/26.
//
import SwiftUI

struct LeaderboardView: View {
    @ObservedObject private var ledger = RewardLedger.shared
    @ObservedObject private var session = AppSession.shared
    @ObservedObject private var store = LeaderboardStore.shared
    @State private var period: LeaderboardPeriod = .month

    private var ranking: [(member: CommunityMember, points: Int)] { Community.standings(for: period) }

    var body: some View {
        let ranking = self.ranking
        TabScrollView {
            VStack(spacing: 18) {
                // All-time rankings exist only on the server.
                if session.isBackendConfigured {
                    Picker("Period", selection: $period.animation(.snappy)) {
                        Text("This Month").tag(LeaderboardPeriod.month)
                        Text("All Time").tag(LeaderboardPeriod.all)
                    }
                    .pickerStyle(.segmented)
                    .environment(\.colorScheme, .light)
                }
                if ranking.count >= 3 {
                    podium(ranking)
                }
                VStack(spacing: 8) {
                    ForEach(Array(ranking.enumerated().dropFirst(ranking.count >= 3 ? 3 : 0)),
                            id: \.element.member.id) { index, entry in
                        rankRow(rank: index + 1, entry: entry)
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 8)
            .padding(.bottom, 16)
        }
        .scrollIndicators(.hidden)
        .background {
            ForestBackdrop(blurFrom: 0.32, blurTo: 0.52, scrim: [
                .init(color: Theme.forestShade.opacity(0.54), location: 0),
                .init(color: Theme.forestShade.opacity(0.3), location: 0.24),
                .init(color: Theme.mist.opacity(0.44), location: 0.46),
                .init(color: Theme.mist.opacity(0.77), location: 0.64),
                .init(color: Theme.mist.opacity(0.81), location: 1),
            ])
        }
        .forestNavigationBar("Leaderboard")
        .task { await store.refresh() }
        .refreshable { await store.refresh() }
    }

    // MARK: - Podium

    private func podium(_ ranking: [(member: CommunityMember, points: Int)]) -> some View {
        HStack(alignment: .bottom, spacing: 22) {
            podiumPlace(rank: 2, entry: ranking[1])
                .frame(maxWidth: .infinity)
            podiumPlace(rank: 1, entry: ranking[0])
                .frame(maxWidth: .infinity)
                .layoutPriority(1.15)
                .padding(.bottom, 16)
            podiumPlace(rank: 3, entry: ranking[2])
                .frame(maxWidth: .infinity)
        }
        .padding(.top, 6)
    }

    private func podiumPlace(rank: Int, entry: (member: CommunityMember, points: Int)) -> some View {
        let isWinner = rank == 1
        return VStack(spacing: 8) {
            if isWinner {
                WinnerAvatar(member: entry.member)
            } else {
                MemberAvatar(member: entry.member, size: 64, borderColor: .white.opacity(0.7), borderWidth: 2)
            }
            VStack(spacing: isWinner ? 3 : 2) {
                Group {
                    if isWinner {
                        Label("\(rank)", systemImage: "medal.fill")
                            .labelStyle(.titleAndIcon)
                            .foregroundStyle(Theme.inkOnWhite)
                            .padding(.horizontal, 9)
                            .padding(.vertical, 2)
                            .background(Capsule().fill(.white.opacity(0.85)))
                    } else {
                        Text("\(rank)")
                            .foregroundStyle(.white)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 1)
                            .background(Capsule().fill(.white.opacity(0.22)))
                    }
                }
                .font(.system(size: 12, weight: .bold))

                Text(entry.member.shortName)
                    .font(.system(size: isWinner ? 15 : 13, weight: isWinner ? .bold : .semibold))
                    .foregroundStyle(.white)
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
                LeafAmount(value: entry.points, size: isWinner ? 13 : 11, color: isWinner ? .white : .white.opacity(0.85),
                           leafColor: Theme.mint)
            }
            .frame(maxWidth: .infinity)
            .padding(.horizontal, 6)
            .padding(.vertical, isWinner ? 12 : 10)
            .glass(GlassStyle(top: isWinner ? 0.2 : 0.14, bottom: isWinner ? 0.2 : 0.14, border: isWinner ? 0.45 : 0.36,
                              highlight: 0.4, material: .ultraThinMaterial,
                              shadow: Color(hex: 0x081C10, opacity: isWinner ? 0.22 : 0), shadowRadius: 12, shadowY: 10),
                   cornerRadius: isWinner ? 22 : 20)
        }
        .accessibilityElement(children: .combine)
    }

    // MARK: - Rows

    private func rankRow(rank: Int, entry: (member: CommunityMember, points: Int)) -> some View {
        HStack(spacing: 12) {
            Text("\(rank)")
                .font(.system(size: 13, weight: .bold))
                .foregroundStyle(Theme.green)
                .frame(width: 26, height: 26)
                .background(RoundedRectangle(cornerRadius: 9, style: .continuous).fill(Theme.green.opacity(0.12)))
            Text(entry.member.shortName)
                .font(.system(size: 16, weight: .medium))
                .tracking(-0.16)
                .foregroundStyle(Theme.ink)
            Spacer(minLength: 0)
            LeafAmount(value: entry.points)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
        .glass(GlassStyle(top: 0.78, bottom: 0.58, border: 0.8, highlight: 0.9, material: nil,
                          shadow: Color(hex: 0x143A22, opacity: 0.08), shadowRadius: 10, shadowY: 8),
               cornerRadius: 20)
        .accessibilityElement(children: .combine)
    }
}

/// The first-place avatar with a slowly pulsing aura.
private struct WinnerAvatar: View {
    let member: CommunityMember
    @State private var pulsing = false

    var body: some View {
        MemberAvatar(member: member, size: 88, borderColor: .white.opacity(0.85), borderWidth: 2.5)
            .background(
                Circle()
                    .fill(Theme.mint.opacity(0.4))
                    .padding(-6)
                    .scaleEffect(pulsing ? 1.06 : 1)
                    .opacity(pulsing ? 0.85 : 0.55)
            )
            .onAppear {
                withAnimation(.easeInOut(duration: 1.5).repeatForever(autoreverses: true)) { pulsing = true }
            }
    }
}

#Preview {
    NavigationStack {
        LeaderboardView()
    }
    .preferredColorScheme(.dark)
}
