//
//  UserOptionsView.swift
//  awareapp
//
//  Created by Nguyen Truong Son on 21/2/26.
//

import SwiftUI

struct UserOptionsView: View {
    var body: some View {
        List {
            Section {
                NavigationLink {
                    RecyclingGuidanceInfoView()
                } label: {
                    Label("Recycling guidance", systemImage: "arrow.3.trianglepath")
                }
            }
        }
        .navigationTitle("More")
        .navigationBarTitleDisplayMode(.inline)
    }
}

/// Where the scan guidance comes from. Kept out of the scan results on purpose.
struct RecyclingGuidanceInfoView: View {
    private let groups: [DisposalGroup] = [.recyclable, .foodWaste, .other, .hazardous]

    var body: some View {
        List {
            Section {
                Text("AWARE's sorting tips follow Hanoi's household waste sorting rules, which split waste into three groups, plus hazardous items kept apart.")
                    .fixedSize(horizontal: false, vertical: true)
            }
            Section {
                ForEach(groups, id: \.self) { group in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(group.displayName).font(.headline)
                        Text(group.destination)
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(.vertical, 2)
                }
            }
            Section("Sources") {
                Text(RecyclingPolicy.jurisdiction).font(.subheadline.weight(.semibold))
                Text(RecyclingPolicy.source)
                    .font(.footnote)
                    .fixedSize(horizontal: false, vertical: true)
                Text("Guidance version \(RecyclingPolicy.version)")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
        }
        .navigationTitle("Recycling guidance")
        .navigationBarTitleDisplayMode(.inline)
    }
}

#Preview {
    NavigationStack { UserOptionsView() }
}
