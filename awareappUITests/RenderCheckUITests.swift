import XCTest

/// Captures screens so their rendering can be checked without a device.
/// `.github/scripts/ios-render-check.sh` runs it once per appearance (Light,
/// Dark) and collects the PNGs; every screenshot is also attached to the result.
///
/// What it does comes from `RENDER_STEPS`: steps separated by `|`, each
/// `command` or `command:argument`. Empty runs `fullTour`; `readme` runs
/// `readmeTour`, which paces the screens for the README's GIFs.
///
///     launch             (re)launch the app, onboarding skipped
///     onboarding         (re)launch the app showing onboarding
///     tab:<name>         select a tab (Home, Scan, Gallery)
///     tap:<text>         tap the first button whose label contains text
///     tap-text:<text>    tap the first static text whose label contains text
///     back               tap the back button (or swipe back when there is none)
///     swipe-back         swipe from the left edge
///     scroll:up|down     swipe the screen
///     glide:up|down      drag the screen slowly, without a fling
///     type:<text>        type into the focused field
///     wait:<seconds>     pause
///     shot:<name>        screenshot, saved as NN-name.png
///     dump               the accessibility tree, saved as NN-dump.txt
///
/// The app launches (onboarding skipped) before the first step unless that step
/// is `launch` or `onboarding`. The Scan tab's live camera feed never lets the
/// app go idle, so nothing but `wait` and `shot` may follow `tab:Scan` until
/// the scan opens its results.
///
/// Next to the screenshots, `timeline.json` lists each step with its start and
/// end time (seconds since 1970, the clock `ios-render-check.sh` stamps the
/// video with) and where and when it touched the window (0–1), so clips can be
/// cut from the recording.
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

    /// The screens the README shows, with pauses long enough to read in a GIF.
    static let readmeTour = """
        onboarding | wait:1 | shot:onboarding | tap:Got it | wait:1.5 | shot:home \
        | glide:down | wait:0.8 | glide:down | wait:0.8 | glide:down | wait:1 | scroll:up | wait:1.5 \
        | tap:Waste Saved | wait:1 | shot:waste-saved | glide:down | wait:1 | swipe-back | wait:1 \
        | tap:CO | wait:1 | shot:co2-saved | back | wait:1 \
        | tap:Recycling Map | wait:1 | shot:recycling-map \
        | tap:Plastic | wait:1.5 | tap:Paper | wait:1.5 | tap:Glass | wait:1.5 | tap:All | wait:1.5 | back | wait:1 \
        | tap:Recycle Leaderboard | wait:0.5 | shot:leaderboard | glide:down | wait:1 | swipe-back | wait:1 \
        | tap:Welcome back | wait:0.5 | shot:more | back | wait:1 \
        | tab:Gallery | wait:0.5 | shot:gallery | tap:Like | wait:1.2 \
        | glide:down | wait:0.8 | glide:down | wait:1 | scroll:up | wait:1.5 \
        | tap-text:I just recycled | wait:0.5 | shot:post | back | wait:1 \
        | tap:Share what you made | wait:0.8 | type:Turned old jam jars into herb planters | wait:0.5 \
        | shot:new-post | tap:Cancel | wait:1 \
        | tab:Scan | wait:7 | shot:scan-results | glide:down | wait:1 | glide:down | wait:0.5 \
        | shot:scan-guidance | tap:Add to Gallery | wait:1 | shot:scan-shared
        """

    private var outputDirectory: URL?
    private var shotCount = 0
    private var timeline: [[String: Any]] = []
    /// What the current step adds to its timeline entry (touch, file).
    private var stepDetails: [String: Any] = [:]

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
        let script = (ProcessInfo.processInfo.environment["RENDER_STEPS"] ?? "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        let tour = script.isEmpty ? Self.fullTour : script == "readme" ? Self.readmeTour : script
        let steps = tour
            .split(separator: "|")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }

        let app = XCUIApplication()
        // What was on screen when a step failed.
        addTeardownBlock { @MainActor [weak self] in
            // (hasSucceeded is still false here even when every step passed)
            guard let self, (self.testRun?.totalFailureCount ?? 0) > 0 else { return }
            try? self.dump(app, as: "failure-dump")
        }
        if let first = steps.first, first != "launch", first != "onboarding" {
            launch(app, showingOnboarding: false)
        }
        for step in steps {
            let start = Date().timeIntervalSince1970
            stepDetails = [:]
            try record(step, start: start, done: false)
            try perform(step, in: app)
            try record(step, start: start, done: true)
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
            noteTouch(on: tab, in: app)
            tab.tap()
        case "tap":
            let button = app.buttons.containing(NSPredicate(format: "label CONTAINS %@", argument)).firstMatch
            XCTAssertTrue(button.waitForExistence(timeout: 5), "No button labeled \(argument)")
            noteTouch(on: button, in: app)
            button.tap()
        case "tap-text":
            let text = app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", argument)).firstMatch
            XCTAssertTrue(text.waitForExistence(timeout: 5), "No text containing \(argument)")
            noteTouch(on: text, in: app)
            text.tap()
        case "back":
            // The navigation bar's button, or the system back button wherever
            // it is. Some pushed screens on iOS 27 had neither after earlier
            // navigation; the edge swipe still goes back there.
            if let back = firstExisting([app.navigationBars.buttons.firstMatch, app.buttons["BackButton"],
                                         app.buttons["Back"]], timeout: 5) {
                noteTouch(on: back, in: app)
                back.tap()
            } else {
                print("RenderCheck: no back button, swiping back instead")
                swipeBack(in: app)
            }
        case "swipe-back":
            swipeBack(in: app)
        case "scroll":
            switch argument {
            case "up": app.swipeDown()
            case "down": app.swipeUp()
            default: XCTFail("scroll takes up or down, not \(argument)")
            }
        case "glide":
            // Holding still before lifting the finger leaves no fling, so the
            // page stops where the drag ends.
            let from: CGFloat, to: CGFloat
            switch argument {
            case "down": from = 0.74; to = 0.34
            case "up": from = 0.34; to = 0.74
            default:
                XCTFail("glide takes up or down, not \(argument)")
                return
            }
            drag(in: app, from: CGVector(dx: 0.5, dy: from), to: CGVector(dx: 0.5, dy: to),
                 velocity: 500, hold: 0.25)
        case "type":
            // Into the focused field, or else the first one, tapped to focus it.
            let focused = app.descendants(matching: .any)
                .matching(NSPredicate(format: "hasKeyboardFocus == true")).firstMatch
            if !focused.waitForExistence(timeout: 2),
               let field = firstExisting([app.textViews.firstMatch, app.textFields.firstMatch], timeout: 2) {
                field.tap()
            }
            app.typeText(argument)
        case "wait":
            let seconds = try XCTUnwrap(Double(argument), "wait takes a number of seconds, not \(argument)")
            Thread.sleep(forTimeInterval: seconds)
        case "shot":
            try capture(argument.isEmpty ? "screen" : argument)
        case "dump":
            shotCount += 1
            try dump(app, as: String(format: "%02d-dump", shotCount))
        default:
            XCTFail("Unknown render step: \(step)")
        }
    }

    @MainActor
    private func launch(_ app: XCUIApplication, showingOnboarding: Bool) {
        if app.state != .notRunning { app.terminate() }
        // A fresh simulator takes its region from the host (CI runners are
        // en_US), so pin it for screenshots that compare across machines.
        // `-hasSeenOnboarding NO` would override what "Got it!" saves, so
        // onboarding could never close; the app resets the flag for
        // -AWAREShowOnboarding instead. It goes last, as it takes no value.
        app.launchArguments = ["-AppleLanguages", "(en-VN)", "-AppleLocale", "en_VN"]
            + (showingOnboarding ? ["-AWAREShowOnboarding"] : ["-hasSeenOnboarding", "YES"])
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
        stepDetails["file"] = "\(fileName).png"
        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = fileName
        attachment.lifetime = .keepAlways
        add(attachment)
        if let outputDirectory {
            try screenshot.pngRepresentation.write(to: outputDirectory.appendingPathComponent("\(fileName).png"))
        }
    }

    /// Saves the app's accessibility tree, the elements the steps can find.
    @MainActor
    private func dump(_ app: XCUIApplication, as name: String) throws {
        guard let outputDirectory else { return }
        try app.debugDescription.write(to: outputDirectory.appendingPathComponent("\(name).txt"),
                                       atomically: true, encoding: .utf8)
    }

    /// The first of the elements to exist within `timeout` seconds.
    @MainActor
    private func firstExisting(_ elements: [XCUIElement], timeout: TimeInterval) -> XCUIElement? {
        let deadline = Date().addingTimeInterval(timeout)
        repeat {
            if let element = elements.first(where: { $0.exists }) { return element }
            Thread.sleep(forTimeInterval: 0.25)
        } while Date() < deadline
        return nil
    }

    @MainActor
    private func swipeBack(in app: XCUIApplication) {
        drag(in: app, from: CGVector(dx: 0.01, dy: 0.55), to: CGVector(dx: 0.85, dy: 0.55),
             velocity: 300, hold: 0.1)
    }

    /// Presses for 0.05 s, drags at `velocity` points per second and holds for
    /// `hold` seconds before lifting, noting the drag for the timeline.
    @MainActor
    private func drag(in app: XCUIApplication, from: CGVector, to: CGVector, velocity: Double, hold: TimeInterval) {
        let window = app.windows.firstMatch
        stepDetails["touch"] = ["x": Double(from.dx), "y": Double(from.dy), "toX": Double(to.dx), "toY": Double(to.dy),
                                "velocity": velocity, "hold": hold, "time": Date().timeIntervalSince1970]
        window.coordinate(withNormalizedOffset: from)
            .press(forDuration: 0.05, thenDragTo: window.coordinate(withNormalizedOffset: to),
                   withVelocity: XCUIGestureVelocity(rawValue: CGFloat(velocity)), thenHoldForDuration: hold)
    }

    /// Remembers where a tap lands, relative to the window, and when it was sent.
    @MainActor
    private func noteTouch(on element: XCUIElement, in app: XCUIApplication) {
        let frame = element.frame
        let bounds = app.windows.firstMatch.frame
        guard bounds.width > 0, bounds.height > 0 else { return }
        stepDetails["touch"] = ["x": Double((frame.midX - bounds.minX) / bounds.width),
                                "y": Double((frame.midY - bounds.minY) / bounds.height),
                                "time": Date().timeIntervalSince1970]
    }

    /// Writes the step to `timeline.json` before it runs, without an end time,
    /// so a failed run shows where it stopped, and again once it's done.
    @MainActor
    private func record(_ step: String, start: TimeInterval, done: Bool) throws {
        var entry = stepDetails
        entry["step"] = step
        entry["start"] = start
        if done {
            entry["end"] = Date().timeIntervalSince1970
            timeline.removeLast()
        }
        timeline.append(entry)
        guard let outputDirectory else { return }
        let data = try JSONSerialization.data(withJSONObject: timeline, options: [.prettyPrinted, .sortedKeys])
        try data.write(to: outputDirectory.appendingPathComponent("timeline.json"))
    }
}
