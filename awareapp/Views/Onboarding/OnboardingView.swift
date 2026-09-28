//
//  WelcomeView.swift
//  awareapp
//
//  Created by Nguyen Truong Son on 9/4/26.
//

import SwiftUI

struct OnboardingView: View {

    @Environment(\.dismiss) var dismiss

    private let features: [(icon: String, title: LocalizedStringKey, text: LocalizedStringKey)] = [
        ("chart.line.uptrend.xyaxis", "Dashboard", "Effortlessly follow up on your recycling journey."),
        ("brain.head.profile", "AI-Powered Identification", "Scan waste and quickly get bonus points in return."),
        ("photo", "Gallery", "See what others are up to – find inspirations for yourself."),
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                VStack(alignment: .leading, spacing: 8) {
                    Image(systemName: "leaf.fill")
                        .font(.system(size: 28))
                        .foregroundStyle(Theme.mint)
                        .frame(width: 56, height: 56)
                        .background(RoundedRectangle(cornerRadius: 18, style: .continuous).fill(.white.opacity(0.22)))
                        .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(.white.opacity(0.35), lineWidth: 0.5))
                    Text("Welcome to")
                        .font(.system(size: 15, weight: .medium))
                        .foregroundStyle(.white.opacity(0.72))
                        .padding(.top, 8)
                    Text("AWARE")
                        .font(.system(size: 46, weight: .bold))
                        .tracking(-1.6)
                        .foregroundStyle(.white)
                    Text("One quick scan to sort with ease – help the Earth and save the trees.")
                        .font(.system(size: 16))
                        .lineSpacing(3)
                        .foregroundStyle(.white.opacity(0.82))
                        .frame(maxWidth: 290, alignment: .leading)
                }

                VStack(spacing: 14) {
                    ForEach(features, id: \.icon) { feature in
                        HStack(spacing: 14) {
                            IconTile(systemImage: feature.icon, tint: Theme.mint, background: Theme.mint.opacity(0.22),
                                     size: 38, cornerRadius: 13, iconSize: 18)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(feature.title)
                                    .font(.system(size: 16, weight: .semibold))
                                    .foregroundStyle(.white)
                                Text(feature.text)
                                    .font(.system(size: 13))
                                    .foregroundStyle(.white.opacity(0.75))
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                            Spacer(minLength: 0)
                        }
                        .padding(.horizontal, 14)
                        .padding(.vertical, 12)
                        .background(RoundedRectangle(cornerRadius: 18, style: .continuous).fill(.white.opacity(0.14)))
                        .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(.white.opacity(0.22), lineWidth: 0.5))
                    }
                }

                Button {
                    dismiss()
                } label: {
                    Text("Got it!")
                        .font(.system(size: 17, weight: .semibold))
                        .foregroundStyle(Theme.inkOnWhite)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(
                            RoundedRectangle(cornerRadius: 18, style: .continuous)
                                .fill(LinearGradient(colors: [.white.opacity(0.98), Color(hex: 0xE4F4E9, opacity: 0.94)],
                                                     startPoint: .top, endPoint: .bottom))
                                .shadow(color: Theme.forestShade.opacity(0.28), radius: 10, y: 8)
                        )
                }
                .buttonStyle(PressableStyle())
            }
            .padding(.horizontal, 22)
            .padding(.vertical, 26)
            .glass(.frosted, cornerRadius: 32)
            .padding(16)
            .frame(maxWidth: 450)
            .frame(maxWidth: .infinity)
            .containerRelativeFrame(.vertical, alignment: .bottom)
        }
        .scrollBounceBehavior(.basedOnSize)
        .scrollIndicators(.hidden)
        .background {
            ForestBackdrop(blurFrom: 0.42, blurTo: 0.62, scrim: [
                .init(color: Theme.forestShade.opacity(0.34), location: 0),
                .init(color: Theme.forestShade.opacity(0.12), location: 0.26),
                .init(color: Theme.forestShade.opacity(0.48), location: 0.58),
                .init(color: Theme.forestShade.opacity(0.8), location: 0.86),
                .init(color: Theme.forestShade.opacity(0.88), location: 1),
            ])
        }
        .preferredColorScheme(.dark)
    }
}


#Preview {
    OnboardingView()
}
