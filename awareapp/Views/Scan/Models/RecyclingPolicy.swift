import Foundation

// MARK: - Canonical labels

/// The frozen ontology classes (backend/ontology.yaml, aware-ontology-v3), in
/// model class order. Labels are matched exactly, never by substring.
enum CanonicalLabel: String, CaseIterable, Identifiable {
    case plasticBottle = "plastic_bottle"
    case glassContainer = "glass_container"
    case metalCan = "metal_can"
    case cardboard = "cardboard"
    case plasticBag = "plastic_bag"
    case disposableCup = "disposable_cup"
    case styrofoam = "styrofoam"

    var id: String { rawValue }

    init?(modelLabel: String) {
        self.init(rawValue: modelLabel.trimmingCharacters(in: .whitespacesAndNewlines))
    }

    var displayName: String {
        switch self {
        case .plasticBottle: String(localized: "Plastic bottle")
        case .glassContainer: String(localized: "Glass bottle or jar")
        case .metalCan: String(localized: "Metal can")
        case .cardboard: String(localized: "Cardboard")
        case .plasticBag: String(localized: "Plastic bag")
        case .disposableCup: String(localized: "Disposable cup")
        case .styrofoam: String(localized: "Styrofoam")
        }
    }

    var iconName: String {
        switch self {
        case .plasticBottle: "waterbottle.fill"
        case .glassContainer: "wineglass.fill"
        case .metalCan: "cylinder.fill"
        case .cardboard: "shippingbox.fill"
        case .plasticBag: "bag.fill"
        case .disposableCup: "cup.and.saucer.fill"
        case .styrofoam: "square.stack.3d.up.fill"
        }
    }
}

// MARK: - Disposal groups (Law on Environmental Protection 2020, Art. 75)

enum DisposalGroup: String {
    case recyclable
    case foodWaste
    case other
    case hazardous

    var displayName: String {
        switch self {
        case .recyclable: String(localized: "Recyclable")
        case .foodWaste: String(localized: "Food waste")
        case .other: String(localized: "Other waste")
        case .hazardous: String(localized: "Hazardous waste")
        }
    }

    /// Where the item goes in Hanoi.
    var destination: String {
        switch self {
        case .recyclable:
            String(localized: "Keep it separate from food and other waste, then give or sell it to a scrap collector (ve chai, đồng nát).")
        case .foodWaste:
            String(localized: "Put it in the green food-waste bag.")
        case .other:
            String(localized: "Put it in the grey bag for other household waste.")
        case .hazardous:
            String(localized: "Keep it apart from all other waste in a sealed, leak-proof container and hand it over at a hazardous-waste collection point.")
        }
    }
}

// MARK: - Policy results

enum PolicyState: Equatable {
    case guidanceAvailable
    case confirmationRequired
    case unsupported
}

struct PolicyChoice: Identifiable, Equatable {
    let id: String
    let title: String
    let group: DisposalGroup
    let steps: [String]
}

struct PolicyConfirmation: Equatable {
    let question: String
    let choices: [PolicyChoice]
}

struct PolicyResult: Equatable {
    let label: CanonicalLabel?
    let state: PolicyState
    let displayName: String
    /// Nil while a confirmation is still needed or when the label is unsupported.
    let group: DisposalGroup?
    let summary: String
    let steps: [String]
    let notes: [String]
    let confirmation: PolicyConfirmation?
    let rewardPoints: Int
    let jurisdiction: String
    let policySource: String
    let policyVersion: String

    var isRewardEligible: Bool { state == .guidanceAvailable && group != nil && rewardPoints > 0 }
}

// MARK: - Hanoi policy table

/// Canonical-label-to-policy table for Hanoi (SPECIFICATION.md 5.3 and 13).
///
/// Groups follow Hanoi People's Committee Decision No. 87 (in force from
/// 8 January 2026), which applies the three groups of the Law on Environmental
/// Protection 2020, Article 75. Item assignments and preparation steps follow
/// the MONRE technical guidance, Official Letter 9368/BTNMT-KSONMT
/// (2 November 2023), developed into practical household instructions.
enum RecyclingPolicy {
    static let version = "hanoi-2026.1"
    static let ontologyVersion = "aware-ontology-v3"

    static var jurisdiction: String { String(localized: "Hanoi, Vietnam") }

    static var source: String {
        String(localized: "Hanoi People's Committee Decision No. 87 (from 8 January 2026); Law on Environmental Protection 2020, Article 75; MONRE guidance 9368/BTNMT-KSONMT (2 November 2023).")
    }

    static let recyclablePoints = 20
    static let otherWastePoints = 10

    static func points(for group: DisposalGroup) -> Int {
        switch group {
        case .recyclable: recyclablePoints
        case .other: otherWastePoints
        case .foodWaste, .hazardous: 0
        }
    }

    /// Evaluates a raw model label. `choiceID` is the user's answer to the
    /// confirmation question, if the item needs one.
    static func evaluate(modelLabel: String, choiceID: String? = nil) -> PolicyResult {
        guard let label = CanonicalLabel(modelLabel: modelLabel) else {
            return unsupported(modelLabel: modelLabel)
        }
        let entry = entry(for: label)
        guard let confirmation = entry.confirmation else {
            return result(label, entry, state: .guidanceAvailable, group: entry.group, steps: entry.steps)
        }
        guard let choiceID, let choice = confirmation.choices.first(where: { $0.id == choiceID }) else {
            return result(label, entry, state: .confirmationRequired, group: nil, steps: [])
        }
        return result(label, entry, state: .guidanceAvailable, group: choice.group, steps: choice.steps)
    }

    private struct Entry {
        let group: DisposalGroup?
        let summary: String
        let steps: [String]
        let notes: [String]
        let confirmation: PolicyConfirmation?
    }

    private static func result(
        _ label: CanonicalLabel,
        _ entry: Entry,
        state: PolicyState,
        group: DisposalGroup?,
        steps: [String]
    ) -> PolicyResult {
        PolicyResult(
            label: label,
            state: state,
            displayName: label.displayName,
            group: group,
            summary: entry.summary,
            steps: steps,
            notes: entry.notes,
            confirmation: state == .confirmationRequired ? entry.confirmation : nil,
            rewardPoints: group.map(points(for:)) ?? 0,
            jurisdiction: jurisdiction,
            policySource: source,
            policyVersion: version
        )
    }

    private static func unsupported(modelLabel: String) -> PolicyResult {
        PolicyResult(
            label: nil,
            state: .unsupported,
            displayName: String(localized: "Not sure what this is"),
            group: nil,
            summary: String(localized: "We couldn't identify this item."),
            steps: [
                String(localized: "Try scanning it again, a little closer and in good light."),
                String(localized: "Still unsure? Put it in other waste so it doesn't end up mixed into recyclables."),
            ],
            notes: [],
            confirmation: nil,
            rewardPoints: 0,
            jurisdiction: jurisdiction,
            policySource: source,
            policyVersion: version
        )
    }

    private static func entry(for label: CanonicalLabel) -> Entry {
        switch label {
        case .plasticBottle:
            return Entry(
                group: .recyclable,
                summary: String(localized: "Plastic bottles are recyclable."),
                steps: [
                    String(localized: "Pour out any liquid left inside."),
                    String(localized: "Quickly rinse bottles that held milk, juice, or sweet drinks so they do not smell or attract insects."),
                    String(localized: "Take off the cap. Keep it: caps are plastic too and go in the same recyclables bag."),
                    String(localized: "For soap or shampoo pump bottles, unscrew the pump. The bottle is recyclable; the pump has a metal spring and goes in other waste."),
                    String(localized: "Squash the bottle flat to save space."),
                ],
                notes: [
                    String(localized: "Bottles that held pesticides, strong chemicals, or motor oil are hazardous waste, not recyclables."),
                ],
                confirmation: nil
            )
        case .glassContainer:
            return Entry(
                group: .recyclable,
                summary: String(localized: "Glass bottles and jars are recyclable."),
                steps: [
                    String(localized: "Take off the lid. Metal lids go with metal recyclables; plastic lids go with plastic recyclables."),
                    String(localized: "Empty the bottle or jar and rinse off food or drink."),
                    String(localized: "Keep it whole. Do not break glass on purpose."),
                    String(localized: "If it is already broken, wrap the pieces in paper or cardboard and write \"broken glass\" on it to protect collectors."),
                ],
                notes: [
                    String(localized: "Light bulbs are hazardous waste. Mirrors, window glass, and ceramics are not bottles or jars; ask your collector before recycling them."),
                ],
                confirmation: nil
            )
        case .metalCan:
            return Entry(
                group: .recyclable,
                summary: String(localized: "Metal cans are recyclable, and scrap collectors will even buy aluminium drink cans."),
                steps: [
                    String(localized: "Empty the can completely and rinse it quickly."),
                    String(localized: "Leave the ring pull attached."),
                    String(localized: "Squash aluminium drink cans flat."),
                    String(localized: "For food tins, push the sharp lid inside the tin so nobody gets cut."),
                ],
                notes: [
                    String(localized: "Spray cans and cans that held paint, pesticide, or oil are hazardous waste, not recyclables."),
                ],
                confirmation: nil
            )
        case .cardboard:
            return Entry(
                group: nil,
                summary: String(localized: "Clean cardboard is recyclable. Greasy, wet, or food-stained cardboard isn't."),
                steps: [],
                notes: [
                    String(localized: "Milk and juice cartons are lined with plastic and foil. Rinse and flatten them, and ask your collector whether they accept them."),
                ],
                confirmation: PolicyConfirmation(
                    question: String(localized: "Is the cardboard clean and dry?"),
                    choices: [
                        PolicyChoice(
                            id: "clean",
                            title: String(localized: "Yes, clean and dry"),
                            group: .recyclable,
                            steps: [
                                String(localized: "Take everything out of the box."),
                                String(localized: "Remove plastic tape, plastic windows, and foam inserts. Foam goes in other waste."),
                                String(localized: "Flatten the box and stack or tie flat boxes together."),
                                String(localized: "Keep it dry and out of the rain. Wet cardboard cannot be recycled."),
                            ]
                        ),
                        PolicyChoice(
                            id: "soiled",
                            title: String(localized: "No, greasy, wet, or food-stained"),
                            group: .other,
                            steps: [
                                String(localized: "Tear off any clean, dry parts and recycle those separately."),
                                String(localized: "Scrape food scraps into the green food-waste bag."),
                                String(localized: "Put the greasy or wet cardboard in other waste."),
                            ]
                        ),
                    ]
                )
            )
        case .plasticBag:
            return Entry(
                group: .other,
                summary: String(localized: "Plastic bags can't be recycled here, so they go in other waste."),
                steps: [
                    String(localized: "Reuse the bag while it is still intact, for example as a bin liner for other waste."),
                    String(localized: "When you throw it away, shake out any food or liquid."),
                    String(localized: "Tie several bags together into one bundle so they do not blow away."),
                    String(localized: "Do not put plastic bags in with recyclables. They get tangled in sorting and lower the value of the whole bag."),
                ],
                notes: [
                    String(localized: "Carrying a reusable shopping bag avoids plastic bags altogether."),
                ],
                confirmation: nil
            )
        case .disposableCup:
            return Entry(
                group: nil,
                summary: String(localized: "Paper and hard plastic cups are recyclable. Foam cups aren't."),
                steps: [],
                notes: [
                    String(localized: "Straws, sealing films, and plastic spoons are not recyclable; put them in other waste."),
                ],
                confirmation: PolicyConfirmation(
                    question: String(localized: "What is the cup made of?"),
                    choices: [
                        PolicyChoice(
                            id: "paper",
                            title: String(localized: "Paper"),
                            group: .recyclable,
                            steps: [
                                String(localized: "Drink or pour out what is left and rinse the cup."),
                                String(localized: "Take off the plastic lid and recycle it with plastics. Put the straw in other waste."),
                                String(localized: "Stack clean paper cups together to save space."),
                            ]
                        ),
                        PolicyChoice(
                            id: "plastic",
                            title: String(localized: "Hard plastic"),
                            group: .recyclable,
                            steps: [
                                String(localized: "Empty the cup. Tapioca pearls, jelly, and ice go in the green food-waste bag."),
                                String(localized: "Peel off the sealing film and remove the straw; both go in other waste."),
                                String(localized: "Rinse the cup and stack it with other clean plastic cups."),
                            ]
                        ),
                        PolicyChoice(
                            id: "foam",
                            title: String(localized: "Foam"),
                            group: .other,
                            steps: [
                                String(localized: "Empty the cup and put any drink or food left in the green food-waste bag."),
                                String(localized: "Put the foam cup in other waste."),
                            ]
                        ),
                    ]
                )
            )
        case .styrofoam:
            return Entry(
                group: .other,
                summary: String(localized: "Styrofoam can't be recycled here, so it goes in other waste."),
                steps: [
                    String(localized: "Scrape food scraps from foam boxes or trays into the green food-waste bag."),
                    String(localized: "Break large foam blocks into smaller pieces so they fit in the bag."),
                    String(localized: "Put the foam in other waste."),
                ],
                notes: [
                    String(localized: "Clean foam boxes are useful for storage. Choosing paper or reusable containers for takeaway avoids foam waste."),
                ],
                confirmation: nil
            )
        }
    }
}
