import Combine
import CoreLocation

/// The user's location, asked for only when they tap a control that needs it
/// ("While Using" permission). Everything works without it: the map then
/// measures from Hoan Kiem Lake, as before.
@MainActor
final class LocationProvider: NSObject, ObservableObject, CLLocationManagerDelegate {
    static let shared = LocationProvider()

    /// The last location found, if the user allowed it.
    @Published private(set) var location: CLLocationCoordinate2D?
    /// The user turned location off for AWARE (so asking again won't help).
    @Published private(set) var isDenied = false

    private let manager = CLLocationManager()
    private var waiting: [CheckedContinuation<CLLocationCoordinate2D?, Never>] = []

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
        isDenied = [.denied, .restricted].contains(manager.authorizationStatus)
    }

    /// Asks for permission the first time, then for one location. Returns nil
    /// when location is off or can't be found.
    func requestLocation() async -> CLLocationCoordinate2D? {
        switch manager.authorizationStatus {
        case .denied, .restricted:
            isDenied = true
            return nil
        default:
            break
        }
        return await withCheckedContinuation { continuation in
            waiting.append(continuation)
            if manager.authorizationStatus == .notDetermined {
                manager.requestWhenInUseAuthorization()
            } else {
                manager.requestLocation()
            }
        }
    }

    private func finish(with coordinate: CLLocationCoordinate2D?) {
        if let coordinate { location = coordinate }
        let continuations = waiting
        waiting = []
        continuations.forEach { $0.resume(returning: coordinate) }
    }

    // MARK: - CLLocationManagerDelegate

    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        Task { @MainActor in
            switch self.manager.authorizationStatus {
            case .authorizedWhenInUse, .authorizedAlways:
                self.isDenied = false
                if !self.waiting.isEmpty { self.manager.requestLocation() }
            case .denied, .restricted:
                self.isDenied = true
                self.finish(with: nil)
            default:
                break
            }
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let coordinate = locations.last?.coordinate else { return }
        Task { @MainActor in self.finish(with: coordinate) }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        Task { @MainActor in self.finish(with: nil) }
    }
}
