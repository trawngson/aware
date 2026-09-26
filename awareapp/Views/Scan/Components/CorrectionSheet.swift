import SwiftUI

/// "What should this have been?" sheet, opened from "Was this detection
/// correct? No".
struct CorrectionSheet: View {
    /// Name of what the scanner currently shows.
    let detectedName: String
    /// Label currently shown, left out of the options.
    let currentLabel: String
    /// Called with a canonical label or `DetectionFeedback.somethingElse`.
    let onSubmit: (String) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var selection: String?

    private var options: [CanonicalLabel] {
        CanonicalLabel.allCases.filter { $0.rawValue != currentLabel }
    }

    var body: some View {
        List {
            Section {
                ForEach(options) { label in
                    optionRow(id: label.rawValue, title: label.displayName, systemImage: label.iconName, tint: label.tint)
                }
                optionRow(id: DetectionFeedback.somethingElse, title: String(localized: "Something else"),
                          systemImage: "ellipsis", tint: Theme.ink.opacity(0.6))
            } header: {
                VStack(alignment: .leading, spacing: 4) {
                    Text("What should this have been?")
                        .font(.system(size: 22, weight: .bold))
                        .tracking(-0.6)
                        .foregroundStyle(Theme.ink)
                    Text("We detected **\(detectedName)**. Pick what it really is and we'll update the guidance.")
                        .font(.system(size: 14))
                        .foregroundStyle(Theme.ink.opacity(0.6))
                }
                .textCase(nil)
                .padding(.bottom, 8)
                .padding(.top, 8)
            }
            .listRowBackground(Color.white.opacity(0.8))
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(Color(hex: 0xF3F7F1))
        .safeAreaInset(edge: .bottom) {
            HStack(spacing: 10) {
                Button {
                    dismiss()
                } label: {
                    Text("Cancel")
                        .font(.system(size: 17, weight: .semibold))
                        .foregroundStyle(Theme.ink.opacity(0.72))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(RoundedRectangle(cornerRadius: 20, style: .continuous).fill(Theme.ink.opacity(0.06)))
                }
                .buttonStyle(PressableStyle())
                Button("Submit correction") {
                    guard let selection else { return }
                    onSubmit(selection)
                    dismiss()
                }
                .buttonStyle(PrimaryButtonStyle(cornerRadius: 20))
                .disabled(selection == nil)
            }
            .padding(.horizontal, 16)
            .padding(.top, 10)
            .padding(.bottom, 6)
            .background(Color(hex: 0xF3F7F1).opacity(0.95))
        }
        .presentationDetents([.large])
        .presentationDragIndicator(.visible)
        .presentationCornerRadius(38)
        .lightSheetAppearance()
    }

    private func optionRow(id: String, title: String, systemImage: String, tint: Color) -> some View {
        let isSelected = selection == id
        return Button {
            selection = id
        } label: {
            HStack(spacing: 12) {
                IconTile(systemImage: systemImage, tint: tint, size: 30, cornerRadius: 9, iconSize: 15)
                Text(title).font(.system(size: 16)).foregroundStyle(Theme.ink)
                Spacer(minLength: 0)
                if isSelected {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 21))
                        .foregroundStyle(Theme.green)
                        .transition(.scale.combined(with: .opacity))
                } else {
                    Circle()
                        .strokeBorder(Theme.ink.opacity(0.18), lineWidth: 1.5)
                        .frame(width: 21, height: 21)
                }
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .animation(.snappy, value: isSelected)
        .accessibilityAddTraits(isSelected ? .isSelected : [])
    }
}

#Preview {
    Color.gray.sheet(isPresented: .constant(true)) {
        CorrectionSheet(detectedName: "Plastic bottle", currentLabel: "plastic_bottle") { _ in }
    }
}
