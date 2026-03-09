import SwiftUI

struct StatsView: View {
    @EnvironmentObject var gameManager: GameManager
    @Environment(\.dismiss) var dismiss
    
    private var stats: GameStatistics {
        gameManager.gameEngine.getStatistics()
    }
    
    var body: some View {
        NavigationView {
            ZStack {
                Color.gameBackground
                    .ignoresSafeArea()
                
                ScrollView {
                    VStack(spacing: 24) {
                        // Main stats
                        mainStatsGrid
                            .padding(.horizontal, 20)
                        
                        // Guess distribution
                        guessDistributionView
                            .padding(.horizontal, 20)
                        
                        // Streak info
                        streakView
                            .padding(.horizontal, 20)
                    }
                    .padding(.vertical, 24)
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                    .foregroundColor(.accentSpotify)
                }
                
                ToolbarItem(placement: .principal) {
                    Text("Statistics")
                        .font(.system(size: 17, weight: .semibold))
                        .foregroundColor(.textPrimary)
                }
            }
            .toolbarBackground(Color.gameBackground, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
        .preferredColorScheme(.dark)
    }
    
    // MARK: - Main Stats Grid
    
    private var mainStatsGrid: some View {
        LazyVGrid(columns: [
            GridItem(.flexible()),
            GridItem(.flexible())
        ], spacing: 12) {
            statCard(value: "\(stats.gamesPlayed)", label: "Games Played", icon: "gamecontroller.fill")
            statCard(value: String(format: "%.0f%%", stats.winPercentage), label: "Win Rate", icon: "percent")
            statCard(value: "\(stats.currentStreak)", label: "Current Streak", icon: "flame.fill")
            statCard(value: "\(stats.maxStreak)", label: "Best Streak", icon: "trophy.fill")
        }
    }
    
    private func statCard(value: String, label: String, icon: String) -> some View {
        VStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 24))
                .foregroundColor(.accentSpotify)
            
            Text(value)
                .font(.system(size: 28, weight: .bold))
                .foregroundColor(.textPrimary)
            
            Text(label)
                .font(.system(size: 13))
                .foregroundColor(.textSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 20)
        .cardStyle()
    }
    
    // MARK: - Guess Distribution
    
    private var guessDistributionView: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Guess Distribution")
                .font(.system(size: 16, weight: .semibold))
                .foregroundColor(.textPrimary)
            
            VStack(spacing: 8) {
                ForEach(1...10, id: \.self) { guessNumber in
                    distributionRow(guessNumber: guessNumber)
                }
            }
        }
        .padding(16)
        .cardStyle()
    }
    
    private func distributionRow(guessNumber: Int) -> some View {
        let count = stats.guessDistribution[guessNumber] ?? 0
        let maxCount = stats.guessDistribution.values.max() ?? 1
        let percentage = maxCount > 0 ? CGFloat(count) / CGFloat(maxCount) : 0
        
        return HStack(spacing: 8) {
            Text("\(guessNumber)")
                .font(.system(size: 14, weight: .medium))
                .foregroundColor(.textSecondary)
                .frame(width: 20)
            
            GeometryReader { geometry in
                HStack {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(count > 0 ? Color.accentSpotify : Color.cardBorder)
                        .frame(width: max(30, geometry.size.width * percentage))
                    
                    Spacer()
                }
            }
            .frame(height: 24)
            
            Text("\(count)")
                .font(.system(size: 14, weight: .medium))
                .foregroundColor(.textPrimary)
                .frame(width: 30, alignment: .trailing)
        }
    }
    
    // MARK: - Streak View
    
    private var streakView: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Streak Info")
                .font(.system(size: 16, weight: .semibold))
                .foregroundColor(.textPrimary)
            
            HStack(spacing: 16) {
                streakItem(
                    value: stats.currentStreak,
                    label: "Current",
                    isActive: stats.currentStreak > 0
                )
                
                Divider()
                    .frame(height: 50)
                    .background(Color.cardBorder)
                
                streakItem(
                    value: stats.maxStreak,
                    label: "Best",
                    isActive: false
                )
            }
        }
        .padding(16)
        .cardStyle()
    }
    
    private func streakItem(value: Int, label: String, isActive: Bool) -> some View {
        VStack(spacing: 4) {
            HStack(spacing: 4) {
                if isActive && value > 0 {
                    Image(systemName: "flame.fill")
                        .foregroundColor(.orange)
                }
                
                Text("\(value)")
                    .font(.system(size: 24, weight: .bold))
                    .foregroundColor(isActive && value > 0 ? .orange : .textPrimary)
            }
            
            Text(label)
                .font(.system(size: 13))
                .foregroundColor(.textSecondary)
        }
        .frame(maxWidth: .infinity)
    }
}

#Preview {
    StatsView()
        .environmentObject(GameManager())
}
