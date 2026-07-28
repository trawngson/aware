//
//  awareappUITests.swift
//  awareappUITests
//
//  Created by Nguyen Truong Son on 16/2/26.
//

import XCTest

final class awareappUITests: XCTestCase {

    override func setUpWithError() throws {
        // Put setup code here. This method is called before the invocation of each test method in the class.

        // In UI tests it is usually best to stop immediately when a failure occurs.
        continueAfterFailure = false

        // In UI tests it’s important to set the initial state - such as interface orientation - required for your tests before they run. The setUp method is a good place to do this.
    }

    override func tearDownWithError() throws {
        // Put teardown code here. This method is called after the invocation of each test method in the class.
    }

    @MainActor
    func testOpeningScanKeepsAppRunning() throws {
        let app = XCUIApplication()
        app.launch()

        let onboardingButton = app.buttons["Got it!"]
        if onboardingButton.waitForExistence(timeout: 2) {
            onboardingButton.tap()
        }

        app.tabBars.buttons["Scan"].tap()

        XCTAssertTrue(
            app.staticTexts["Detected Items"].waitForExistence(timeout: 5),
            "The Scan tab should remain visible after its camera session starts."
        )
    }

    @MainActor
    func testLaunchPerformance() throws {
        // This measures how long it takes to launch your application.
        measure(metrics: [XCTApplicationLaunchMetric()]) {
            XCUIApplication().launch()
        }
    }
}
