import Foundation

struct ItemInfo {
    let displayName: String
    let category: String
    let leafPoints: Int
    let shortDescription: String
    let fullDescription: String
    
    static func info(for label: String) -> ItemInfo {
        let normalizedLabel = label.lowercased().replacingOccurrences(of: "_", with: " ")
        
        // Plastic items
        if normalizedLabel.contains("plastic") || normalizedLabel.contains("bottle") {
            return ItemInfo(
                displayName: "Plastic Bottle",
                category: "Plastic",
                leafPoints: 25,
                shortDescription: "Plastic bottles are versatile, lightweight, and durable containers, commonly made from PET (polyethylene terephthalate) or HDPE (high",
                fullDescription: "Plastic bottles are versatile, lightweight, and durable containers, commonly made from PET (polyethylene terephthalate) or HDPE (high-density polyethylene). They are widely used for beverages, cleaning products, and personal care items. Most plastic bottles are recyclable and can be transformed into new bottles, clothing fibers, or other plastic products. Remember to rinse and remove caps before recycling."
            )
        }
        
        // Cardboard items
        if normalizedLabel.contains("cardboard") || normalizedLabel.contains("carton") || normalizedLabel.contains("box") {
            return ItemInfo(
                displayName: "Cardboard",
                category: "Paper",
                leafPoints: 20,
                shortDescription: "Cardboard is a sturdy paper-based material commonly used for packaging and shipping boxes.",
                fullDescription: "Cardboard is a sturdy paper-based material commonly used for packaging and shipping boxes. It's made from recycled paper pulp and is highly recyclable. Flatten boxes before recycling to save space. Remove any tape or labels if possible."
            )
        }
        
        // Metal/Can items
        if normalizedLabel.contains("can") || normalizedLabel.contains("aluminum") || normalizedLabel.contains("metal") {
            return ItemInfo(
                displayName: "Aluminum Can",
                category: "Metal",
                leafPoints: 30,
                shortDescription: "Aluminum cans are lightweight, durable containers commonly used for beverages.",
                fullDescription: "Aluminum cans are lightweight, durable containers commonly used for beverages. They are infinitely recyclable without losing quality, making them one of the most sustainable packaging options. Recycling aluminum saves 95% of the energy needed to make new aluminum."
            )
        }
        
        // Glass items
        if normalizedLabel.contains("glass") || normalizedLabel.contains("jar") {
            return ItemInfo(
                displayName: "Glass Container",
                category: "Glass",
                leafPoints: 20,
                shortDescription: "Glass containers are durable, reusable, and 100% recyclable without loss of quality.",
                fullDescription: "Glass containers are durable, reusable, and 100% recyclable without loss of quality. They can be recycled endlessly, making them one of the most eco-friendly packaging materials. Rinse containers before recycling and remove any lids or caps."
            )
        }
        
        // Paper items
        if normalizedLabel.contains("paper") || normalizedLabel.contains("newspaper") || normalizedLabel.contains("magazine") {
            return ItemInfo(
                displayName: "Paper",
                category: "Paper",
                leafPoints: 15,
                shortDescription: "Paper products are widely recyclable and can be transformed into new paper products.",
                fullDescription: "Paper products are widely recyclable and can be transformed into new paper products. Keep paper dry and free from food contamination. Shredded paper should be placed in a paper bag before recycling."
            )
        }
        
        // Food waste
        if normalizedLabel.contains("food") || normalizedLabel.contains("waste") || normalizedLabel.contains("organic") {
            return ItemInfo(
                displayName: "Food Waste",
                category: "Organic",
                leafPoints: 10,
                shortDescription: "Food waste can be composted to create nutrient-rich soil for gardens.",
                fullDescription: "Food waste can be composted to create nutrient-rich soil for gardens. Composting reduces methane emissions from landfills and returns valuable nutrients to the earth. Consider starting a home compost bin or using a local composting service."
            )
        }
        
        // Default for unknown items
        return ItemInfo(
            displayName: LabelMappings.formatLabel(label),
            category: "General",
            leafPoints: 15,
            shortDescription: "This item may be recyclable depending on your local recycling guidelines.",
            fullDescription: "This item may be recyclable depending on your local recycling guidelines. Check with your local waste management facility for specific instructions on how to properly dispose of or recycle this item. When in doubt, reduce and reuse before recycling."
        )
    }
}
