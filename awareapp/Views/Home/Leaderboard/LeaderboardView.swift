//
//  LeaderboardView.swift
//  awareapp
//
//  Created by Nguyen Truong Son on 26/2/26.
//
import SwiftUI

struct LeaderboardView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
//            Text("Leaderboard")
//                .font(.largeTitle)
//                .fontWeight(.bold)

            HStack(alignment: .bottom, spacing: 40) {
                
                VStack(spacing: 10) {
                    avatar(size: 72)
                    VStack(spacing: 2) {
                        HStack(spacing: 3) {
                            Text("10,000")
                                .foregroundStyle(.secondary)
                                .font(.caption)
                            Image(systemName: "leaf.fill").foregroundStyle(.secondary).font(.caption)
                        }
                        Text("Dieu Linh")
                            .font(.subheadline.weight(.semibold))
                        HStack(spacing: 2) {
                            Image(systemName: "medal.fill")
                                .foregroundStyle(.orange)
                                .font(.subheadline)
                            Text("Top 2")
                                .font(.subheadline.weight(.bold))
                                .foregroundStyle(Color.orange)
                        }
                    }
                }
                

                VStack(spacing: 10) {
                    myAvatar(size: 96)
                    VStack(spacing: 2) {
                        HStack(spacing: 3) {
                            Text("20,000")
                                .foregroundStyle(.secondary)
                                .font(.footnote)
                            Image(systemName: "leaf.fill").foregroundStyle(.secondary).font(.footnote)
                        }
                        Text("Truong Son")
                            .font(.headline.weight(.semibold))
                        HStack(spacing: 2) {
                            Image(systemName: "medal.fill")
                                .foregroundStyle(.yellow.mix(with: .red, by: 0.2))
                            Text("Top 1")
                                .font(.headline.weight(.bold))
                                .foregroundStyle(Color.yellow.mix(with: .red, by: 0.2))
                        }
                    }
                }

                VStack(spacing: 10) {
                    avatar(size: 72)
                    VStack(spacing: 2) {
                        HStack(spacing: 3) {
                            Text("5,000")
                                .foregroundStyle(.secondary)
                                .font(.caption)
                            Image(systemName: "leaf.fill").foregroundStyle(.secondary).font(.caption)
                        }
                        Text("Ha Chi")
                            .font(.subheadline.weight(.semibold))
                        HStack(spacing: 2) {
                            Image(systemName: "medal.fill")
                                .foregroundStyle(.orange.opacity(0.6))
                                .font(.subheadline)
                            Text("Top 3")
                                .font(.subheadline.weight(.bold))
                                .foregroundStyle(Color.orange.opacity(0.6))
                        }
                    }
                }
            }
            .frame(maxWidth: .infinity)
            
            VStack(spacing: 12) {
                ForEach(lowerRanks, id: \.rank) { entry in
                    HStack {
                        Text("\(entry.rank)")
                            .fontWeight(.bold)
                        Text(entry.name)
                        HStack(spacing: 3) {
                            Text(entry.leaves)
                                .foregroundStyle(.secondary)
                            Image(systemName: "leaf.fill")
                                .foregroundStyle(.secondary)
                        }
                        Spacer()
                        Image(systemName: "chevron.right")
                            .foregroundStyle(.secondary)
                    }
                    .padding()
                    .frame(maxWidth: .infinity, minHeight: 60, alignment: .leading)
                    .background(
                        RoundedRectangle(cornerRadius: 16, style: .continuous)
                            .fill(.thickMaterial)
                    )
                }
            }
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(backgroundView)
    }

    private var lowerRanks: [(rank: Int, name: String, leaves: String)] {
        [
            (4, "Johnathan", "10,000"),
            (5, "Mia", "9,200"),
            (6, "Noah", "8,750"),
            (7, "Luna", "8,300"),
            (8, "Ethan", "7,950"),
            (9, "Ava", "7,600"),
        ]
    }

    private func avatar(size: CGFloat) -> some View {
        Circle()
            .fill(Color.gray.opacity(0.35))
            .frame(width: size, height: size)
            .overlay(
                Image(systemName: "PlaceholderAvatar")
                    .font(.system(size: size * 0.45, weight: .semibold))
                    .foregroundStyle(Color.gray)
            )
    }
    
    private func myAvatar(size: CGFloat) -> some View {
        Circle()
            .fill(Color.gray.opacity(0.35))
            .frame(width: size, height: size)
            .overlay(
                Image("PlaceholderAvatar")
                    .resizable()
                    .scaledToFill()
                    .frame(width: size, height: size)
                    .font(.system(size: size * 0.45, weight: .semibold))
                    .clipShape(Circle())
                    .foregroundStyle(Color.gray)
            )
    }
}

private var backgroundView: some View {
    ZStack(alignment: .top) {
        Color(uiColor: .systemGroupedBackground)
        LinearGradient(
            stops: [
                .init(color: Color.green.opacity(0.35), location: 0.0),
                .init(color: Color.green.opacity(0.2), location: 0.15 * 1.5),
                .init(color: Color.green.opacity(0.0), location: 0.3 * 1.5)
            ],
            startPoint: .top,
            endPoint: .bottom
        )
    }
    .ignoresSafeArea()
}

#Preview {
    LeaderboardView()
}
