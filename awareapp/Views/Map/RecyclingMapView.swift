import MapKit
import SwiftUI

/// Full-screen map of recycling projects shared near the user: real posts
/// with a location and, while samples are on, the sample spots and clusters.
struct RecyclingMapView: View {
    @State private var position: MapCameraPosition = .region(RecyclingMapData.region)
    @State private var filter: MaterialTag?
    @State private var selectedSpotID: UUID? = RecyclingMapData.spots.first?.id
    @State private var isLocationOff = false
    @Environment(\.deviceColorScheme) private var deviceColorScheme
    @Environment(\.openURL) private var openURL
    @ObservedObject private var session = AppSession.shared
    @ObservedObject private var mapStore = MapStore.shared

    /// The map is light, except in Dark mode, where it follows the device so
    /// the tab bar over it (which takes its style from the map) stays dark.
    private var mapIsLight: Bool { deviceColorScheme != .dark }

    private func spots(for filter: MaterialTag?) -> [MapSpot] {
        mapStore.spots(for: filter) + (session.showSamples ? RecyclingMapData.spots(for: filter) : [])
    }

    private var visibleSpots: [MapSpot] { spots(for: filter) }

    private var clusters: [MapCluster] { session.showSamples ? RecyclingMapData.clusters : [] }

    private var nearbyCount: Int {
        (session.showSamples ? RecyclingMapData.nearbyCount(for: filter, from: mapStore.origin) : 0)
            + mapStore.nearbyCount(for: filter)
    }

    private var selectedSpot: MapSpot? {
        visibleSpots.first { $0.id == selectedSpotID }
    }

    var body: some View {
        Map(position: $position) {
            ForEach(clusters) { cluster in
                let count = cluster.count(for: filter)
                if count > 0 {
                    Annotation("", coordinate: cluster.coordinate) {
                        ClusterBubble(count: count)
                            .onTapGesture { zoom(to: cluster.coordinate) }
                    }
                    .annotationTitles(.hidden)
                }
            }

            Annotation("", coordinate: mapStore.origin) {
                UserLocationDot()
            }
            .annotationTitles(.hidden)

            ForEach(visibleSpots) { spot in
                Annotation(spot.title, coordinate: spot.coordinate, anchor: .bottom) {
                    PhotoPin(spot: spot, isSelected: spot.id == selectedSpotID)
                        .onTapGesture { select(spot) }
                }
                .annotationTitles(.hidden)
            }
        }
        .mapStyle(.standard(pointsOfInterest: .excludingAll))
        .mapControls {
            MapCompass()
            MapScaleView()
        }
        .environment(\.colorScheme, mapIsLight ? .light : .dark)
        .overlay(alignment: .top) {
            // Keeps the navigation bar and chips readable over busy map tiles.
            let shade = mapIsLight ? Color(hex: 0xF8FAF7) : Theme.forestShade
            LinearGradient(
                stops: [.init(color: shade.opacity(mapIsLight ? 0.74 : 0.6), location: 0),
                        .init(color: shade.opacity(0), location: 1)],
                startPoint: .top, endPoint: .bottom
            )
            .frame(height: 170)
            .ignoresSafeArea()
            .allowsHitTesting(false)
        }
        .safeAreaInset(edge: .top) { filterChips }
        .overlay(alignment: .bottom) {
            // Over the map instead of in its safe area, so Apple's Maps logo and
            // Legal link (which must stay visible) sit in the strip left under
            // the card, next to the tab bar, rather than above the card.
            if let spot = selectedSpot {
                selectedCard(spot)
                    .padding(.bottom, 26)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .navigationTitle("Recycling Map")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarColorScheme(mapIsLight ? .light : .dark, for: .navigationBar)
        .toolbarBackground(.hidden, for: .navigationBar)
        .onAppear { NavigationManager.shared.usesLightChrome = mapIsLight }
        .onChange(of: mapIsLight) { _, isLight in NavigationManager.shared.usesLightChrome = isLight }
        .onDisappear { NavigationManager.shared.usesLightChrome = false }
        .toolbar {
            // Finding the user needs location permission, asked for only
            // when they tap this. Offered only with a backend.
            if mapStore.isAvailable {
                ToolbarItem(placement: .topBarTrailing) {
                    Button(action: locate) {
                        Image(systemName: mapStore.usesDeviceLocation ? "location.fill" : "location")
                    }
                    .tint(mapIsLight ? Theme.green : Theme.mint)
                    .accessibilityLabel("Show projects near me")
                }
            }
            ToolbarItem(placement: .topBarTrailing) {
                Text("\(nearbyCount) nearby")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(mapIsLight ? Theme.green : Theme.mint)
                    .contentTransition(.numericText())
                    .fixedSize()
            }
        }
        .animation(.snappy, value: filter)
        .animation(.snappy, value: selectedSpotID)
        .task {
            await mapStore.refresh()
            if selectedSpot == nil { selectedSpotID = visibleSpots.first?.id }
        }
        .alert("Location is off", isPresented: $isLocationOff) {
            Button("Open Settings") {
                if let url = URL(string: UIApplication.openSettingsURLString) { openURL(url) }
            }
            Button("Not now", role: .cancel) {}
        } message: {
            Text("To see projects near you, allow AWARE to use your location in Settings. The map works without it too.")
        }
    }

    private func locate() {
        Task {
            if await mapStore.locateMe() {
                withAnimation(.smooth(duration: 0.6)) {
                    position = .region(MKCoordinateRegion(center: mapStore.origin,
                                                          span: RecyclingMapData.region.span))
                }
            } else if LocationProvider.shared.isDenied {
                isLocationOff = true
            }
        }
    }

    // MARK: - Filters

    /// `.chrome` without its drop shadow, so the chips sit flat on the map.
    private static let chipGlass: GlassStyle = {
        var style = GlassStyle.chrome
        style.shadow = .clear
        style.shadowRadius = 0
        style.shadowY = 0
        return style
    }()

    private var filterChips: some View {
        ScrollView(.horizontal) {
            HStack(spacing: 8) {
                chip(nil, title: "All")
                ForEach(MaterialTag.allCases) { tag in
                    chip(tag, title: tag.title)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 6)
        }
        .scrollIndicators(.hidden)
    }

    private func chip(_ tag: MaterialTag?, title: LocalizedStringKey) -> some View {
        let isSelected = filter == tag
        return Button {
            filter = tag
            if let current = selectedSpotID, !spots(for: tag).contains(where: { $0.id == current }) {
                selectedSpotID = spots(for: tag).first?.id
            } else if selectedSpotID == nil {
                selectedSpotID = spots(for: tag).first?.id
            }
        } label: {
            Text(title)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(isSelected ? .white : Theme.ink.opacity(0.72))
                .padding(.horizontal, 14)
                .padding(.vertical, 8)
                .background {
                    if isSelected {
                        Capsule().fill(Theme.activeGradient)
                    }
                }
                .glassCapsule(isSelected ? GlassStyle(top: 0, bottom: 0, border: 0.35, highlight: 0.35, material: nil,
                                                      shadow: .clear, shadowRadius: 0, shadowY: 0)
                                         : Self.chipGlass)
        }
        .buttonStyle(PressableStyle())
        .accessibilityAddTraits(isSelected ? .isSelected : [])
    }

    // MARK: - Selected project

    private func selectedCard(_ spot: MapSpot) -> some View {
        NavigationLink {
            PostThreadView(postID: spot.postID)
        } label: {
            HStack(spacing: 12) {
                SpotPhoto(spot: spot)
                    .frame(width: 56, height: 56)
                    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                VStack(alignment: .leading, spacing: 3) {
                    Text(spot.title)
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(Theme.ink)
                    HStack(spacing: 5) {
                        MemberAvatar(member: spot.author, size: 16)
                        Text("\(spot.author.name) · \(RecyclingMapData.distanceText(to: spot.coordinate, from: mapStore.origin)) · \(spot.age)")
                            .font(.system(size: 12))
                            .foregroundStyle(Theme.ink.opacity(0.62))
                            .lineLimit(1)
                    }
                }
                Spacer(minLength: 0)
                if spot.points > 0 {
                    Text("+\(spot.points)")
                        .font(.system(size: 13, weight: .bold))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(Capsule().fill(Theme.activeGradient))
                        .shadow(color: Theme.greenDeep.opacity(0.3), radius: 5, y: 4)
                }
            }
            .padding(12)
            .glass(GlassStyle(top: 0.76, bottom: 0.58, border: 0.8, highlight: 0.92, material: .ultraThinMaterial,
                              shadow: Color(hex: 0x081C10, opacity: 0.22), shadowRadius: 18, shadowY: 16),
                   cornerRadius: 24)
        }
        .buttonStyle(PressableStyle())
        .padding(.horizontal, 16)
        .padding(.bottom, 10)
    }

    // MARK: - Camera

    private func select(_ spot: MapSpot) {
        selectedSpotID = spot.id
        withAnimation(.smooth(duration: 0.6)) {
            position = .region(MKCoordinateRegion(
                center: CLLocationCoordinate2D(latitude: spot.coordinate.latitude - 0.0012,
                                               longitude: spot.coordinate.longitude),
                span: MKCoordinateSpan(latitudeDelta: 0.01, longitudeDelta: 0.008)
            ))
        }
    }

    private func zoom(to coordinate: CLLocationCoordinate2D) {
        withAnimation(.smooth(duration: 0.6)) {
            position = .region(MKCoordinateRegion(
                center: coordinate,
                span: MKCoordinateSpan(latitudeDelta: 0.005, longitudeDelta: 0.004)
            ))
        }
    }
}

/// Small, non-interactive map for the Home card.
struct MiniRecyclingMap: View {
    @ObservedObject private var session = AppSession.shared
    @ObservedObject private var mapStore = MapStore.shared

    private var spots: [MapSpot] {
        Array((mapStore.spots(for: nil) + (session.showSamples ? RecyclingMapData.spots : [])).prefix(2))
    }

    var body: some View {
        Map(initialPosition: .region(RecyclingMapData.miniRegion), interactionModes: []) {
            ForEach(spots) { spot in
                Annotation("", coordinate: spot.coordinate) {
                    PhotoPin(spot: spot, width: 44, imageHeight: 34, showsAuthor: false)
                }
                .annotationTitles(.hidden)
            }
            if session.showSamples, let cluster = RecyclingMapData.clusters.first {
                Annotation("", coordinate: cluster.coordinate) {
                    ClusterBubble(count: cluster.count(for: nil), size: 22)
                }
                .annotationTitles(.hidden)
            }
            Annotation("", coordinate: mapStore.origin) {
                UserLocationDot(size: 14)
            }
            .annotationTitles(.hidden)
        }
        .mapStyle(.standard(pointsOfInterest: .excludingAll))
        .environment(\.colorScheme, .light)
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}

#Preview {
    NavigationStack {
        RecyclingMapView()
    }
}
