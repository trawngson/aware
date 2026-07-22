import SwiftUI

struct ScanResultsView: View {
    let detection: YOLODetection
    let capturedImage: UIImage?
    let onDismiss: () -> Void
    let onAddToGallery: (() -> Void)?
    
//    @State private var showingSaveSuccess: Bool = false
    
    private var itemInfo: ItemInfo {
        ItemInfo.info(for: detection.label)
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
        VStack(spacing: 0) {
            // Image Section
            imageSection
            
            // Details Section
            detailsSection
            
            Spacer()
        }
        .background(Color(uiColor: .systemBackground))
//        .overlay {
//            if showingSaveSuccess {
//                saveSuccessOverlay
//            }
//        }
    }
    
    // MARK: - Image Section
    
    private var imageSection: some View {
        Group {
            if let image = capturedImage {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFill()
                    .frame(height: UIScreen.main.bounds.height * 0.40)
                    .clipped()
            } else {
                Rectangle()
                    .fill(Color(uiColor: .systemGray5))
                    .frame(height: UIScreen.main.bounds.height * 0.40)
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        .padding(.horizontal, 20)
    }
    
    // MARK: - Details Section
    
    private var detailsSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Item Name
            Text(itemInfo.displayName)
                .font(.largeTitle)
                .fontWeight(.bold)
            
            // Category Pills
            HStack(spacing: 12) {
                CategoryPill(
                    icon: "tag.fill",
                    text: itemInfo.category,
                    color: .purple
                )
                CategoryPill(
                    icon: "leaf.fill",
                    text: "\(itemInfo.leafPoints)",
                    color: .green
                )
            }
            
            // Description
            ExpandableText(
                shortText: itemInfo.shortDescription,
                fullText: itemInfo.fullDescription
            )
            
            // Bottle-only instructions
            if isBottleClass {
                bottleInstructionsSection
//                recyclingProjects
            }
            
            // Add to Gallery Button
            addToGalleryButton
        }
        .padding(.horizontal, 24)
        .padding(.top, 24)
    }
    
    // MARK: - Specific Recycling Instructions
    
    private var isBottleClass: Bool {
        let normalized = detection.label
            .lowercased()
            .replacingOccurrences(of: "_", with: " ")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return normalized == "bottle" || normalized == "plastic bottle"
    }
    
//    private var recyclingProjects: some View {
//        
//    }
    
    private var bottleInstructionsSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("How to recycle this bottle", systemImage: "arrow.triangle.2.circlepath")
                .font(.headline)
                .foregroundStyle(.green)
            
            instructionRow(number: 1, text: "Empty any remaining liquid.")
            instructionRow(number: 2, text: "Quick-rinse to remove residue.")
            instructionRow(number: 3, text: "Put cap back on if your local program accepts capped bottles.")
            instructionRow(number: 4, text: "Place in plastics recycling bin (PET/HDPE where supported).")
            
            Text("Tip: Avoid crushing unless your local guidance says it is okay.")
                .font(.footnote)
                .foregroundStyle(.secondary)
                .padding(.top, 2)
        }
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(Color.green.opacity(0.08))
        )
    }
    
    private func instructionRow(number: Int, text: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Text("\(number).")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.green)
            Text(text)
                .font(.subheadline)
                .foregroundStyle(.primary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
    
    // MARK: - Add to Gallery Button
    
    private var addToGalleryButton: some View {
        Button(action: handleAddToGallery) {
            HStack(spacing: 8) {
                Image(systemName: "photo.badge.plus")
                    .font(.body.weight(.semibold))
                Text("Add to Gallery")
                    .font(.headline)
            }
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(Color.green)
            .clipShape(Capsule())
        }
        .padding(.top, 8)
    }
    
    private func handleAddToGallery() {
        // Add post directly to gallery
        GalleryStore.shared.addPostFromScan(
            image: capturedImage,
            itemName: itemInfo.displayName,
            leafPoints: itemInfo.leafPoints
        )
        
        // Call the callback
        onAddToGallery?()
        
        // Dismiss results and switch to Gallery tab
        onDismiss()
        NavigationManager.shared.switchToGallery()
    }
    
    // MARK: - Save Success Overlay
    
//    private var saveSuccessOverlay: some View {
//        VStack(spacing: 12) {
//            Image(systemName: "checkmark.circle.fill")
//                .font(.system(size: 48))
//                .foregroundStyle(.green)
//            Text("Added to Gallery!")
//                .font(.headline)
//        }
//        .padding(32)
//        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
//        .transition(.scale.combined(with: .opacity))
//    }
}


// MARK: - Specific Recycling Instructions

// MARK: - Preview

#Preview {
    ScanResultsView(
        detection: YOLODetection(
            id: 0,
            label: "plastic bottle",
            confidence: 0.95,
            boundingBox: .zero
        ),
        capturedImage: nil,
        onDismiss: {}
    )
}

// bỏ hết COCO ra, chỉ cho TACO
// train lại từ đầu, train trên COCO100
// https://docs.roboflow.com/datasets/merge-datasets
