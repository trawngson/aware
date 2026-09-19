import Foundation
import Testing
@testable import awareapp

struct RecyclingPolicyTests {

    @Test func everyCanonicalLabelHasExplicitGuidance() {
        for label in CanonicalLabel.allCases {
            let result = RecyclingPolicy.evaluate(modelLabel: label.rawValue)
            #expect(result.label == label)
            #expect(result.state != .unsupported)
            #expect(result.policyVersion == RecyclingPolicy.version)
            if result.state == .guidanceAvailable {
                #expect(result.group != nil)
                #expect(!result.steps.isEmpty)
            }
        }
    }

    @Test func labelOrderMatchesTheFrozenOntology() {
        #expect(CanonicalLabel.allCases.map(\.rawValue) == [
            "plastic_bottle", "glass_container", "metal_can", "cardboard",
            "plastic_bag", "disposable_cup", "styrofoam",
        ])
    }

    @Test(arguments: ["bottle", "plastic", "plastic bottle", "Plastic_Bottle", "can", "person", ""])
    func nearMissLabelsAreNeverSubstringMatched(label: String) {
        let result = RecyclingPolicy.evaluate(modelLabel: label)
        #expect(result.state == .unsupported)
        #expect(result.group == nil)
        #expect(result.rewardPoints == 0)
    }

    @Test func hanoiGroupAssignments() {
        #expect(RecyclingPolicy.evaluate(modelLabel: "plastic_bottle").group == .recyclable)
        #expect(RecyclingPolicy.evaluate(modelLabel: "glass_container").group == .recyclable)
        #expect(RecyclingPolicy.evaluate(modelLabel: "metal_can").group == .recyclable)
        #expect(RecyclingPolicy.evaluate(modelLabel: "plastic_bag").group == .other)
        #expect(RecyclingPolicy.evaluate(modelLabel: "styrofoam").group == .other)
    }

    @Test func cupAndCardboardWaitForTheUsersAnswer() {
        for label in ["disposable_cup", "cardboard"] {
            let pending = RecyclingPolicy.evaluate(modelLabel: label)
            #expect(pending.state == .confirmationRequired)
            #expect(pending.group == nil)
            #expect(pending.confirmation != nil)
            for choice in pending.confirmation?.choices ?? [] {
                let answered = RecyclingPolicy.evaluate(modelLabel: label, choiceID: choice.id)
                #expect(answered.state == .guidanceAvailable)
                #expect(answered.group == choice.group)
                #expect(!answered.steps.isEmpty)
            }
        }
        #expect(RecyclingPolicy.evaluate(modelLabel: "disposable_cup", choiceID: "paper").group == .recyclable)
        #expect(RecyclingPolicy.evaluate(modelLabel: "disposable_cup", choiceID: "plastic").group == .recyclable)
        #expect(RecyclingPolicy.evaluate(modelLabel: "disposable_cup", choiceID: "foam").group == .other)
        #expect(RecyclingPolicy.evaluate(modelLabel: "cardboard", choiceID: "clean").group == .recyclable)
        #expect(RecyclingPolicy.evaluate(modelLabel: "cardboard", choiceID: "soiled").group == .other)
    }
}

@MainActor
struct RewardLedgerTests {

    @Test func awardsEachScanEventAtMostOnce() {
        let ledger = RewardLedger()
        let event = UUID()
        let policy = RecyclingPolicy.evaluate(modelLabel: "metal_can")
        #expect(ledger.award(policy, scanEventID: event).state == .eligible)
        #expect(ledger.award(policy, scanEventID: event).state == .alreadyAwarded)
        #expect(ledger.totalPoints == RecyclingPolicy.recyclablePoints)
    }

    @Test func noPointsBeforeConfirmation() {
        let ledger = RewardLedger()
        let event = UUID()
        let pending = RecyclingPolicy.evaluate(modelLabel: "cardboard")
        #expect(ledger.award(pending, scanEventID: event).state == .confirmationRequired)
        #expect(ledger.totalPoints == 0)
        let answered = RecyclingPolicy.evaluate(modelLabel: "cardboard", choiceID: "soiled")
        #expect(ledger.award(answered, scanEventID: event).points == RecyclingPolicy.otherWastePoints)
    }

    @Test func unsupportedLabelsEarnNothing() {
        let ledger = RewardLedger()
        let result = ledger.award(RecyclingPolicy.evaluate(modelLabel: "person"), scanEventID: UUID())
        #expect(result.state == .ineligible)
        #expect(ledger.totalPoints == 0)
    }
}
