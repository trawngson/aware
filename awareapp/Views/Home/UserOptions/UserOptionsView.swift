//
//  UserOptionsView.swift
//  awareapp
//
//  Created by Nguyen Truong Son on 21/2/26.
//

import SwiftUI

/// "More": profile summary, guidance, preferences and about.
struct UserOptionsView: View {
    @ObservedObject private var ledger = RewardLedger.shared
    @ObservedObject private var session = AppSession.shared
    @AppStorage(NotificationManager.enabledKey) private var notificationsEnabled = true
    @State private var isNotificationPermissionOff = false
    @Environment(\.openURL) private var openURL

    private var languageName: String {
        let code = Bundle.main.preferredLocalizations.first ?? "en"
        return Locale.current.localizedString(forLanguageCode: code)?.localizedCapitalized ?? code
    }

    var body: some View {
        List {
            Section {
                profileCard
                    .listRowInsets(EdgeInsets())
                    .listRowBackground(Color.clear)
            }

            // Only with a backend: without one there is no account.
            if session.isBackendConfigured {
                Section {
                    NavigationLink {
                        AccountView()
                    } label: {
                        HStack {
                            row("Account", systemImage: "person.crop.circle.fill", tint: Theme.blue)
                            Spacer()
                            (session.isGuest ? Text("Guest") : Text("Apple ID"))
                                .foregroundStyle(Theme.ink.opacity(0.5))
                        }
                    }
                } header: {
                    sectionHeader("Account")
                }
                .listRowBackground(Color.white.opacity(0.74))
            }

            Section {
                NavigationLink {
                    RecyclingGuidanceInfoView()
                } label: {
                    row("Recycling guidance", systemImage: "arrow.3.trianglepath", tint: Theme.green)
                }
                NavigationLink {
                    RecyclingMapView()
                } label: {
                    row("Recycling map", systemImage: "map.fill", tint: Theme.blue)
                }
            } header: {
                sectionHeader("Guidance")
            }
            .listRowBackground(Color.white.opacity(0.74))

            // Only with a backend: without one there is no community to moderate.
            if session.isBackendConfigured {
                Section {
                    NavigationLink {
                        CommunityGuidelinesView()
                    } label: {
                        row("Community guidelines", systemImage: "person.2.fill", tint: Theme.green)
                    }
                    NavigationLink {
                        BlockedPeopleView()
                    } label: {
                        row("Blocked people", systemImage: "hand.raised.fill", tint: Theme.slate)
                    }
                } header: {
                    sectionHeader("Community")
                }
                .listRowBackground(Color.white.opacity(0.74))
            }

            Section {
                Toggle(isOn: $notificationsEnabled) {
                    row("Notifications", systemImage: "bell.fill", tint: Theme.orangeDeep)
                }
                .tint(Theme.greenBright)
                .onChange(of: notificationsEnabled) { _, isOn in
                    Task {
                        guard isOn else {
                            await NotificationManager.shared.disable()
                            return
                        }
                        // Asks for permission the first time; turns back off if declined.
                        if !(await NotificationManager.shared.enable()) {
                            notificationsEnabled = false
                            isNotificationPermissionOff = true
                        }
                    }
                }
                Button {
                    if let url = URL(string: UIApplication.openSettingsURLString) { openURL(url) }
                } label: {
                    HStack {
                        row("Language", systemImage: "globe", tint: Theme.cyanDeep)
                        Spacer()
                        Text(languageName).foregroundStyle(Theme.ink.opacity(0.5))
                        Image(systemName: "arrow.up.forward.app")
                            .font(.system(size: 14))
                            .foregroundStyle(Theme.ink.opacity(0.3))
                    }
                }
                .accessibilityHint("Opens Settings to change the app language")
            } header: {
                sectionHeader("Preferences")
            }
            .listRowBackground(Color.white.opacity(0.74))

            Section {
                NavigationLink {
                    RecyclingGuidanceInfoView()
                } label: {
                    HStack {
                        row("Latest regulations update", systemImage: "info.circle", tint: Theme.ink)
                        Spacer()
                        Text(RecyclingPolicy.lastReviewed, format: .dateTime.day().month(.abbreviated).year())
                            .font(.system(size: 13))
                            .foregroundStyle(Theme.ink.opacity(0.5))
                    }
                }
            } header: {
                sectionHeader("About")
            }
            .listRowBackground(Color.white.opacity(0.74))
        }
        .listStyle(.insetGrouped)
        .listSectionSpacing(18)
        .scrollContentBackground(.hidden)
        .environment(\.colorScheme, .light)
        .background {
            ForestBackdrop(blurFrom: 0.18, blurTo: 0.34,
                           scrim: ForestBackdrop.scrim(dark: 0.5, darkEnd: 0.15, mistStart: 0.32, mistMid: 0.5))
        }
        .forestNavigationBar("More")
        .alert("Notifications are off", isPresented: $isNotificationPermissionOff) {
            Button("Open Settings") {
                if let url = URL(string: UIApplication.openSettingsURLString) { openURL(url) }
            }
            Button("Not now", role: .cancel) {}
        } message: {
            Text("To get reminders and replies, allow notifications for AWARE in Settings.")
        }
    }

    private var profileCard: some View {
        HStack(spacing: 14) {
            MemberAvatar(member: Community.current, size: 56, borderColor: .white.opacity(0.7), borderWidth: 1.5)
            VStack(alignment: .leading, spacing: 2) {
                Text(Community.current.shortName)
                    .font(.system(size: 20, weight: .bold))
                    .tracking(-0.5)
                    .foregroundStyle(.white)
                HStack(spacing: 4) {
                    LeafAmount(value: Community.myPoints, size: 13, color: .white.opacity(0.8), leafColor: Theme.mint)
                    Text("· Rank \(Community.myRank)")
                        .font(.system(size: 13))
                        .foregroundStyle(.white.opacity(0.8))
                }
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
        .glass(.frosted, cornerRadius: 26)
        .accessibilityElement(children: .combine)
    }

    private func row(_ title: LocalizedStringKey, systemImage: String, tint: Color) -> some View {
        Label {
            Text(title).font(.system(size: 16)).foregroundStyle(Theme.ink)
        } icon: {
            IconTile(systemImage: systemImage, tint: tint, size: 30, cornerRadius: 9, iconSize: 15)
        }
    }

    private func sectionHeader(_ title: LocalizedStringKey) -> some View {
        Text(title)
            .font(.system(size: 13, weight: .semibold))
            .foregroundStyle(Theme.ink.opacity(0.5))
    }
}

/// Where the scan guidance comes from. Kept out of the scan results on purpose.
struct RecyclingGuidanceInfoView: View {
    private let groups: [DisposalGroup] = [.recyclable, .foodWaste, .other, .hazardous]

    var body: some View {
        TabScrollView {
            VStack(spacing: 16) {
                VStack(alignment: .leading, spacing: 6) {
                    Label(RecyclingPolicy.jurisdiction, systemImage: "mappin")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(.white.opacity(0.82))
                    Text("AWARE's sorting tips follow Hanoi's household waste sorting rules, which split waste into three groups, plus hazardous items kept apart.")
                        .font(.system(size: 15))
                        .lineSpacing(3)
                        .foregroundStyle(.white)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 18)
                .padding(.vertical, 16)
                .glass(.frosted, cornerRadius: 26)

                VStack(spacing: 10) {
                    ForEach(groups, id: \.self) { group in
                        HStack(alignment: .top, spacing: 12) {
                            IconTile(systemImage: group.symbol, tint: group.tint, size: 34, cornerRadius: 11, iconSize: 16)
                            VStack(alignment: .leading, spacing: 4) {
                                Text(group.displayName)
                                    .font(.system(size: 16, weight: .semibold))
                                    .foregroundStyle(Theme.ink)
                                Text(group.destination)
                                    .font(.system(size: 13))
                                    .lineSpacing(2)
                                    .foregroundStyle(Theme.ink.opacity(0.66))
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                            Spacer(minLength: 0)
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 14)
                        .glass(.card, cornerRadius: 20)
                        .accessibilityElement(children: .combine)
                    }
                }

                VStack(spacing: 8) {
                    SectionLabel(title: "Sources")
                    VStack(alignment: .leading, spacing: 8) {
                        Text(RecyclingPolicy.jurisdiction)
                            .font(.system(size: 15, weight: .semibold))
                            .foregroundStyle(Theme.ink)
                        Text(RecyclingPolicy.source)
                            .font(.system(size: 12.5))
                            .lineSpacing(3)
                            .foregroundStyle(Theme.ink.opacity(0.62))
                            .fixedSize(horizontal: false, vertical: true)
                        Text("Guidance version \(RecyclingPolicy.version)")
                            .font(.system(size: 12, design: .monospaced))
                            .foregroundStyle(Theme.ink.opacity(0.45))
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(16)
                    .glass(.card, cornerRadius: 22)
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 6)
            .padding(.bottom, 20)
        }
        .scrollIndicators(.hidden)
        .background {
            ForestBackdrop(blurFrom: 0.16, blurTo: 0.32,
                           scrim: ForestBackdrop.scrim(dark: 0.5, darkEnd: 0.14, mistStart: 0.3, mistMid: 0.46))
        }
        .forestNavigationBar("Recycling guidance")
    }
}

extension DisposalGroup {
    var symbol: String {
        switch self {
        case .recyclable: "arrow.3.trianglepath"
        case .foodWaste: "leaf.arrow.triangle.circlepath"
        case .other: "trash"
        case .hazardous: "exclamationmark.triangle.fill"
        }
    }

    var tint: Color {
        switch self {
        case .recyclable: Theme.green
        case .foodWaste: Color(hex: 0x2C8B4F)
        case .other: Theme.slate
        case .hazardous: Theme.red
        }
    }
}

#Preview {
    NavigationStack { UserOptionsView() }
        .preferredColorScheme(.dark)
}
