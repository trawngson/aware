import SwiftUI

struct ExpandableText: View {
    let shortText: String
    let fullText: String
    
    @State private var isExpanded: Bool = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(isExpanded ? fullText : shortText)
                .font(.body)
                .foregroundStyle(.primary)
            
            if fullText.count > shortText.count {
                Button(isExpanded ? "less" : "more") {
                    withAnimation(.easeInOut(duration: 0.2)) {
                        isExpanded.toggle()
                    }
                }
                .font(.body)
                .foregroundStyle(.blue)
            }
        }
    }
}

#Preview {
    ExpandableText(
        shortText: "This is a short preview of the text that will be shown initially...",
        fullText: "This is a short preview of the text that will be shown initially. When you tap 'more', you'll see this complete text with all the additional information included."
    )
    .padding()
}
