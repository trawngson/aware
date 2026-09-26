import CoreLocation
import MapKit

/// A shared recycling project pinned on the map. Each one links to its
/// Gallery post. Sample spots use an asset photo, real ones a stored photo.
struct MapSpot: Identifiable, Equatable {
    let postID: UUID
    let title: String
    let author: CommunityMember
    let imageName: String?
    var imageURL: URL? = nil
    let coordinate: CLLocationCoordinate2D
    let tag: MaterialTag?
    let age: String
    let points: Int

    var id: UUID { postID }

    static func == (lhs: MapSpot, rhs: MapSpot) -> Bool { lhs.postID == rhs.postID }
}

/// Several recycled items close together, drawn as one numbered bubble.
struct MapCluster: Identifiable {
    let id: Int
    let coordinate: CLLocationCoordinate2D
    let counts: [MaterialTag: Int]

    func count(for filter: MaterialTag?) -> Int {
        guard let filter else { return counts.values.reduce(0, +) }
        return counts[filter] ?? 0
    }
}

/// Demo data around Hoan Kiem Lake, Hanoi. Unless the user shares their
/// location (only possible with a backend), "you" are a fixed point by the
/// lake and all distances are measured from it.
enum RecyclingMapData {
    static let userLocation = CLLocationCoordinate2D(latitude: 21.0287, longitude: 105.8524)

    /// Radius used for "nearby" counts on Home and on the map.
    static let nearbyRadiusMeters: CLLocationDistance = 2_000

    static let region = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 21.0282, longitude: 105.8530),
        span: MKCoordinateSpan(latitudeDelta: 0.016, longitudeDelta: 0.012)
    )

    static let miniRegion = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 21.0290, longitude: 105.8531),
        span: MKCoordinateSpan(latitudeDelta: 0.009, longitudeDelta: 0.012)
    )

    static let spots: [MapSpot] = [
        MapSpot(postID: GalleryPost.SampleID.fabricLamp, title: "Fabric lamp", author: Community.dieuLinh,
                imageName: "RecycleProject1", coordinate: .init(latitude: 21.0318, longitude: 105.8505),
                tag: nil, age: "2d", points: 40),
        MapSpot(postID: GalleryPost.SampleID.eggCartonTurtle, title: "Egg carton turtle", author: Community.anthony,
                imageName: "RecycleProject2", coordinate: .init(latitude: 21.0249, longitude: 105.8551),
                tag: .paper, age: "1d", points: 25),
        MapSpot(postID: GalleryPost.SampleID.bottleSpiral, title: "Bottle flower spiral", author: Community.max,
                imageName: "RecycleProject3", coordinate: .init(latitude: 21.0236, longitude: 105.8498),
                tag: .plastic, age: "14h", points: 30),
    ]

    static let clusters: [MapCluster] = [
        MapCluster(id: 1, coordinate: .init(latitude: 21.0321, longitude: 105.8561),
                   counts: [.plastic: 5, .paper: 4, .glass: 2, .metal: 1]),
        MapCluster(id: 2, coordinate: .init(latitude: 21.0262, longitude: 105.8478),
                   counts: [.plastic: 2, .paper: 2, .glass: 1]),
        MapCluster(id: 3, coordinate: .init(latitude: 21.0282, longitude: 105.8577),
                   counts: [.plastic: 3, .paper: 2, .glass: 2, .metal: 1]),
        MapCluster(id: 4, coordinate: .init(latitude: 21.0360, longitude: 105.8440),
                   counts: [.plastic: 14, .paper: 10, .glass: 6, .metal: 4]),
        MapCluster(id: 5, coordinate: .init(latitude: 21.0200, longitude: 105.8600),
                   counts: [.plastic: 11, .paper: 8, .glass: 5, .metal: 3]),
        MapCluster(id: 6, coordinate: .init(latitude: 21.0350, longitude: 105.8620),
                   counts: [.plastic: 8, .paper: 6, .glass: 3, .metal: 2]),
        MapCluster(id: 7, coordinate: .init(latitude: 21.0190, longitude: 105.8450),
                   counts: [.plastic: 6, .paper: 5, .glass: 3, .metal: 1]),
        MapCluster(id: 8, coordinate: .init(latitude: 21.0400, longitude: 105.8530),
                   counts: [.plastic: 2, .paper: 2, .glass: 1]),
    ]

    static func spots(for filter: MaterialTag?) -> [MapSpot] {
        guard let filter else { return spots }
        return spots.filter { $0.tag == filter }
    }

    /// Sample items recycled within `nearbyRadiusMeters` of `origin`.
    static func nearbyCount(for filter: MaterialTag?, from origin: CLLocationCoordinate2D = userLocation) -> Int {
        let inRange = { (coordinate: CLLocationCoordinate2D) in
            distance(to: coordinate, from: origin) <= nearbyRadiusMeters
        }
        return spots(for: filter).filter { inRange($0.coordinate) }.count
            + clusters.filter { inRange($0.coordinate) }.map { $0.count(for: filter) }.reduce(0, +)
    }

    static func distance(to coordinate: CLLocationCoordinate2D,
                         from origin: CLLocationCoordinate2D = userLocation) -> CLLocationDistance {
        CLLocation(latitude: origin.latitude, longitude: origin.longitude)
            .distance(from: CLLocation(latitude: coordinate.latitude, longitude: coordinate.longitude))
    }

    /// "400 m" / "1.2 km", rounded the way people say it.
    static func distanceText(to coordinate: CLLocationCoordinate2D,
                             from origin: CLLocationCoordinate2D = userLocation) -> String {
        let meters = distance(to: coordinate, from: origin)
        let rounded = meters < 1_000 ? (meters / 50).rounded() * 50 : (meters / 100).rounded() * 100
        return Measurement(value: rounded, unit: UnitLength.meters)
            .formatted(.measurement(width: .abbreviated, usage: .road))
    }
}
