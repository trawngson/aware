import SwiftUI

struct ScanResultsView: View {
    let detection: YOLODetection
    let capturedImage: UIImage?
    let onDismiss: () -> Void
    let onAddToGallery: (() -> Void)?

    /// One scan event per results screen; the reward layer awards it at most once.
    @State private var scanEventID = UUID()
    @State private var choiceID: String?

    private var policy: PolicyResult {
        RecyclingPolicy.evaluate(modelLabel: detection.label, choiceID: choiceID)
    }

    init(
        detection: YOLODetection,
        capturedImage: UIImage?,
        onDismiss: @escaping () -> Void,
        onAddToGallery: (() -> Void)? = nil
    ) {
        self.detection = detection
        self.capturedImage = capturedImage
        self.onDismiss = onDismiss
        self.onAddToGallery = onAddToGallery
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                imageSection
                detailsSection
            }
            .padding(.bottom, 24)
        }
        .background(Color(uiColor: .systemBackground))
    }

    // MARK: - Image

    private var imageSection: some View {
        Group {
            if let image = capturedImage {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFill()
                    .frame(height: UIScreen.main.bounds.height * 0.32)
                    .clipped()
            } else {
                Rectangle()
                    .fill(Color(uiColor: .systemGray5))
                    .frame(height: UIScreen.main.bounds.height * 0.32)
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        .padding(.horizontal, 20)
    }

    // MARK: - Details

    private var detailsSection: some View {
        let policy = policy
        return VStack(alignment: .leading, spacing: 16) {
            Text(policy.displayName)
                .font(.largeTitle)
                .fontWeight(.bold)

            HStack(spacing: 12) {
                if let group = policy.group {
                    CategoryPill(icon: groupIcon(group), text: group.displayName, color: groupColor(group))
                }
                if policy.rewardPoints > 0 {
                    CategoryPill(icon: "leaf.fill", text: "\(policy.rewardPoints)", color: .green)
                }
            }

            Text(policy.summary)
                .font(.body)
                .fixedSize(horizontal: false, vertical: true)

            if let confirmation = policy.confirmation {
                confirmationSection(confirmation)
            }

            if !policy.steps.isEmpty {
                stepsSection(policy.steps, group: policy.group)
            }

            if let group = policy.group {
                destinationSection(group)
            }

            ForEach(policy.notes, id: \.self) { note in
                Label(note, systemImage: "info.circle")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if policy.state != .confirmationRequired {
                recyclingIdeasSection
            }

            addToGalleryButton(policy)
        }
        .padding(.horizontal, 24)
        .padding(.top, 24)
    }

    private func confirmationSection(_ confirmation: PolicyConfirmation) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Label(confirmation.question, systemImage: "questionmark.circle.fill")
                .font(.headline)
                .foregroundStyle(.orange)
            ForEach(confirmation.choices) { choice in
                Button {
                    withAnimation { choiceID = choice.id }
                } label: {
                    Text(choice.title)
                        .font(.body.weight(.semibold))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .background(Color.orange.opacity(0.12))
                        .foregroundStyle(.orange)
                        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                }
            }
        }
    }

    private func stepsSection(_ steps: [String], group: DisposalGroup?) -> some View {
        let color = group.map(groupColor) ?? .green
        return VStack(alignment: .leading, spacing: 10) {
            HStack {
                Label("How to sort it", systemImage: "arrow.triangle.2.circlepath")
                    .font(.headline)
                    .foregroundStyle(color)
                Spacer()
                if choiceID != nil {
                    Button("Change answer") { withAnimation { choiceID = nil } }
                        .font(.footnote)
                }
            }
            ForEach(Array(steps.enumerated()), id: \.offset) { index, step in
                HStack(alignment: .top, spacing: 10) {
                    Text("\(index + 1).")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(color)
                    Text(step)
                        .font(.subheadline)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
        .padding(14)
        .background(RoundedRectangle(cornerRadius: 14, style: .continuous).fill(color.opacity(0.08)))
    }

    private func destinationSection(_ group: DisposalGroup) -> some View {
        Label(group.destination, systemImage: "mappin.and.ellipse")
            .font(.subheadline)
            .fixedSize(horizontal: false, vertical: true)
    }

    private var recyclingIdeasSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Want to give it a second life? See our recycling ideas below.")
                .font(.subheadline)
                .fixedSize(horizontal: false, vertical: true)
            Button(action: openRecyclingIdeas) {
                Label("See recycling ideas", systemImage: "lightbulb.fill")
                    .font(.subheadline.weight(.semibold))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
                    .foregroundStyle(.green)
                    .background(Color.green.opacity(0.12))
                    .clipShape(Capsule())
            }
        }
    }

    private func openRecyclingIdeas() {
        onDismiss()
        NavigationManager.shared.switchToGallery()
    }

    // MARK: - Gallery and reward

    private func addToGalleryButton(_ policy: PolicyResult) -> some View {
        let needsAnswer = policy.state == .confirmationRequired
        return Button { handleAddToGallery(policy) } label: {
            HStack(spacing: 8) {
                Image(systemName: "photo.badge.plus")
                    .font(.body.weight(.semibold))
                Text(needsAnswer ? LocalizedStringKey("Answer the question above first") : LocalizedStringKey("Add to Gallery"))
                    .font(.headline)
            }
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(needsAnswer ? Color.gray : Color.green)
            .clipShape(Capsule())
        }
        .disabled(needsAnswer)
        .padding(.top, 8)
    }

    private func handleAddToGallery(_ policy: PolicyResult) {
        let result = RewardLedger.shared.award(policy, scanEventID: scanEventID)
        GalleryStore.shared.addPostFromScan(
            image: capturedImage,
            itemName: policy.displayName,
            leafPoints: result.state == .eligible ? result.points : 0
        )
        onAddToGallery?()
        onDismiss()
        NavigationManager.shared.switchToGallery()
    }

    // MARK: - Styling

    private func groupColor(_ group: DisposalGroup) -> Color {
        switch group {
        case .recyclable: .blue
        case .foodWaste: .green
        case .other: .gray
        case .hazardous: .red
        }
    }

    private func groupIcon(_ group: DisposalGroup) -> String {
        switch group {
        case .recyclable: "arrow.3.trianglepath"
        case .foodWaste: "leaf"
        case .other: "trash"
        case .hazardous: "exclamationmark.triangle.fill"
        }
    }
}

// MARK: - Preview

#Preview("Cup (needs confirmation)") {
    ScanResultsView(
        detection: YOLODetection(id: 0, label: "disposable_cup", confidence: 0.9, boundingBox: .zero),
        capturedImage: nil,
        onDismiss: {}
    )
}

#Preview("Plastic bottle") {
    ScanResultsView(
        detection: YOLODetection(id: 0, label: "plastic_bottle", confidence: 0.95, boundingBox: .zero),
        capturedImage: nil,
        onDismiss: {}
    )
}
