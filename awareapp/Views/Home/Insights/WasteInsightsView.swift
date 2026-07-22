import SwiftUI

struct WasteInsightsView: View {
    @State private var selectedPeriod: TimePeriod = .week
    
    enum TimePeriod: String, CaseIterable {
        case week = "Week"
        case month = "Month"
    }
    
    var body: some View {
        ZStack {
            backgroundView
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    // Hero stat
                    heroSection
                    
                    // Period selector
                    periodPicker
                    
                    // Line chart
                    chartSection
                    
                    // Stats grid
                    statsSection
                    
                    // Breakdown
                    breakdownSection
                    
                    // Tips
                    tipsSection
                }
                .padding()
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Waste Saved")
        .navigationBarTitleDisplayMode(.large)
        .toolbarBackground(.visible, for: .navigationBar)
        .toolbarBackground(.ultraThinMaterial, for: .navigationBar)
    }
    
    // MARK: - Sections
    
    private var heroSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "trash.fill")
                    .font(.title2)
                    .foregroundStyle(.green)
                Text("Total Waste Saved")
                    .font(.headline)
                    .foregroundStyle(.secondary)
            }
            
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text("6,700")
                    .font(.system(size: 56, weight: .bold, design: .rounded))
                Text("g")
                    .font(.title)
                    .foregroundStyle(.secondary)
            }
            
            HStack(spacing: 4) {
                Image(systemName: "arrow.up.right")
                    .font(.subheadline.weight(.semibold))
                Text("+12% from last week")
                    .font(.subheadline.weight(.medium))
            }
            .foregroundStyle(.green)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .fill(.ultraThinMaterial)
        )
    }
    
    private var periodPicker: some View {
        Picker("Period", selection: $selectedPeriod) {
            ForEach(TimePeriod.allCases, id: \.self) { period in
                Text(period.rawValue).tag(period)
            }
        }
        .pickerStyle(.segmented)
    }
    
    private var chartSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Trend")
                .font(.headline)
            
            LineChartView(
                data: selectedPeriod == .week ? SampleData.wasteWeekly : SampleData.wasteMonthly,
                accentColor: .green
            )
            .id(selectedPeriod) // Force re-animation on period change
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .fill(.ultraThinMaterial)
        )
    }
    
    private var statsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Statistics")
                .font(.headline)
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                ForEach(SampleData.wasteStats) { stat in
                    StatCardView(stat: stat)
                }
            }
        }
    }
    
    private var breakdownSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Breakdown by Category")
                .font(.headline)
            
            DonutChartView(
                data: SampleData.wasteByCategory,
                colors: [.green, .blue, .cyan, .orange, .gray]
            )
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .fill(.ultraThinMaterial)
        )
    }
    
    private var tipsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Tips to Improve")
                .font(.headline)
            
            VStack(spacing: 12) {
                TipCard(
                    icon: "lightbulb.fill",
                    color: .yellow,
                    title: "Reduce Plastic Usage",
                    description: "Bring reusable bags when shopping to cut plastic waste by up to 40%."
                )
                
                TipCard(
                    icon: "arrow.3.trianglepath",
                    color: .green,
                    title: "Compost Food Scraps",
                    description: "Start composting to divert organic waste from landfills."
                )
            }
        }
    }
    
    private var backgroundView: some View {
        ZStack(alignment: .top) {
            Color(uiColor: .systemGroupedBackground)
                .ignoresSafeArea()
            LinearGradient(
                stops: [
                    .init(color: Color.green.opacity(0.35), location: 0.0),
                    .init(color: Color.green.opacity(0.15), location: 0.2),
                    .init(color: Color.green.opacity(0.0), location: 0.4)
                ],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()
        }
    }
}

// MARK: - Tip Card

struct TipCard: View {
    let icon: String
    let color: Color
    let title: String
    let description: String
    
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundStyle(color)
                .frame(width: 36, height: 36)
                .background(color.opacity(0.15), in: Circle())
            
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.subheadline.weight(.semibold))
                Text(description)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            
            Spacer()
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(.ultraThinMaterial)
        )
    }
}

#Preview {
    NavigationStack {
        WasteInsightsView()
    }
}
