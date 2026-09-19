import SwiftUI

/// Developer-only screen for the iPhone XR device benchmark. It is shown only
/// when the app is launched with `-AWAREDeviceBenchmark` (the "awareapp
/// Benchmark" scheme) and runs the same camera component as the Scan tab.
struct DeviceBenchmarkView: View {
    @StateObject private var recorder = DeviceBenchmarkRecorder()
    @Environment(\.scenePhase) private var scenePhase
    @State private var refresh = 0

    var body: some View {
        NavigationStack {
            Group {
                switch recorder.phase {
                case .setup:
                    setupView
                case .running:
                    runningView
                case .finished(let url, let status):
                    finishedView(url: url, status: status)
                case .failed(let message):
                    messageView(title: "Run failed", message: message, color: .red)
                }
            }
            .navigationTitle(Text(verbatim: "Device benchmark"))
            .navigationBarTitleDisplayMode(.inline)
        }
        // Auto-lock stays off for the whole benchmark session, so the phone
        // can't lock during the unplugged wait, the run, or the AirDrop.
        .onAppear {
            UIApplication.shared.isIdleTimerDisabled = true
            recorder.holdScreenBrightness()
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { refresh += 1 }
        }
    }

    // MARK: Setup

    private var setupView: some View {
        let checks = recorder.checks()
        let ready = checks.allSatisfy(\.passed)
        return Form {
            Section {
                if let model = recorder.model {
                    LabeledContent { Text(verbatim: String(model.weightSha256.prefix(16))).monospaced() } label: {
                        Text(verbatim: "Model weights")
                    }
                    LabeledContent {
                        Text(verbatim: String(format: "%.1f MB", Double(model.compiledBytes) / 1_048_576))
                    } label: {
                        Text(verbatim: "Compiled size")
                    }
                } else {
                    Text(verbatim: recorder.modelError ?? "Model not found").foregroundStyle(.red)
                }
            } header: {
                Text(verbatim: "Model")
            }

            Section {
                TextField(text: $recorder.batteryHealthText) { Text(verbatim: "Battery health % (required)") }
                    .keyboardType(.numberPad)
                TextField(text: $recorder.roomTemperatureText) { Text(verbatim: "Room temperature °C (optional)") }
                    .keyboardType(.decimalPad)
                TextField(text: $recorder.notes) { Text(verbatim: "Notes: run label, scene (optional)") }
            } header: {
                Text(verbatim: "Before you start")
            }

            Section {
                ForEach(checks) { check in
                    HStack {
                        Image(systemName: check.passed ? "checkmark.circle.fill" : "xmark.circle.fill")
                            .foregroundStyle(check.passed ? .green : .red)
                        Text(verbatim: check.id)
                        Spacer()
                        Text(verbatim: check.detail).font(.footnote).foregroundStyle(.secondary)
                    }
                }
                Button {
                    refresh += 1
                } label: {
                    Text(verbatim: "Check again")
                }
            } header: {
                Text(verbatim: "Checks")
            } footer: {
                Text(verbatim: "The run lasts 10 minutes 10 seconds (10 s warm-up, then 10 measured minutes). The screen stays on at 50% brightness while this app is open. Don't touch the phone or switch apps; leaving the app ends the run.")
            }

            Section {
                Button {
                    recorder.requestCameraIfNeeded()
                    recorder.start()
                } label: {
                    Text(verbatim: recorder.isStarting ? "Starting…" : "Start the run")
                        .frame(maxWidth: .infinity).bold()
                }
                .disabled(recorder.isStarting || (!ready && !needsCameraPrompt(checks)))
            }
        }
        .id(refresh)
    }

    private func needsCameraPrompt(_ checks: [DeviceBenchmarkRecorder.Check]) -> Bool {
        checks.filter { !$0.passed }.map(\.id) == ["Camera allowed"]
    }

    // MARK: Running

    private var runningView: some View {
        ZStack(alignment: .bottom) {
            CleanYOLOCamera(
                modelPathOrName: DeviceBenchmarkSettings.modelResource,
                task: .detect,
                cameraPosition: .back,
                confidenceThreshold: Float(DeviceBenchmarkSettings.confidenceThreshold),
                onDetection: { result in
                    let threshold = DeviceBenchmarkSettings.confidenceThreshold
                    recorder.record(detectionCount: result.boxes.filter { Double($0.conf) >= threshold }.count)
                },
                onRawInferenceTime: { [frameLog = recorder.frameLog] start, duration in
                    frameLog.append(start: start, duration: duration)
                }
            )
            .ignoresSafeArea()

            VStack(alignment: .leading, spacing: 6) {
                let live = recorder.live
                let remaining = max(0, DeviceBenchmarkSettings.durationSeconds - live.elapsed)
                Text(verbatim: String(format: "%d:%02d left", Int(remaining) / 60, Int(remaining) % 60))
                    .font(.title.monospacedDigit().bold())
                Text(verbatim: String(
                    format: "%d frames · %.1f FPS · %.1f ms median (last 10 s)",
                    live.frames, live.recentFPS, live.recentMedianMs
                ))
                Text(verbatim: String(
                    format: "%.0f MB · thermal %@ · battery %d%%",
                    live.memoryMB, live.thermal, live.batteryPercent
                ))
                Text(verbatim: String(format: "Items detected in %.0f%% of frames", live.detectionPercent))
                Button(role: .destructive) {
                    recorder.stop(reason: "operator_stopped")
                } label: {
                    Text(verbatim: "Stop early (the file is still saved)")
                }
                .padding(.top, 4)
            }
            .font(.footnote.monospacedDigit())
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.ultraThinMaterial)
        }
    }

    // MARK: Done

    private func finishedView(url: URL, status: String) -> some View {
        VStack(spacing: 16) {
            Image(systemName: status == "completed" ? "checkmark.seal.fill" : "exclamationmark.triangle.fill")
                .font(.system(size: 56))
                .foregroundStyle(status == "completed" ? .green : .orange)
            Text(verbatim: status == "completed" ? "Run completed" : "Run ended: \(status)")
                .font(.title2.bold())
            Text(verbatim: url.lastPathComponent)
                .font(.footnote.monospaced())
                .multilineTextAlignment(.center)
            ShareLink(item: url) {
                Label { Text(verbatim: "Send the file to your Mac (AirDrop)") } icon: {
                    Image(systemName: "square.and.arrow.up")
                }
                .bold()
            }
            .buttonStyle(.borderedProminent)
            Text(verbatim: "Keep every file, including stopped or failed runs.")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .padding()
    }

    private func messageView(title: String, message: String, color: Color) -> some View {
        VStack(spacing: 12) {
            Text(verbatim: title).font(.title2.bold()).foregroundStyle(color)
            Text(verbatim: message).multilineTextAlignment(.center)
        }
        .padding()
    }
}
