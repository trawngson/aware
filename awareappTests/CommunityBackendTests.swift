import Foundation
import Testing
import UIKit
@testable import awareapp

struct BackendConfigTests {

    @Test func emptyValuesMeanNoBackend() {
        #expect(BackendConfig(urlString: "", anonKey: "") == nil)
        #expect(BackendConfig(urlString: "https://abc.supabase.co", anonKey: "  ") == nil)
        #expect(BackendConfig(urlString: "not a url", anonKey: "key") == nil)
        #expect(BackendConfig(urlString: " https://abc.supabase.co ", anonKey: "key")?.url.host == "abc.supabase.co")
    }

    @Test func launchArgumentTurnsTheBackendOff() throws {
        let defaults = try #require(UserDefaults(suiteName: "BackendConfigTests"))
        defaults.set(true, forKey: BackendConfig.disabledArgument)
        #expect(BackendConfig.load(defaults: defaults) == nil)
        defaults.removePersistentDomain(forName: "BackendConfigTests")
    }
}

@MainActor
struct LedgerSyncTests {

    private func response(_ state: ScanAwardResponse.State, points: Int, reason: String, id: UUID) -> ScanAwardResponse {
        ScanAwardResponse(state: state, points: points, reasonCode: reason, scanEventID: id)
    }

    @Test func awardedScansWaitForTheServer() {
        let ledger = RewardLedger()
        let event = UUID()
        ledger.award(RecyclingPolicy.evaluate(modelLabel: "disposable_cup", choiceID: "paper"), scanEventID: event)
        let pending = ledger.pendingScans()
        #expect(pending.map(\.id) == [event])
        #expect(pending.first?.choiceID == "paper")
        #expect(pending.first?.awardRequest.confirmed == true)
        #expect(ledger.totalPoints == RecyclingPolicy.recyclablePoints)
    }

    @Test func theServerHasTheFinalSay() {
        let ledger = RewardLedger()
        let event = UUID()
        ledger.award(RecyclingPolicy.evaluate(modelLabel: "metal_can"), scanEventID: event)
        ledger.applyServerResult(response(.ineligible, points: 0, reason: "daily_cap_reached", id: event), to: event)
        #expect(ledger.totalPoints == 0)
        #expect(ledger.pendingScans().isEmpty)
        #expect(ledger.scans.first?.syncState == .synced)
        // Still the same event: it can't be awarded again.
        #expect(ledger.award(RecyclingPolicy.evaluate(modelLabel: "metal_can"), scanEventID: event).state == .alreadyAwarded)
    }

    @Test func rejectedScansStopBlockingTheQueue() {
        let ledger = RewardLedger()
        let event = UUID()
        ledger.award(RecyclingPolicy.evaluate(modelLabel: "plastic_bottle"), scanEventID: event)
        ledger.markRejected(event)
        #expect(ledger.pendingScans().isEmpty)
        #expect(ledger.totalPoints == 0)
    }

    @Test func dailyCapOnlyWithABackend() {
        let ledger = RewardLedger()
        for _ in 0..<3 {
            #expect(ledger.award(RecyclingPolicy.evaluate(modelLabel: "metal_can"), scanEventID: UUID()).state == .eligible)
        }
        ledger.dailyCap = 70
        let capped = ledger.award(RecyclingPolicy.evaluate(modelLabel: "metal_can"), scanEventID: UUID())
        #expect(capped.state == .ineligible)
        #expect(capped.reason == "daily_cap_reached")
        #expect(ledger.award(RecyclingPolicy.evaluate(modelLabel: "plastic_bag"), scanEventID: UUID()).state == .eligible)
    }

    @Test func restoresScansFromTheServerOnce() throws {
        let ledger = RewardLedger()
        let json = """
        [{"id": "6B1F2C8E-2D4A-4E61-9B4B-0A1D7E3C5F99", "label": "glass_container", "choice_id": null,
          "policy_version": "hanoi-2026.1", "disposal_group": "recyclable", "points_awarded": 20,
          "reward_state": "eligible", "reason_code": "sorted_recyclable", "scanned_at": "2026-09-20T10:00:00Z"}]
        """
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let events = try decoder.decode([RemoteScanEvent].self, from: Data(json.utf8))
        ledger.restore(events)
        ledger.restore(events)
        #expect(ledger.scans.count == 1)
        #expect(ledger.totalPoints == 20)
        #expect(ledger.pendingScans().isEmpty)
    }
}

struct PersonalStatsTests {

    private let calendar: Calendar = {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "Asia/Ho_Chi_Minh")!
        return calendar
    }()

    private func date(_ text: String) -> Date {
        let formatter = ISO8601DateFormatter()
        return formatter.date(from: text + "+07:00")!
    }

    private func scan(_ label: String, _ when: String, choice: String? = nil) -> ScanSnapshot {
        let policy = RecyclingPolicy.evaluate(modelLabel: label, choiceID: choice)
        return ScanSnapshot(id: UUID(), label: label, choiceID: policy.choiceID, policyVersion: policy.policyVersion,
                            group: policy.group?.rawValue, points: policy.rewardPoints, reasonCode: "test",
                            scannedAt: date(when), syncState: .pending)
    }

    @Test func noScansMeansZeros() {
        let stats = PersonalStats(scans: [], now: date("2026-09-26T10:00:00"), calendar: calendar)
        #expect(stats.points == 0)
        #expect(stats.currentStreak == 0)
        #expect(stats.thisWeek.count == 7)
        #expect(stats.pointsToGoal == PersonalStats.monthlyGoal)
    }

    @Test func totalsStreaksAndWeeks() {
        // 2026-09-26 is a Saturday; its week starts on Monday the 21st.
        let scans = [
            scan("plastic_bottle", "2026-09-26T09:00:00"),
            scan("metal_can", "2026-09-26T08:00:00"),
            scan("plastic_bag", "2026-09-25T20:00:00"),
            scan("glass_container", "2026-09-24T20:00:00"),
            scan("cardboard", "2026-09-20T10:00:00", choice: "clean"),
            scan("styrofoam", "2026-08-31T23:30:00"),
        ]
        let stats = PersonalStats(scans: scans, now: date("2026-09-26T10:00:00"), calendar: calendar)
        #expect(stats.points == 20 + 20 + 10 + 20 + 20 + 10)
        #expect(stats.currentStreak == 3)
        #expect(stats.thisWeek.map(\.scans) == [0, 0, 0, 1, 1, 2, 0])
        #expect(stats.lastWeek.map(\.scans) == [0, 0, 0, 0, 0, 0, 1])
        #expect(stats.categoriesThisMonth[.plastic] == 2)
        #expect(stats.categoriesThisMonth[.paper] == 1)
        #expect(stats.lastMonth.scans == 1)
        // Recycled only: bottle 10 g, can 13 g, glass jar 350 g, small box 200 g.
        #expect(abs(stats.wasteGrams - 573) < 0.001)
        #expect(abs(stats.co2Grams - (12 + 131 + 115.5 + 732)) < 0.001)
        #expect(stats.recent.map(\.label) == ["plastic_bottle", "metal_can", "plastic_bag"])
    }
}

@MainActor
struct GalleryTests {

    @Test func failuresGetFriendlyMessages() {
        #expect(GalleryMessage.failure(BackendError.unreachable).title == String(localized: "You're offline"))
        #expect(GalleryMessage.failure(BackendError.contentNotAllowed).title == String(localized: "Let's keep it friendly"))
        #expect(GalleryMessage.failure(BackendError.rejected("banned")).title == String(localized: "That didn't work"))
        #expect(GalleryMessage.failure(URLError(.badServerResponse)).title == String(localized: "Something went wrong"))
    }

    @Test func photosAreShrunkForUpload() throws {
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        let big = UIGraphicsImageRenderer(size: CGSize(width: 4_000, height: 3_000), format: format).image { context in
            UIColor.systemGreen.setFill()
            context.fill(CGRect(x: 0, y: 0, width: 4_000, height: 3_000))
        }
        let jpeg = try #require(ImageUpload.jpeg(from: big))
        let decoded = try #require(UIImage(data: jpeg))
        #expect(max(decoded.size.width, decoded.size.height) <= ImageUpload.maxDimension)
        #expect(jpeg.count <= ImageUpload.maxBytes)
    }

    @Test func postAges() {
        let now = Date()
        #expect(GalleryStore.age(of: now.addingTimeInterval(-20), now: now) == String(localized: "Just now"))
        #expect(GalleryStore.age(of: now.addingTimeInterval(-5 * 60), now: now) == "5m")
        #expect(GalleryStore.age(of: now.addingTimeInterval(-3 * 3_600), now: now) == "3h")
        #expect(GalleryStore.age(of: now.addingTimeInterval(-2 * 86_400), now: now) == "2d")
    }
}
