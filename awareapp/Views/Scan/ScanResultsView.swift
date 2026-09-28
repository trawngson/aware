import SwiftUI

struct ScanResultsView: View {
    let detection: YOLODetection
    let capturedImage: UIImage?
    let onDismiss: () -> Void
    let onAddToGallery: (() -> Void)?

    /// One scan event per results screen; the reward layer awards it at most once.
    @State private var scanEventID = UUID()
    @State private var choiceID: String?
    /// Label the user picked in "Correct the detection", if any.
    @State private var correctedLabel: String?
    @State private var feedback: DetectionFeedback.Verdict?
    @State private var showCorrection = false
    @State private var showImpactInfo = false

    private var effectiveLabel: String { correctedLabel ?? detection.label }

    private var policy: PolicyResult {
        RecyclingPolicy.evaluate(modelLabel: effectiveLabel, choiceID: choiceID)
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
        let policy = policy
        TabScrollView {
            VStack(spacing: 14) {
                Color.clear.frame(height: 180)

                titleCard(policy)
                feedbackCard(policy)

                if let confirmation = policy.confirmation {
                    confirmationCard(confirmation)
                        .transition(.opacity.combined(with: .move(edge: .top)))
                }

                if let label = policy.label, policy.state == .guidanceAvailable {
                    ImpactCard(label: label, isRecycled: policy.group == .recyclable) {
                        showImpactInfo = true
                    }
                    .id(label)
                }

                if !policy.steps.isEmpty {
                    stepsCard(policy)
                }

                if policy.state != .confirmationRequired {
                    recyclingIdeasLink
                }

                addToGalleryButton(policy)
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 16)
            .animation(.snappy, value: policy)
        }
        .scrollIndicators(.hidden)
        .background(alignment: .top) { hero }
        .navigationTitle("")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) { shareButton(policy) }
        }
        .tint(.white)
        .sheet(isPresented: $showCorrection) {
            CorrectionSheet(detectedName: policy.displayName, currentLabel: effectiveLabel) { label in
                applyCorrection(label)
            }
        }
        .sheet(isPresented: $showImpactInfo) {
            if let label = policy.label {
                ImpactInfoSheet(label: label, isRecycled: policy.group == .recyclable)
            }
        }
    }

    // MARK: - Hero image

    private var hero: some View {
        ZStack(alignment: .top) {
            Theme.page
            Group {
                if let image = capturedImage {
                    Image(uiImage: image).resizable().scaledToFill()
                } else {
                    LinearGradient(colors: [Color(hex: 0x12301E), Color(hex: 0x2C5A3C)], startPoint: .top, endPoint: .bottom)
                }
            }
            .frame(height: 400)
            .frame(maxWidth: .infinity)
            .clipped()
            LinearGradient(
                stops: [
                    .init(color: Color(hex: 0x081A0F, opacity: 0.42), location: 0),
                    .init(color: Color(hex: 0x081A0F, opacity: 0.08), location: 0.3),
                    .init(color: Theme.page.opacity(0.5), location: 0.82),
                    .init(color: Theme.page, location: 1),
                ],
                startPoint: .top, endPoint: .bottom
            )
            .frame(height: 401)
        }
        .ignoresSafeArea()
        .accessibilityHidden(true)
    }

    // MARK: - Title

    private func titleCard(_ policy: PolicyResult) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top, spacing: 10) {
                Text(policy.displayName)
                    .font(.system(size: 30, weight: .bold))
                    .tracking(-1)
                    .foregroundStyle(Theme.ink)
                    .frame(maxWidth: .infinity, alignment: .leading)
                if policy.rewardPoints > 0 {
                    HStack(spacing: 4) {
                        Text("+\(policy.rewardPoints)")
                        Image(systemName: "leaf.fill").font(.system(size: 13))
                    }
                    .font(.system(size: 15, weight: .bold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 7)
                    .background(Capsule().fill(Theme.primaryGradient))
                    .shadow(color: Theme.green.opacity(0.3), radius: 5, y: 4)
                    .accessibilityLabel(Text("\(policy.rewardPoints) leaves"))
                }
            }

            FlowLayout(spacing: 8) {
                if let label = policy.label {
                    tag(label.materialName, systemImage: "tag.fill", foreground: label.tagTextColor, background: label.tint.opacity(0.13))
                }
                if let group = policy.group {
                    tag(group.displayName, systemImage: group.symbol, foreground: group.tint, background: group.tint.opacity(0.1))
                }
                if correctedLabel != nil {
                    tag(String(localized: "Corrected by you"), systemImage: "hand.thumbsup.fill",
                        foreground: Theme.ink.opacity(0.7), background: Theme.ink.opacity(0.06))
                } else {
                    tag(String(localized: "\(Int((detection.confidence * 100).rounded()))% match"), systemImage: nil,
                        foreground: Theme.ink.opacity(0.7), background: Theme.ink.opacity(0.06))
                }
            }

            Text(policy.summary)
                .font(.system(size: 15))
                .lineSpacing(3)
                .foregroundStyle(Theme.ink.opacity(0.78))
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(20)
        .glass(.cardStrong, cornerRadius: 26)
    }

    private func tag(_ text: String, systemImage: String?, foreground: Color, background: Color) -> some View {
        HStack(spacing: 6) {
            if let systemImage {
                Image(systemName: systemImage).font(.system(size: 12))
            }
            Text(text)
        }
        .font(.system(size: 13, weight: .semibold))
        .foregroundStyle(foreground)
        .padding(.horizontal, 12)
        .padding(.vertical, 7)
        .background(Capsule().fill(background))
    }

    // MARK: - Feedback

    private func feedbackCard(_ policy: PolicyResult) -> some View {
        HStack(spacing: 9) {
            if feedback == nil {
                Text("Was this detection correct?")
                    .font(.system(size: 14.5, weight: .semibold))
                    .foregroundStyle(Theme.ink)
                Spacer(minLength: 0)
                feedbackButton("Yes", tint: Theme.green) { confirmDetection() }
                feedbackButton("No", tint: Theme.ink.opacity(0.7)) { showCorrection = true }
            } else {
                Image(systemName: "checkmark.circle.fill").foregroundStyle(Theme.green)
                Text("Thanks for the feedback!")
                    .font(.system(size: 14.5, weight: .semibold))
                    .foregroundStyle(Theme.ink)
                Spacer(minLength: 0)
                if correctedLabel != nil {
                    Button("Undo") { undoCorrection() }
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(Theme.green)
                }
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, feedback == nil ? 14 : 16)
        .glass(.card, cornerRadius: 22)
    }

    private func feedbackButton(_ title: LocalizedStringKey, tint: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(tint)
                .frame(minWidth: 50)
                .padding(.horizontal, 15)
                .padding(.vertical, 9)
                .background(Capsule().fill(tint.opacity(0.1)))
                .overlay(Capsule().strokeBorder(tint.opacity(0.16), lineWidth: 0.5))
        }
        .buttonStyle(PressableStyle())
    }

    private func confirmDetection() {
        record(.confirmed)
        withAnimation(.snappy) { feedback = .confirmed }
    }

    private func applyCorrection(_ label: String) {
        record(.corrected(to: label))
        withAnimation(.snappy) {
            correctedLabel = label
            choiceID = nil
            feedback = .corrected(to: label)
        }
    }

    private func undoCorrection() {
        withAnimation(.snappy) {
            correctedLabel = nil
            choiceID = nil
            feedback = nil
        }
    }

    private func record(_ verdict: DetectionFeedback.Verdict) {
        DetectionFeedbackLog.shared.record(DetectionFeedback(
            scanEventID: scanEventID,
            predictedLabel: detection.label,
            confidence: detection.confidence,
            verdict: verdict,
            date: .now
        ))
    }

    // MARK: - Confirmation question

    private func confirmationCard(_ confirmation: PolicyConfirmation) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                IconTile(systemImage: "questionmark", tint: Theme.orangeDeep)
                Text(confirmation.question)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(Theme.ink)
                    .fixedSize(horizontal: false, vertical: true)
            }
            ForEach(confirmation.choices) { choice in
                Button {
                    withAnimation(.snappy) { choiceID = choice.id }
                } label: {
                    Text(choice.title)
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(Theme.ink)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 13)
                        .background(RoundedRectangle(cornerRadius: 16, style: .continuous).fill(.white.opacity(0.85)))
                        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(Theme.ink.opacity(0.08), lineWidth: 0.5))
                }
                .buttonStyle(PressableStyle())
            }
        }
        .padding(18)
        .glass(.card, cornerRadius: 26)
    }

    // MARK: - Steps

    private func stepsCard(_ policy: PolicyResult) -> some View {
        let recyclable = policy.group == .recyclable
        let title = policy.label?.stepsTitle(recyclable: recyclable) ?? String(localized: "What to do")
        return VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 8) {
                IconTile(systemImage: "arrow.triangle.2.circlepath")
                Text(title)
                    .font(.system(size: 16, weight: .semibold))
                    .tracking(-0.24)
                    .foregroundStyle(Theme.ink)
                Spacer(minLength: 0)
                if choiceID != nil {
                    Button("Change answer") {
                        withAnimation(.snappy) { choiceID = nil }
                    }
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(Theme.green)
                }
            }

            VStack(alignment: .leading, spacing: 11) {
                ForEach(Array(policy.steps.enumerated()), id: \.offset) { index, step in
                    HStack(alignment: .top, spacing: 11) {
                        Text("\(index + 1)")
                            .font(.system(size: 11, weight: .bold))
                            .foregroundStyle(Theme.green)
                            .frame(width: 21, height: 21)
                            .background(RoundedRectangle(cornerRadius: 7, style: .continuous).fill(Theme.green.opacity(0.13)))
                        Text(step)
                            .font(.system(size: 15))
                            .lineSpacing(2)
                            .foregroundStyle(Theme.ink.opacity(0.82))
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }

            if let group = policy.group {
                Label {
                    Text(group.destination)
                        .fixedSize(horizontal: false, vertical: true)
                } icon: {
                    Image(systemName: "mappin.and.ellipse").foregroundStyle(group.tint)
                }
                .font(.system(size: 13.5))
                .foregroundStyle(Theme.ink.opacity(0.72))
            }

            ForEach(policy.notes, id: \.self) { note in
                Text("Tip: \(note)")
                    .font(.system(size: 13))
                    .lineSpacing(2)
                    .foregroundStyle(Theme.ink.opacity(0.6))
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 10)
                    .background(RoundedRectangle(cornerRadius: 14, style: .continuous).fill(Theme.green.opacity(0.07)))
            }
        }
        .padding(18)
        .glass(.card, cornerRadius: 26)
    }

    private var recyclingIdeasLink: some View {
        Button(action: openRecyclingIdeas) {
            HStack(spacing: 10) {
                IconTile(systemImage: "lightbulb.fill", tint: Theme.orangeDeep)
                Text("Want to give it a second life? See recycling ideas")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundStyle(Theme.ink.opacity(0.78))
                    .multilineTextAlignment(.leading)
                Spacer(minLength: 0)
                Image(systemName: "chevron.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(Theme.ink.opacity(0.3))
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 13)
            .glass(.card, cornerRadius: 22)
        }
        .buttonStyle(PressableStyle())
    }

    private func openRecyclingIdeas() {
        onDismiss()
        NavigationManager.shared.switchToGallery()
    }

    // MARK: - Share

    @ViewBuilder
    private func shareButton(_ policy: PolicyResult) -> some View {
        let message = String(localized: "I just sorted a \(policy.displayName.lowercased()) with AWARE ♻️")
        if let capturedImage {
            ShareLink(item: Image(uiImage: capturedImage), message: Text(message),
                      preview: SharePreview(policy.displayName, image: Image(uiImage: capturedImage))) {
                Image(systemName: "square.and.arrow.up")
            }
        } else {
            ShareLink(item: message) {
                Image(systemName: "square.and.arrow.up")
            }
        }
    }

    // MARK: - Gallery and reward

    private func addToGalleryButton(_ policy: PolicyResult) -> some View {
        let needsAnswer = policy.state == .confirmationRequired
        return Button { handleAddToGallery(policy) } label: {
            Label(needsAnswer ? LocalizedStringKey("Answer the question above first") : LocalizedStringKey("Add to Gallery"),
                  systemImage: "photo.badge.plus")
        }
        .buttonStyle(PrimaryButtonStyle())
        .disabled(needsAnswer)
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
}

// MARK: - Preview

#Preview("Plastic bottle") {
    NavigationStack {
        ScanResultsView(
            detection: YOLODetection(id: 0, label: "plastic_bottle", confidence: 0.9, boundingBox: .zero),
            capturedImage: UIImage(named: "SampleImage"),
            onDismiss: {}
        )
    }
    .preferredColorScheme(.dark)
}

#Preview("Glass (per kg)") {
    NavigationStack {
        ScanResultsView(
            detection: YOLODetection(id: 0, label: "glass_container", confidence: 0.87, boundingBox: .zero),
            capturedImage: nil,
            onDismiss: {}
        )
    }
    .preferredColorScheme(.dark)
}

#Preview("Cup (needs confirmation)") {
    NavigationStack {
        ScanResultsView(
            detection: YOLODetection(id: 0, label: "disposable_cup", confidence: 0.84, boundingBox: .zero),
            capturedImage: nil,
            onDismiss: {}
        )
    }
    .preferredColorScheme(.dark)
}
