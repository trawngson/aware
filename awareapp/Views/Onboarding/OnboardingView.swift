//
//  WelcomeView.swift
//  awareapp
//
//  Created by Nguyen Truong Son on 9/4/26.
//

import OnboardingKit
import SwiftUI

struct OnboardingView: View {

    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 32) {
                    OnboardingIntroScreen(
                        icon: Image(systemName: "leaf.fill"),
                        welcomeTitle: "Welcome to",
                        title: "AWARE",
                        text: "One quick scan to sort with ease – help the Earth and save the trees.",
                        usps: [
                            .init(
                                title: "Dashboard",
                                text: "Effortlessly follow up on your recycling journey.",
                                image: .init(systemName: "chart.line.uptrend.xyaxis")
                            ),
                            .init(
                                title: "AI-Powered Identification",
                                text: "Scan waste and quickly get bonus points in return.",
                                image: .init(systemName: "brain")
                            ),
                            .init(
                                title: "Gallery",
                                text: "See what others are up to – find inspirations for yourself.",
                                image: .init(systemName: "photo")
                            )
                        ]
                    )
                    
                    Button {
                        dismiss()
                    } label: {
                        Text("Got it!")
                            .font(.headline)
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(.blue)
                            .cornerRadius(12)
                            .shadow(color: .green.opacity(0.3), radius: 10, x: 0, y: 5)
                    }
                }
                .padding()
                .padding(.top, 40)
                .frame(maxWidth: 450)
            }
        }
        .presentationDragIndicator(.visible)
    }
}


#Preview {
    OnboardingView()
}
