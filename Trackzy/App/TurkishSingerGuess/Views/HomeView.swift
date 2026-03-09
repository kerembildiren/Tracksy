import SwiftUI

/// Home screen: game name + logo at top, then mode options (All, Turkish, Create). Only Turkish is active for now.
struct HomeView: View {
    var onPlay: () async -> Void
    var onHowToPlay: () -> Void
    var onStats: () -> Void
    
    @State private var isStarting = false
    @State private var showComingSoon = false
    @State private var comingSoonMessage = ""
    
    var body: some View {
        ZStack {
            Color.gameBackground
                .ignoresSafeArea()
            
            VStack(spacing: 0) {
                // Top section: logo (includes wordmark)
                VStack(spacing: 0) {
                    logoView
                }
                .frame(maxWidth: .infinity)
                .padding(.top, 48)
                .padding(.bottom, 40)
                
                // Mode options: All, Turkish, Create
                VStack(spacing: 14) {
                    modeButton(
                        title: "All",
                        subtitle: "All nationalities",
                        icon: "globe",
                        enabled: false
                    ) {
                        comingSoonMessage = "More singers from other nationalities coming soon. You’ll need a separate playlist to play."
                        showComingSoon = true
                    }
                    
                    modeButton(
                        title: "Turkish",
                        subtitle: "Guess from Turkish singers",
                        icon: "music.mic",
                        enabled: true,
                        isPrimary: true
                    ) {
                        startGame()
                    }
                    
                    modeButton(
                        title: "Create",
                        subtitle: "Pick an artist, share a link",
                        icon: "link",
                        enabled: false
                    ) {
                        comingSoonMessage = "Create a custom puzzle: pick an artist, get a link, and share it. Whoever opens the link will try to find that artist."
                        showComingSoon = true
                    }
                }
                .padding(.horizontal, 24)
                
                Spacer()
                
                // Secondary: How to Play, Stats
                VStack(spacing: 12) {
                    Button(action: onHowToPlay) {
                        HStack(spacing: 8) {
                            Image(systemName: "questionmark.circle")
                            Text("How to Play")
                                .font(.system(size: 15, weight: .medium))
                        }
                        .foregroundColor(.textSecondary)
                    }
                    
                    Button(action: onStats) {
                        HStack(spacing: 8) {
                            Image(systemName: "chart.bar")
                            Text("Stats")
                                .font(.system(size: 15, weight: .medium))
                        }
                        .foregroundColor(.textSecondary)
                    }
                }
                .padding(.bottom, 32)
            }
        }
        .alert("Coming soon", isPresented: $showComingSoon) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(comingSoonMessage)
        }
    }
    
    // MARK: - Logo
    
    private var logoView: some View {
        Image("Logo")
            .resizable()
            .scaledToFit()
            .frame(maxWidth: 200)
    }
    
    // MARK: - Mode button
    
    private func modeButton(
        title: String,
        subtitle: String,
        icon: String,
        enabled: Bool,
        isPrimary: Bool = false,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            HStack(spacing: 14) {
                ZStack {
                    RoundedRectangle(cornerRadius: 10)
                        .fill(isPrimary && enabled ? Color.accentSpotify.opacity(0.25) : Color.cardBorder.opacity(0.5))
                        .frame(width: 44, height: 44)
                    Image(systemName: icon)
                        .font(.system(size: 20, weight: .semibold))
                        .foregroundColor(enabled ? (isPrimary ? .accentSpotify : .textPrimary) : .textMuted)
                }
                
                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.system(size: 17, weight: .semibold))
                        .foregroundColor(enabled ? .textPrimary : .textMuted)
                    Text(subtitle)
                        .font(.system(size: 13))
                        .foregroundColor(.textMuted)
                }
                
                Spacer()
                
                if enabled && isPrimary && isStarting {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .gameBackground))
                } else if enabled {
                    Image(systemName: "chevron.right")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(isPrimary ? .gameBackground : .textMuted)
                } else {
                    Text("Soon")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundColor(.textMuted)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.cardBorder)
                        .cornerRadius(6)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 14)
            .background(
                RoundedRectangle(cornerRadius: 14)
                    .fill(isPrimary && enabled ? Color.accentSpotify : Color.cardBackground)
            )
            .foregroundColor(isPrimary && enabled ? .gameBackground : .textPrimary)
            .overlay(
                RoundedRectangle(cornerRadius: 14)
                    .stroke(Color.cardBorder, lineWidth: enabled && !isPrimary ? 1 : 0)
            )
        }
        .buttonStyle(.plain)
        .disabled(enabled && isStarting)
    }
    
    private func startGame() {
        guard !isStarting else { return }
        isStarting = true
        Task {
            await onPlay()
            await MainActor.run {
                isStarting = false
            }
        }
    }
}

#Preview {
    HomeView(
        onPlay: { },
        onHowToPlay: { },
        onStats: { }
    )
}
