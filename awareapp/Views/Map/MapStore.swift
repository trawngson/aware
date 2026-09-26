import Combine
import CoreLocation
import MapKit
import SwiftUI

/// Real posts with a location, for the recycling map and Home's map card.
/// The sample spots and clusters come from `RecyclingMapData` and show while
/// samples are on. Without a backend this stays empty.
@MainActor
final class MapStore: ObservableObject {
    static let shared = MapStore()

    /// Real posts on the map, newest first.
    @Published private(set) var posts: [MapPost] = []
    /// Real posts within `RecyclingMapData.nearbyRadiusMeters` of `origin`,
    /// per material filter (nil key: all).
    @Published private(set) var nearbyCounts: [String?: Int] = [:]
    /// Where distances are measured from: the user's location once they share
    /// it, otherwise Hoan Kiem Lake.
    @Published private(set) var origin = RecyclingMapData.userLocation
    @Published private(set) var usesDeviceLocation = false

    private let session: AppSession
    private var backend: CommunityBackend { session.backend }
    /// About 5 km around the origin.
    private static let span = 0.05

    private init(session: AppSession = .shared) {
        self.session = session
    }

    var isAvailable: Bool { session.isBackendConfigured }

    func nearbyCount(for filter: MaterialTag?) -> Int {
        nearbyCounts[filter?.rawValue] ?? 0
    }

    /// Fetches real posts around the origin and the nearby counts.
    func refresh() async {
        guard isAvailable else { return }
        let bounds = MapBounds(minLatitude: origin.latitude - Self.span, minLongitude: origin.longitude - Self.span,
                               maxLatitude: origin.latitude + Self.span, maxLongitude: origin.longitude + Self.span)
        do {
            posts = try await backend.fetchMapPosts(in: bounds, material: nil)
            var counts: [String?: Int] = [:]
            let materials: [String?] = [nil] + MaterialTag.allCases.map { $0.rawValue }
            for material in materials {
                counts[material] = try await backend.fetchNearbyCount(
                    latitude: origin.latitude, longitude: origin.longitude,
                    radius: RecyclingMapData.nearbyRadiusMeters, material: material)
            }
            nearbyCounts = counts
        } catch {
            // Offline: keep what was fetched last.
        }
    }

    /// Asks for the user's location (permission first, the first time) and
    /// measures from there. Returns false when location is off.
    func locateMe() async -> Bool {
        guard let coordinate = await LocationProvider.shared.requestLocation() else { return false }
        origin = coordinate
        usesDeviceLocation = true
        await refresh()
        return true
    }

    /// Real posts as map spots, optionally one material.
    func spots(for filter: MaterialTag?) -> [MapSpot] {
        posts
            .filter { filter == nil || $0.material == filter?.rawValue }
            .map { post in
                MapSpot(postID: post.id,
                        title: post.title ?? String(post.body.prefix(40)),
                        author: CommunityMember(mapPost: post),
                        imageName: nil,
                        imageURL: post.imagePath.flatMap { backend.imageURL(for: $0) },
                        coordinate: CLLocationCoordinate2D(latitude: post.latitude, longitude: post.longitude),
                        tag: post.material.flatMap(MaterialTag.init(rawValue:)),
                        age: GalleryStore.age(of: post.createdAt),
                        points: 0)
            }
    }
}

extension CommunityMember {
    /// The author of a post on the map.
    init(mapPost post: MapPost) {
        self.init(
            id: post.authorID.uuidString.lowercased(),
            name: post.authorName,
            shortName: post.authorName,
            points: 0,
            avatar: .initials(post.authorInitials,
                              top: Color(hex: UInt32(clamping: post.authorTop)),
                              bottom: Color(hex: UInt32(clamping: post.authorBottom)))
        )
    }
}
