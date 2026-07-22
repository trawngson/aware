import Foundation

// MARK: - Label Mappings

struct LabelMappings {
    //0: 'battery', 1: 'disposable cup', 2: 'glass', 3: 'metal can', 4: 'organics', 5: 'plastic bag', 6: 'plastic bottle', 7: 'plastic bottle cap', 8: 'plastic container', 9: 'plastic cutlery', 10: 'straw', 11: 'styrofoam', 12: 'toothbrush'}
    
    // Manual mapping for SF Symbols icons
    static let iconNames: [String: String] = [
        // COCO classes (0-79)
        "battery": "minus.plus.and.fluid.batteryblock",
        "disposable cup": "takeoutbag.and.cup.and.straw.fill",
        "glass": "wineglass.fill",
        "metal can": "shippingbox.fill", // no icon yet
        "organics": "carrot.fill",
        "plastic bag": "bag.fill",
        "plastic bottle": "waterbottle.fill",
        "plastic bottle cap": "circle.fill",
        "plastic container": "tray.fill",
        "plastic cutlery": "fork.knife",
        "straw": "takeoutbag.and.cup.and.straw.fill",
        "styrofoam": "tray.fill",
        "toothbrush": "shippingbox.fill" // no icon yet
    ]
    
    static func formatLabel(_ label: String) -> String {
        return label.capitalized
    }
    
    static func iconForLabel(_ label: String) -> String {
        return iconNames[label.lowercased()] ?? "shippingbox.fill"
    }
}
