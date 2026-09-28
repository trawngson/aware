#if targetEnvironment(simulator)

import AVFoundation
import CoreImage
import UIKit
import YOLO

/// Replaces the unavailable simulator camera with a looping bundled video while
/// still running every sampled frame through the same YOLO model.
final class SimulatorVideoYOLOView: UIView {
    var onDetection: ((YOLOResult) -> Void)?
    var onFrameCapture: ((UIImage) -> Void)?

    private let player = AVPlayer()
    private let playerLayer = AVPlayerLayer()
    private let videoOutput = AVPlayerItemVideoOutput(
        pixelBufferAttributes: [
            kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA
        ]
    )
    private let inferenceQueue = DispatchQueue(
        label: "net.nctson.awareapp.simulator-video-inference",
        qos: .userInitiated
    )
    private let imageContext = CIContext()

    private var detector: YOLO?
    private var displayLink: CADisplayLink?
    private var playbackEndObserver: NSObjectProtocol?
    private var confidenceThreshold: Double
    private var isModelReady = false
    private var isInferring = false
    private var isActive = true
    /// Rotation stored in the video track. Inference still runs on the raw
    /// frame (as before), but boxes and captured photos are turned upright so
    /// they match what the player shows.
    private var frameOrientation: CGImagePropertyOrientation = .up

    init(
        frame: CGRect,
        modelPathOrName: String,
        task: YOLOTask,
        confidenceThreshold: Float,
        videoURL: URL?
    ) {
        self.confidenceThreshold = Double(confidenceThreshold)
        super.init(frame: frame)

        backgroundColor = .black
        configurePlayer(with: videoURL)
        loadModel(modelPathOrName: modelPathOrName, task: task)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    deinit {
        tearDown()
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        playerLayer.frame = bounds
    }

    func setActive(_ active: Bool) {
        guard isActive != active else { return }
        isActive = active
        displayLink?.isPaused = !active

        if active {
            player.play()
        } else {
            player.pause()
        }
    }

    func setConfidenceThreshold(_ threshold: Float) {
        let newThreshold = Double(threshold)
        guard confidenceThreshold != newThreshold else { return }
        confidenceThreshold = newThreshold
        detector?.setConfidenceThreshold(confidenceThreshold)
    }

    func tearDown() {
        isActive = false
        player.pause()
        player.replaceCurrentItem(with: nil)
        displayLink?.invalidate()
        displayLink = nil

        if let playbackEndObserver {
            NotificationCenter.default.removeObserver(playbackEndObserver)
            self.playbackEndObserver = nil
        }

        onDetection = nil
        onFrameCapture = nil
    }

    private func configurePlayer(with videoURL: URL?) {
        guard let videoURL else {
            showMissingVideoMessage()
            return
        }

        let item = AVPlayerItem(url: videoURL)
        item.add(videoOutput)
        loadFrameOrientation(of: item.asset)

        player.replaceCurrentItem(with: item)
        player.actionAtItemEnd = .none
        player.isMuted = true

        playerLayer.player = player
        playerLayer.videoGravity = .resizeAspectFill
        layer.addSublayer(playerLayer)

        playbackEndObserver = NotificationCenter.default.addObserver(
            forName: .AVPlayerItemDidPlayToEndTime,
            object: item,
            queue: .main
        ) { [weak self] _ in
            self?.restartVideo()
        }

        let displayLink = CADisplayLink(target: self, selector: #selector(processCurrentFrame))
        displayLink.add(to: .main, forMode: .common)
        self.displayLink = displayLink

        player.play()
    }

    private func loadFrameOrientation(of asset: AVAsset) {
        Task { [weak self] in
            guard
                let track = try? await asset.loadTracks(withMediaType: .video).first,
                let transform = try? await track.load(.preferredTransform)
            else { return }
            let orientation: CGImagePropertyOrientation
            switch (transform.a, transform.b, transform.c, transform.d) {
            case (0, 1, -1, 0): orientation = .right
            case (0, -1, 1, 0): orientation = .left
            case (-1, 0, 0, -1): orientation = .down
            default: orientation = .up
            }
            await MainActor.run { self?.frameOrientation = orientation }
        }
    }

    private func loadModel(modelPathOrName: String, task: YOLOTask) {
        detector = YOLO(modelPathOrName, task: task) { [weak self] result in
            DispatchQueue.main.async {
                guard let self else { return }

                switch result {
                case .success(let detector):
                    detector.setConfidenceThreshold(self.confidenceThreshold)
                    self.detector = detector
                    self.isModelReady = true
                case .failure(let error):
                    print("Simulator demo model failed to load: \(error)")
                }
            }
        }
        detector?.setConfidenceThreshold(confidenceThreshold)
    }

    private func restartVideo() {
        player.seek(to: .zero, toleranceBefore: .zero, toleranceAfter: .zero) { [weak self] _ in
            DispatchQueue.main.async {
                guard let self, self.isActive else { return }
                self.player.play()
            }
        }
    }

    @objc private func processCurrentFrame() {
        guard
            isActive,
            isModelReady,
            !isInferring,
            let detector
        else {
            return
        }

        let itemTime = videoOutput.itemTime(forHostTime: CACurrentMediaTime())
        guard
            videoOutput.hasNewPixelBuffer(forItemTime: itemTime),
            let pixelBuffer = videoOutput.copyPixelBuffer(
                forItemTime: itemTime,
                itemTimeForDisplay: nil
            )
        else {
            return
        }

        isInferring = true
        let frame = CIImage(cvPixelBuffer: pixelBuffer)
        let orientation = frameOrientation

        inferenceQueue.async { [weak self] in
            guard let self else { return }

            let rawResult = detector(frame)
            let result = Self.rotate(rawResult, to: orientation)
            let upright = frame.oriented(orientation)
            let renderedFrame = self.imageContext.createCGImage(upright, from: upright.extent)

            DispatchQueue.main.async {
                self.isInferring = false
                guard self.isActive else { return }

                if let renderedFrame {
                    self.onFrameCapture?(UIImage(cgImage: renderedFrame))
                }
                self.onDetection?(result)
            }
        }
    }

    /// Maps normalized, top-left-origin boxes from the raw frame into the
    /// upright frame the player displays.
    private static func rotate(_ result: YOLOResult, to orientation: CGImagePropertyOrientation) -> YOLOResult {
        guard orientation != .up else { return result }
        let size = orientation == .down
            ? result.orig_shape
            : CGSize(width: result.orig_shape.height, height: result.orig_shape.width)
        let boxes = result.boxes.map { box -> Box in
            let r = box.xywhn
            let n: CGRect
            switch orientation {
            case .right: n = CGRect(x: 1 - r.maxY, y: r.minX, width: r.height, height: r.width)
            case .left: n = CGRect(x: r.minY, y: 1 - r.maxX, width: r.height, height: r.width)
            case .down: n = CGRect(x: 1 - r.maxX, y: 1 - r.maxY, width: r.width, height: r.height)
            default: n = r
            }
            let pixels = CGRect(x: n.minX * size.width, y: n.minY * size.height,
                                width: n.width * size.width, height: n.height * size.height)
            return Box(index: box.index, cls: box.cls, conf: box.conf, xywh: pixels, xywhn: n)
        }
        return YOLOResult(orig_shape: size, boxes: boxes, speed: result.speed, fps: result.fps, names: result.names)
    }

    private func showMissingVideoMessage() {
        let label = UILabel()
        label.translatesAutoresizingMaskIntoConstraints = false
        label.text = "Simulator demo video is missing."
        label.textColor = .white
        label.textAlignment = .center
        label.numberOfLines = 0
        addSubview(label)

        NSLayoutConstraint.activate([
            label.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 24),
            label.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -24),
            label.centerYAnchor.constraint(equalTo: centerYAnchor)
        ])
    }
}

#endif
