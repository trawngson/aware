import Foundation
import SwiftData

/// A rewarded scan saved on the phone. Scans work offline: they are saved
/// here first and sent to the server (if there is one) when the phone is
/// online. Records still marked `pending` are the sync queue.
@Model
final class ScanRecord {
    /// The scan event ID, shared with the server.
    @Attribute(.unique) var id: UUID
    var label: String
    var choiceID: String?
    var policyVersion: String
    var group: String?
    var points: Int
    var reasonCode: String
    var scannedAt: Date
    var syncStateRaw: String

    init(_ snapshot: ScanSnapshot) {
        id = snapshot.id
        label = snapshot.label
        choiceID = snapshot.choiceID
        policyVersion = snapshot.policyVersion
        group = snapshot.group
        points = snapshot.points
        reasonCode = snapshot.reasonCode
        scannedAt = snapshot.scannedAt
        syncStateRaw = snapshot.syncState.rawValue
    }

    var snapshot: ScanSnapshot {
        ScanSnapshot(id: id, label: label, choiceID: choiceID, policyVersion: policyVersion, group: group,
                     points: points, reasonCode: reasonCode, scannedAt: scannedAt,
                     syncState: ScanSnapshot.SyncState(rawValue: syncStateRaw) ?? .pending)
    }

    func update(from snapshot: ScanSnapshot) {
        points = snapshot.points
        reasonCode = snapshot.reasonCode
        syncStateRaw = snapshot.syncState.rawValue
    }
}

/// The app's SwiftData store: scans and cached community content. Falls back
/// to memory if the file can't be opened, so the app still runs (without
/// keeping anything across launches).
@MainActor
final class LocalStore {
    static let shared = LocalStore()

    let container: ModelContainer
    var context: ModelContext { container.mainContext }

    init(inMemory: Bool = false) {
        let schema = Schema([ScanRecord.self, CachedContent.self])
        let configuration = ModelConfiguration(schema: schema, isStoredInMemoryOnly: inMemory)
        if let container = try? ModelContainer(for: schema, configurations: [configuration]) {
            self.container = container
        } else {
            // Only reached if the file store fails; memory storage doesn't.
            let memory = ModelConfiguration(schema: schema, isStoredInMemoryOnly: true)
            self.container = try! ModelContainer(for: schema, configurations: [memory])
        }
    }

    func allScans() -> [ScanSnapshot] {
        let descriptor = FetchDescriptor<ScanRecord>(sortBy: [SortDescriptor(\.scannedAt, order: .reverse)])
        return ((try? context.fetch(descriptor)) ?? []).map(\.snapshot)
    }

    /// Inserts or updates scans by ID.
    func save(_ snapshots: [ScanSnapshot]) {
        guard !snapshots.isEmpty else { return }
        let ids = snapshots.map(\.id)
        let descriptor = FetchDescriptor<ScanRecord>(predicate: #Predicate { ids.contains($0.id) })
        let existing = Dictionary(((try? context.fetch(descriptor)) ?? []).map { ($0.id, $0) },
                                  uniquingKeysWith: { first, _ in first })
        for snapshot in snapshots {
            if let record = existing[snapshot.id] {
                record.update(from: snapshot)
            } else {
                context.insert(ScanRecord(snapshot))
            }
        }
        try? context.save()
    }

    /// Removes the scans with these IDs.
    func deleteScans(_ ids: [UUID]) {
        guard !ids.isEmpty else { return }
        let descriptor = FetchDescriptor<ScanRecord>(predicate: #Predicate { ids.contains($0.id) })
        for record in (try? context.fetch(descriptor)) ?? [] {
            context.delete(record)
        }
        try? context.save()
    }

    /// Removes every scan, e.g. after the account is deleted.
    func deleteAllScans() {
        try? context.delete(model: ScanRecord.self)
        try? context.save()
    }
}
