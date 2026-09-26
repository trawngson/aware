import MapKit
import SwiftUI

/// Full-screen map of recycling projects shared near the user (demo data).
struct RecyclingMapView: View {
    @State private var position: MapCameraPosition = .region(RecyclingMapData.region)
    @State private var filter: MaterialTag?
    @State private var selectedSpotID: UUID? = RecyclingMapData.spots.first?.id
    @Environment(\.deviceColorScheme) private var deviceColorScheme

    /// The map is light, except in Dark mode, where it follows the device so
    /// the tab bar over it (which takes its style from the map) stays dark.
    private var mapIsLight: Bool { deviceColorScheme != .dark }

    private var visibleSpots: [MapSpot] { RecyclingMapData.spots(for: filter) }

    private var selectedSpot: MapSpot? {
        visibleSpots.first { $0.id == selectedSpotID }
    }

    var body: some View {
        Map(position: $position) {
            ForEach(RecyclingMapData.clusters) { cluster in
                let count = cluster.count(for: filter)
                if count > 0 {
                    Annotation("", coordinate: cluster.coordinate) {
                        ClusterBubble(count: count)
                            .onTapGesture { zoom(to: cluster.coordinate) }
                    }
                    .annotationTitles(.hidden)
                }
            }

            Annotation("", coordinate: RecyclingMapData.userLocation) {
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
        .safeAreaInset(edge: .bottom) {
            if let spot = selectedSpot {
                selectedCard(spot)
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
            ToolbarItem(placement: .topBarTrailing) {
                Text("\(RecyclingMapData.nearbyCount(for: filter)) nearby")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(mapIsLight ? Theme.green : Theme.mint)
                    .contentTransition(.numericText())
                    .fixedSize()
            }
        }
        .animation(.snappy, value: filter)
        .animation(.snappy, value: selectedSpotID)
    }

    // MARK: - Filters

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
            if let current = selectedSpotID, !RecyclingMapData.spots(for: tag).contains(where: { $0.id == current }) {
                selectedSpotID = RecyclingMapData.spots(for: tag).first?.id
            } else if selectedSpotID == nil {
                selectedSpotID = RecyclingMapData.spots(for: tag).first?.id
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
                            .shadow(color: Theme.greenDeep.opacity(0.32), radius: 6, y: 5)
                    }
                }
                .glassCapsule(isSelected ? GlassStyle(top: 0, bottom: 0, border: 0.35, highlight: 0.35, material: nil,
                                                      shadow: .clear, shadowRadius: 0, shadowY: 0)
                                         : .chrome)
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
                Image(spot.imageName)
                    .resizable()
                    .scaledToFill()
                    .frame(width: 56, height: 56)
                    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                VStack(alignment: .leading, spacing: 3) {
                    Text(spot.title)
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(Theme.ink)
                    HStack(spacing: 5) {
                        MemberAvatar(member: spot.author, size: 16)
                        Text("\(spot.author.name) · \(RecyclingMapData.distanceText(to: spot.coordinate)) · \(spot.age)")
                            .font(.system(size: 12))
                            .foregroundStyle(Theme.ink.opacity(0.62))
                            .lineLimit(1)
                    }
                }
                Spacer(minLength: 0)
                Text("+\(spot.points)")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(Capsule().fill(Theme.activeGradient))
                    .shadow(color: Theme.greenDeep.opacity(0.3), radius: 5, y: 4)
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
    var body: some View {
        Map(initialPosition: .region(RecyclingMapData.miniRegion), interactionModes: []) {
            ForEach(RecyclingMapData.spots.prefix(2)) { spot in
                Annotation("", coordinate: spot.coordinate) {
                    PhotoPin(spot: spot, width: 44, imageHeight: 34, showsAuthor: false)
                }
                .annotationTitles(.hidden)
            }
            if let cluster = RecyclingMapData.clusters.first {
                Annotation("", coordinate: cluster.coordinate) {
                    ClusterBubble(count: cluster.count(for: nil), size: 22)
                }
                .annotationTitles(.hidden)
            }
            Annotation("", coordinate: RecyclingMapData.userLocation) {
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
