import SwiftUI

struct CO2InsightsView: View {
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
                    
                    // Bar chart
                    chartSection
                    
                    // Impact visualization
                    impactSection
                    
                    // Stats grid
                    statsSection
                    
                    // Environmental facts
                    factsSection
                }
                .padding()
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("CO₂ Saved")
        .navigationBarTitleDisplayMode(.large)
        .toolbarBackground(.visible, for: .navigationBar)
        .toolbarBackground(.ultraThinMaterial, for: .navigationBar)
    }
    
    // MARK: - Sections
    
    private var heroSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "carbon.monoxide.cloud.fill")
                    .font(.title2)
                    .foregroundStyle(.red)
                Text("CO₂ Emissions Saved")
                    .font(.headline)
                    .foregroundStyle(.secondary)
            }
            
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text("1,250")
                    .font(.system(size: 56, weight: .bold, design: .rounded))
                Text("kg")
                    .font(.title)
                    .foregroundStyle(.secondary)
            }
            
            HStack(spacing: 4) {
                Image(systemName: "arrow.down.right")
                    .font(.subheadline.weight(.semibold))
                Text("-9% emissions vs. average")
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
            Text("Daily Savings")
                .font(.headline)
            
            BarChartView(
                data: selectedPeriod == .week ? SampleData.co2Weekly : SampleData.co2Monthly,
                accentColor: .red
            )
            .id(selectedPeriod)
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .fill(.ultraThinMaterial)
        )
    }
    
    private var impactSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Environmental Impact")
                .font(.headline)
            
            HStack(spacing: 16) {
                ImpactCard(
                    icon: "tree.fill",
                    value: "24",
                    label: "Trees Equivalent",
                    color: .green
                )
                
                ImpactCard(
                    icon: "car.fill",
                    value: "3,200",
                    label: "km Not Driven",
                    color: .blue
                )
            }
            
            HStack(spacing: 16) {
                ImpactCard(
                    icon: "drop.fill",
                    value: "8,400",
                    label: "Liters Water",
                    color: .cyan
                )
                
                ImpactCard(
                    icon: "bolt.fill",
                    value: "520",
                    label: "kWh Energy",
                    color: .yellow
                )
            }
        }
    }
    
    private var statsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Statistics")
                .font(.headline)
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                ForEach(SampleData.co2Stats) { stat in
                    StatCardView(stat: stat)
                }
            }
        }
    }
    
    private var factsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Did You Know?")
                .font(.headline)
            
            VStack(spacing: 12) {
                FactCard(
                    emoji: "🌍",
                    fact: "The average person produces about 4 tons of CO₂ per year. You've offset 31% of that!"
                )
                
                FactCard(
                    emoji: "🌱",
                    fact: "One tree absorbs approximately 22kg of CO₂ per year. Your savings equal 57 trees working for a year!"
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
                    .init(color: Color.red.opacity(0.25), location: 0.0),
                    .init(color: Color.red.opacity(0.1), location: 0.2),
                    .init(color: Color.red.opacity(0.0), location: 0.4)
                ],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()
        }
    }
}

// MARK: - Impact Card

struct ImpactCard: View {
    let icon: String
    let value: String
    let label: String
    let color: Color
    
    @State private var appeared = false
    
    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: icon)
                .font(.title)
                .foregroundStyle(color)
                .symbolEffect(.bounce, value: appeared)
            
            Text(value)
                .font(.title3.weight(.bold))
            
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(.ultraThinMaterial)
        )
        .scaleEffect(appeared ? 1 : 0.8)
        .opacity(appeared ? 1 : 0)
        .onAppear {
            withAnimation(.spring(response: 0.5, dampingFraction: 0.7).delay(0.1)) {
                appeared = true
            }
        }
    }
}

// MARK: - Fact Card

struct FactCard: View {
    let emoji: String
    let fact: String
    
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Text(emoji)
                .font(.title)
            
            Text(fact)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            
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
        CO2InsightsView()
    }
}
