import Foundation
import SwiftData

/// The last community content fetched from the backend (the Gallery feed),
/// kept so it still shows offline. Stored as the JSON the server sent.
@Model
final class CachedContent {
    @Attribute(.unique) var key: String
    var json: Data
    var savedAt: Date

    init(key: String, json: Data, savedAt: Date = .now) {
        self.key = key
        self.json = json
        self.savedAt = savedAt
    }
}

extension LocalStore {
    func cachedContent(_ key: String) -> Data? {
        let descriptor = FetchDescriptor<CachedContent>(predicate: #Predicate { $0.key == key })
        return (try? context.fetch(descriptor))?.first?.json
    }

    func saveContent(_ json: Data, for key: String) {
        let descriptor = FetchDescriptor<CachedContent>(predicate: #Predicate { $0.key == key })
        if let existing = (try? context.fetch(descriptor))?.first {
            existing.json = json
            existing.savedAt = .now
        } else {
            context.insert(CachedContent(key: key, json: json))
        }
        try? context.save()
    }

    /// Removes all cached community content (after deleting the account).
    func deleteCachedContent() {
        try? context.delete(model: CachedContent.self)
        try? context.save()
    }
}
