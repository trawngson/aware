import AVFoundation
import CryptoKit
import Darwin
import QuartzCore
import SwiftUI
import UIKit

// MARK: - Settings

/// Fixed run settings for the device benchmark (backend/records/device-benchmark-protocol-v1.yaml).
/// The analysis (warm-up, windows, limits) is done on the Mac, not here.
enum DeviceBenchmarkSettings {
    static let launchArgument = "-AWAREDeviceBenchmark"
    static let benchmarkID = "aware-device-benchmark-v1"
    static let modelResource = "aware"
    /// 10 s warm-up (model load) plus ten measured minutes.
    static let durationSeconds: Double = 610
    static let sampleIntervalSeconds: Double = 1
    static let screenBrightness: CGFloat = 0.5
    static let brightnessSettleSeconds: Double = 1.5
    static let minimumStartBattery: Float = 0.5
    /// Same camera settings as the Scan tab.
    static let confidenceThreshold: Double = 0.4
    static let sessionPreset = "photo"
    static let cameraPosition = "back"
    /// A run that produces no frame this long after starting is stopped.
    static let noFrameTimeoutSeconds: Double = 20

    static var isRequested: Bool {
        ProcessInfo.processInfo.arguments.contains(launchArgument)
    }
}

// MARK: - Record

struct DeviceBenchmarkRecord: Encodable {
    struct Device: Encodable {
        let machine: String
        let systemName: String
        let systemVersion: String
    }

    struct AppInfo: Encodable {
        let version: String
        let build: String
        let configuration: String
    }

    struct Model: Encodable {
        let resource: String
        let weightSha256: String
        let compiledBytes: Int64
    }

    struct OperatorInput: Encodable {
        let batteryHealthPercent: Int
        let roomTemperatureC: Double?
        let notes: String
    }

    struct Settings: Encodable {
        let durationSeconds: Double
        let sampleIntervalSeconds: Double
        let screenBrightness: Double
        let confidenceThreshold: Double
        let sessionPreset: String
        let cameraPosition: String
    }

    /// Parallel arrays, one entry per processed camera frame.
    struct Frames: Encodable {
        let startSeconds: [Double]
        let durationMs: [Double]
    }

    struct Sample: Encodable {
        let t: Double
        let physFootprintBytes: UInt64?
        let thermalState: Int
        let batteryLevel: Double
        let batteryState: String
        let lowPowerMode: Bool
        let screenBrightness: Double
        let results: Int
        let resultsWithDetection: Int
    }

    struct Event: Encodable {
        let t: Double
        let kind: String
        let detail: String
    }

    let schemaVersion = "1.0"
    let benchmark = DeviceBenchmarkSettings.benchmarkID
    let runId: UUID
    let startedAt: Date
    let endedAt: Date
    /// completed | stopped | interrupted | failed
    let status: String
    let stopReason: String?
    let device: Device
    let app: AppInfo
    let model: Model
    let operatorInput: OperatorInput
    let settings: Settings
    let frames: Frames
    let samples: [Sample]
    let events: [Event]
}

// MARK: - Frame log

/// Written on the camera queue, read on the main thread.
final class DeviceBenchmarkFrameLog: @unchecked Sendable {
    private let lock = NSLock()
    private var origin: CFTimeInterval?
    private var starts: [Double] = []
    private var durations: [Double] = []

    func begin(at origin: CFTimeInterval) {
        lock.lock()
        defer { lock.unlock() }
        self.origin = origin
        starts = []
        durations = []
        starts.reserveCapacity(20_000)
        durations.reserveCapacity(20_000)
    }

    func end() {
        lock.lock()
        defer { lock.unlock() }
        origin = nil
    }

    func append(start: CFTimeInterval, duration: CFTimeInterval) {
        lock.lock()
        defer { lock.unlock() }
        guard let origin, start >= origin else { return }
        starts.append(start - origin)
        durations.append(duration * 1000)
    }

    var count: Int {
        lock.lock()
        defer { lock.unlock() }
        return starts.count
    }

    /// Frames that started at or after `since` seconds into the run.
    func recent(since: Double) -> [Double] {
        lock.lock()
        defer { lock.unlock() }
        guard let first = starts.firstIndex(where: { $0 >= since }) else { return [] }
        return Array(durations[first...])
    }

    func snapshot() -> DeviceBenchmarkRecord.Frames {
        lock.lock()
        defer { lock.unlock() }
        return DeviceBenchmarkRecord.Frames(
            startSeconds: starts.map { ($0 * 1_000_000).rounded() / 1_000_000 },
            durationMs: durations.map { ($0 * 1000).rounded() / 1000 }
        )
    }
}

// MARK: - Device readings

enum DeviceBenchmarkProbe {
    static var machine: String {
        var info = utsname()
        uname(&info)
        return withUnsafeBytes(of: &info.machine) { bytes in
            String(decoding: bytes.prefix { $0 != 0 }, as: UTF8.self)
        }
    }

    static var isSimulator: Bool {
        #if targetEnvironment(simulator)
        true
        #else
        false
        #endif
    }

    static var buildConfiguration: String {
        #if DEBUG
        "Debug"
        #else
        "Release"
        #endif
    }

    /// The same number Xcode's memory gauge and the system memory limit use.
    static func physFootprintBytes() -> UInt64? {
        var info = task_vm_info_data_t()
        var count = mach_msg_type_number_t(MemoryLayout<task_vm_info_data_t>.size / MemoryLayout<natural_t>.size)
        let status = withUnsafeMutablePointer(to: &info) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
                task_info(mach_task_self_, task_flavor_t(TASK_VM_INFO), $0, &count)
            }
        }
        return status == KERN_SUCCESS ? info.phys_footprint : nil
    }

    static func batteryStateName(_ state: UIDevice.BatteryState) -> String {
        switch state {
        case .unplugged: "unplugged"
        case .charging: "charging"
        case .full: "full"
        case .unknown: "unknown"
        @unknown default: "unknown"
        }
    }

    static func thermalStateName(_ state: ProcessInfo.ThermalState) -> String {
        switch state {
        case .nominal: "nominal"
        case .fair: "fair"
        case .serious: "serious"
        case .critical: "critical"
        @unknown default: "unknown"
        }
    }

    /// SHA-256 of the compiled weights, which Xcode copies unchanged from the
    /// .mlpackage, so it matches the package's weights/weight.bin.
    static func modelIdentity() throws -> DeviceBenchmarkRecord.Model {
        guard let modelURL = Bundle.main.url(
            forResource: DeviceBenchmarkSettings.modelResource, withExtension: "mlmodelc"
        ) else {
            throw CocoaError(.fileNoSuchFile)
        }
        let handle = try FileHandle(forReadingFrom: modelURL.appending(path: "weights/weight.bin"))
        defer { try? handle.close() }
        var hasher = SHA256()
        while let chunk = try handle.read(upToCount: 1 << 20), !chunk.isEmpty {
            hasher.update(data: chunk)
        }
        let digest = hasher.finalize().map { String(format: "%02x", $0) }.joined()

        var bytes: Int64 = 0
        let files = FileManager.default.enumerator(at: modelURL, includingPropertiesForKeys: [.fileSizeKey])
        while let file = files?.nextObject() as? URL {
            bytes += Int64((try? file.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0)
        }
        return DeviceBenchmarkRecord.Model(
            resource: DeviceBenchmarkSettings.modelResource, weightSha256: digest, compiledBytes: bytes
        )
    }
}

// MARK: - Recorder

@MainActor
final class DeviceBenchmarkRecorder: ObservableObject {
    enum Phase: Equatable {
        case setup
        case running
        case finished(URL, status: String)
        case failed(String)
    }

    struct Check: Identifiable {
        let id: String
        let passed: Bool
        let detail: String
    }

    struct LiveStats {
        var elapsed: Double = 0
        var frames = 0
        var recentFPS: Double = 0
        var recentMedianMs: Double = 0
        var memoryMB: Double = 0
        var thermal = "nominal"
        var batteryPercent = 0
        var detectionPercent: Double = 0
    }

    @Published private(set) var phase: Phase = .setup
    @Published private(set) var live = LiveStats()
    @Published private(set) var isStarting = false
    @Published private(set) var model: DeviceBenchmarkRecord.Model?
    @Published private(set) var modelError: String?
    @Published var batteryHealthText = ""
    @Published var roomTemperatureText = ""
    @Published var notes = ""

    let frameLog = DeviceBenchmarkFrameLog()

    private var runID = UUID()
    private var startedAt = Date()
    private var origin: CFTimeInterval = 0
    private var samples: [DeviceBenchmarkRecord.Sample] = []
    private var events: [DeviceBenchmarkRecord.Event] = []
    private var results = 0
    private var resultsWithDetection = 0
    private var ticker: Timer?
    private var observers: [NSObjectProtocol] = []

    init() {
        UIDevice.current.isBatteryMonitoringEnabled = true
        do {
            model = try DeviceBenchmarkProbe.modelIdentity()
        } catch {
            modelError = error.localizedDescription
        }
    }

    // MARK: Preconditions

    var batteryHealth: Int? {
        Int(batteryHealthText.trimmingCharacters(in: .whitespaces)).flatMap { (1...100).contains($0) ? $0 : nil }
    }

    var roomTemperature: Double? {
        Double(roomTemperatureText.trimmingCharacters(in: .whitespaces).replacingOccurrences(of: ",", with: "."))
    }

    /// Every check must pass before a run can start (fail closed).
    func checks() -> [Check] {
        let device = UIDevice.current
        let battery = device.batteryLevel
        let thermal = ProcessInfo.processInfo.thermalState
        let camera = AVCaptureDevice.authorizationStatus(for: .video)
        return [
            Check(id: "Physical device", passed: !DeviceBenchmarkProbe.isSimulator,
                  detail: DeviceBenchmarkProbe.machine),
            Check(id: "Release build", passed: DeviceBenchmarkProbe.buildConfiguration == "Release",
                  detail: "Use the \"awareapp Benchmark\" scheme"),
            Check(id: "Model identified", passed: model != nil,
                  detail: model.map { String($0.weightSha256.prefix(12)) } ?? (modelError ?? "missing")),
            Check(id: "Camera allowed", passed: camera == .authorized,
                  detail: camera == .notDetermined ? "Tap Start once to allow" : "Settings > awareapp > Camera"),
            Check(id: "Unplugged", passed: device.batteryState == .unplugged,
                  detail: DeviceBenchmarkProbe.batteryStateName(device.batteryState)),
            Check(id: "Battery at least 50%", passed: battery >= DeviceBenchmarkSettings.minimumStartBattery,
                  detail: battery < 0 ? "unknown" : "\(Int((battery * 100).rounded()))%"),
            Check(id: "Low Power Mode off", passed: !ProcessInfo.processInfo.isLowPowerModeEnabled,
                  detail: ProcessInfo.processInfo.isLowPowerModeEnabled ? "on" : "off"),
            Check(id: "Phone is cool", passed: thermal == .nominal,
                  detail: DeviceBenchmarkProbe.thermalStateName(thermal)),
            Check(id: "Battery health entered", passed: batteryHealth != nil,
                  detail: batteryHealth.map { "\($0)%" } ?? "Settings > Battery > Battery Health"),
        ]
    }

    func requestCameraIfNeeded() {
        guard AVCaptureDevice.authorizationStatus(for: .video) == .notDetermined else { return }
        AVCaptureDevice.requestAccess(for: .video) { _ in
            Task { @MainActor in self.objectWillChange.send() }
        }
    }

    // MARK: Run

    /// Holds the screen at the benchmark brightness for the whole session.
    func holdScreenBrightness() {
        currentScreen?.brightness = DeviceBenchmarkSettings.screenBrightness
    }

    /// Sets the brightness, then starts the run once iOS has applied it, so the
    /// first sample doesn't read the previous brightness.
    func start() {
        guard phase == .setup, !isStarting, checks().allSatisfy(\.passed) else { return }
        isStarting = true
        holdScreenBrightness()
        DispatchQueue.main.asyncAfter(deadline: .now() + DeviceBenchmarkSettings.brightnessSettleSeconds) {
            self.isStarting = false
            guard self.phase == .setup, self.checks().allSatisfy(\.passed) else { return }
            self.beginRun()
        }
    }

    private func beginRun() {
        runID = UUID()
        startedAt = Date()
        origin = CACurrentMediaTime()
        samples = []
        events = []
        results = 0
        resultsWithDetection = 0
        frameLog.begin(at: origin)
        observe()
        phase = .running
        sample()
        ticker = Timer.scheduledTimer(withTimeInterval: DeviceBenchmarkSettings.sampleIntervalSeconds, repeats: true) { _ in
            Task { @MainActor in self.tick() }
        }
    }

    /// Called from the camera's result callback (main thread).
    func record(detectionCount: Int) {
        guard phase == .running else { return }
        results += 1
        if detectionCount > 0 { resultsWithDetection += 1 }
    }

    func stop(reason: String) {
        finish(status: "stopped", reason: reason)
    }

    private var elapsed: Double { CACurrentMediaTime() - origin }

    private var currentScreen: UIScreen? {
        UIApplication.shared.connectedScenes.compactMap { ($0 as? UIWindowScene)?.screen }.first
    }

    private func tick() {
        guard phase == .running else { return }
        sample()
        if elapsed >= DeviceBenchmarkSettings.durationSeconds {
            finish(status: "completed", reason: nil)
        } else if elapsed >= DeviceBenchmarkSettings.noFrameTimeoutSeconds && frameLog.count == 0 {
            finish(status: "failed", reason: "no_frames")
        }
    }

    private func sample() {
        let device = UIDevice.current
        let thermal = ProcessInfo.processInfo.thermalState
        let footprint = DeviceBenchmarkProbe.physFootprintBytes()
        let t = elapsed
        samples.append(DeviceBenchmarkRecord.Sample(
            t: (t * 1000).rounded() / 1000,
            physFootprintBytes: footprint,
            thermalState: thermal.rawValue,
            batteryLevel: Double(device.batteryLevel),
            batteryState: DeviceBenchmarkProbe.batteryStateName(device.batteryState),
            lowPowerMode: ProcessInfo.processInfo.isLowPowerModeEnabled,
            screenBrightness: Double(currentScreen?.brightness ?? -1),
            results: results,
            resultsWithDetection: resultsWithDetection
        ))

        let recent = frameLog.recent(since: t - 10).sorted()
        live = LiveStats(
            elapsed: t,
            frames: frameLog.count,
            recentFPS: Double(recent.count) / min(10, max(t, 1)),
            recentMedianMs: recent.isEmpty ? 0 : recent[recent.count / 2],
            memoryMB: Double(footprint ?? 0) / 1_048_576,
            thermal: DeviceBenchmarkProbe.thermalStateName(thermal),
            batteryPercent: Int((device.batteryLevel * 100).rounded()),
            detectionPercent: results > 0 ? Double(resultsWithDetection) / Double(results) * 100 : 0
        )
    }

    private func observe() {
        let center = NotificationCenter.default
        let watched: [(Notification.Name, String)] = [
            (ProcessInfo.thermalStateDidChangeNotification, "thermal_state"),
            (UIApplication.didReceiveMemoryWarningNotification, "memory_warning"),
            (UIApplication.willResignActiveNotification, "resign_active"),
            (UIApplication.didBecomeActiveNotification, "become_active"),
            (UIDevice.batteryStateDidChangeNotification, "battery_state"),
            (Notification.Name.NSProcessInfoPowerStateDidChange, "low_power_mode"),
        ]
        observers = watched.map { name, kind in
            center.addObserver(forName: name, object: nil, queue: .main) { _ in
                Task { @MainActor in self.log(kind) }
            }
        }
        observers.append(center.addObserver(
            forName: UIApplication.didEnterBackgroundNotification, object: nil, queue: .main
        ) { _ in
            Task { @MainActor in self.finish(status: "interrupted", reason: "entered_background") }
        })
    }

    private func log(_ kind: String) {
        guard phase == .running else { return }
        let detail: String
        switch kind {
        case "thermal_state": detail = DeviceBenchmarkProbe.thermalStateName(ProcessInfo.processInfo.thermalState)
        case "battery_state": detail = DeviceBenchmarkProbe.batteryStateName(UIDevice.current.batteryState)
        case "low_power_mode": detail = ProcessInfo.processInfo.isLowPowerModeEnabled ? "on" : "off"
        default: detail = ""
        }
        events.append(DeviceBenchmarkRecord.Event(t: (elapsed * 1000).rounded() / 1000, kind: kind, detail: detail))
    }

    private func finish(status: String, reason: String?) {
        guard phase == .running else { return }
        sample()
        frameLog.end()
        ticker?.invalidate()
        ticker = nil
        observers.forEach { NotificationCenter.default.removeObserver($0) }
        observers = []

        guard let model, let batteryHealth else {
            phase = .failed("Model identity or battery health missing")
            return
        }
        let info = Bundle.main.infoDictionary ?? [:]
        let record = DeviceBenchmarkRecord(
            runId: runID,
            startedAt: startedAt,
            endedAt: Date(),
            status: status,
            stopReason: reason,
            device: .init(
                machine: DeviceBenchmarkProbe.machine,
                systemName: UIDevice.current.systemName,
                systemVersion: UIDevice.current.systemVersion
            ),
            app: .init(
                version: info["CFBundleShortVersionString"] as? String ?? "",
                build: info["CFBundleVersion"] as? String ?? "",
                configuration: DeviceBenchmarkProbe.buildConfiguration
            ),
            model: model,
            operatorInput: .init(batteryHealthPercent: batteryHealth, roomTemperatureC: roomTemperature, notes: notes),
            settings: .init(
                durationSeconds: DeviceBenchmarkSettings.durationSeconds,
                sampleIntervalSeconds: DeviceBenchmarkSettings.sampleIntervalSeconds,
                screenBrightness: Double(DeviceBenchmarkSettings.screenBrightness),
                confidenceThreshold: DeviceBenchmarkSettings.confidenceThreshold,
                sessionPreset: DeviceBenchmarkSettings.sessionPreset,
                cameraPosition: DeviceBenchmarkSettings.cameraPosition
            ),
            frames: frameLog.snapshot(),
            samples: samples,
            events: events
        )
        do {
            phase = .finished(try save(record), status: status)
        } catch {
            phase = .failed("Could not save the run: \(error.localizedDescription)")
        }
    }

    private func save(_ record: DeviceBenchmarkRecord) throws -> URL {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.sortedKeys]
        let folder = URL.documentsDirectory.appending(path: "benchmarks", directoryHint: .isDirectory)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let stamp = ISO8601DateFormatter().string(from: record.startedAt).replacingOccurrences(of: ":", with: "")
        let name = "aware-bench-\(record.model.weightSha256.prefix(8))-\(stamp)-\(record.status).json"
        let url = folder.appending(path: name)
        try encoder.encode(record).write(to: url, options: .withoutOverwriting)
        return url
    }
}
