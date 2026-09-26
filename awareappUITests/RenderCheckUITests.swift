import XCTest

/// Captures screens so their rendering can be checked without a device.
/// `.github/scripts/ios-render-check.sh` runs it once per appearance (Light,
/// Dark) and collects the PNGs; every screenshot is also attached to the result.
///
/// What it does comes from `RENDER_STEPS`: steps separated by `|`, each
/// `command` or `command:argument`. Empty runs `fullTour`.
///
///     launch             (re)launch the app, onboarding skipped
///     onboarding         (re)launch the app showing onboarding
///     tab:<name>         select a tab (Home, Scan, Gallery)
///     tap:<text>         tap the first button whose label contains text
///     tap-text:<text>    tap the first static text whose label contains text
///     back               tap the navigation bar's back button
///     swipe-back         swipe from the left edge
///     scroll:up|down     swipe the screen
///     type:<text>        type into the focused field
///     wait:<seconds>     pause
///     shot:<name>        screenshot, saved as NN-name.png
///
/// The app launches (onboarding skipped) before the first step unless that step
/// is `launch` or `onboarding`. The Scan tab's live camera feed never lets the
/// app go idle, so nothing but `wait` and `shot` may follow `tab:Scan`.
final class RenderCheckUITests: XCTestCase {
    static let fullTour = """
        onboarding | shot:onboarding | launch | shot:home \
        | tap:Waste Saved | shot:waste-saved | back \
        | tap:Recycling Map | wait:1 | shot:recycling-map | back \
        | tap:Recycle Leaderboard | shot:leaderboard | back \
        | tap:Welcome back | shot:more | back \
        | tab:Gallery | shot:gallery | tap-text:I just recycled | shot:post | back \
        | tap:Share what you made | shot:new-post | tap:Cancel \
        | tab:Scan | wait:4 | shot:scan
        """

    private var outputDirectory: URL?
    private var shotCount = 0

    override func setUpWithError() throws {
        continueAfterFailure = false
        let environment = ProcessInfo.processInfo.environment
        if let path = environment["RENDER_DIR"], !path.isEmpty {
            let directory = URL(fileURLWithPath: path, isDirectory: true)
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            outputDirectory = directory
        }
    }

    @MainActor
    func testRenderSteps() throws {
        let script = ProcessInfo.processInfo.environment["RENDER_STEPS"] ?? ""
        let steps = (script.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? Self.fullTour : script)
            .split(separator: "|")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }

        let app = XCUIApplication()
        if let first = steps.first, first != "launch", first != "onboarding" {
            launch(app, showingOnboarding: false)
        }
        for step in steps {
            try perform(step, in: app)
        }
    }

    @MainActor
    private func perform(_ step: String, in app: XCUIApplication) throws {
        let parts = step.split(separator: ":", maxSplits: 1).map { $0.trimmingCharacters(in: .whitespaces) }
        let command = parts.first ?? ""
        let argument = parts.count > 1 ? parts[1] : ""

        switch command {
        case "launch":
            launch(app, showingOnboarding: false)
        case "onboarding":
            launch(app, showingOnboarding: true)
        case "tab":
            let tab = app.tabBars.buttons[argument]
            XCTAssertTrue(tab.waitForExistence(timeout: 5), "No tab named \(argument)")
            tab.tap()
        case "tap":
            let button = app.buttons.containing(NSPredicate(format: "label CONTAINS %@", argument)).firstMatch
            XCTAssertTrue(button.waitForExistence(timeout: 5), "No button labeled \(argument)")
            button.tap()
        case "tap-text":
            let text = app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", argument)).firstMatch
            XCTAssertTrue(text.waitForExistence(timeout: 5), "No text containing \(argument)")
            text.tap()
        case "back":
            let back = app.navigationBars.buttons.firstMatch
            XCTAssertTrue(back.waitForExistence(timeout: 5), "No back button")
            back.tap()
        case "swipe-back":
            let window = app.windows.firstMatch
            window.coordinate(withNormalizedOffset: CGVector(dx: 0.01, dy: 0.55))
                .press(forDuration: 0.05,
                       thenDragTo: window.coordinate(withNormalizedOffset: CGVector(dx: 0.85, dy: 0.55)),
                       withVelocity: 300, thenHoldForDuration: 0.1)
        case "scroll":
            switch argument {
            case "up": app.swipeDown()
            case "down": app.swipeUp()
            default: XCTFail("scroll takes up or down, not \(argument)")
            }
        case "type":
            app.typeText(argument)
        case "wait":
            let seconds = try XCTUnwrap(Double(argument), "wait takes a number of seconds, not \(argument)")
            Thread.sleep(forTimeInterval: seconds)
        case "shot":
            try capture(argument.isEmpty ? "screen" : argument)
        default:
            XCTFail("Unknown render step: \(step)")
        }
    }

    @MainActor
    private func launch(_ app: XCUIApplication, showingOnboarding: Bool) {
        if app.state != .notRunning { app.terminate() }
        // A fresh simulator takes its region from the host (CI runners are
        // en_US), so pin it for screenshots that compare across machines.
        // The tour always runs without a backend, even once one is configured.
        app.launchArguments = ["-hasSeenOnboarding", showingOnboarding ? "NO" : "YES",
                               "-AppleLanguages", "(en-VN)", "-AppleLocale", "en_VN",
                               "-AWAREBackendDisabled", "YES"]
        app.launch()
        let ready = showingOnboarding ? app.buttons["Got it!"] : app.tabBars.buttons["Home"]
        XCTAssertTrue(ready.waitForExistence(timeout: 10), "App did not finish launching")
    }

    /// Waits for animations and map tiles to settle, then saves the screen.
    @MainActor
    private func capture(_ name: String) throws {
        Thread.sleep(forTimeInterval: 2)
        shotCount += 1
        let fileName = String(format: "%02d-%@", shotCount, name)
        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = fileName
        attachment.lifetime = .keepAlways
        add(attachment)
        if let outputDirectory {
            try screenshot.pngRepresentation.write(to: outputDirectory.appendingPathComponent("\(fileName).png"))
        }
    }
}
