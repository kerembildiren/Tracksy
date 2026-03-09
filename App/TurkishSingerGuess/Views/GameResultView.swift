import SwiftUI

struct GameResultView: View {
    @EnvironmentObject var gameManager: GameManager
    @Environment(\.dismiss) var dismiss
    @Environment(\.openURL) private var openURL
    
    private var isWin: Bool {
        gameManager.currentState?.status == .won
    }
    
    private var guessCount: Int {
        gameManager.currentState?.guesses.count ?? 0
    }
    
    var body: some View {
        ZStack {
            Color.gameBackground
                .ignoresSafeArea()
            
            VStack(spacing: 24) {
                // Close button
                HStack {
                    Spacer()
                    Button(action: { dismiss() }) {
                        Image(systemName: "xmark")
                            .font(.system(size: 18, weight: .semibold))
                            .foregroundColor(.textSecondary)
                            .frame(width: 32, height: 32)
                    }
                }
                .padding(.horizontal, 20)
                .padding(.top, 16)
                
                Spacer()
                
                // Result icon
                resultIcon
                
                // Result text
                VStack(spacing: 8) {
                    Text(isWin ? "Congratulations!" : "Game Over")
                        .font(.system(size: 28, weight: .bold))
                        .foregroundColor(.textPrimary)
                    
                    if isWin {
                        Text("You found the artist in \(guessCount) guess\(guessCount == 1 ? "" : "es")!")
                            .font(.system(size: 16))
                            .foregroundColor(.textSecondary)
                    } else {
                        Text("Better luck next time!")
                            .font(.system(size: 16))
                            .foregroundColor(.textSecondary)
                    }
                }
                
                // Correct artist reveal
                if let artist = gameManager.correctArtist {
                    correctArtistCard(artist)
                        .padding(.horizontal, 20)
                }
                
                // Track / Listen on Spotify
                if let artist = gameManager.correctArtist {
                    trackSection(artist)
                        .padding(.horizontal, 20)
                }
                
                Spacer()
                
                // Share button
                shareButton
                    .padding(.horizontal, 20)
                    .padding(.bottom, 32)
            }
        }
        .onAppear {
            if let artist = gameManager.correctArtist {
                let urlString = artist.topTrackUri ?? "https://open.spotify.com/artist/\(artist.id)"
                if let url = URL(string: urlString) {
                    openURL(url)
                }
            }
        }
        .preferredColorScheme(.dark)
    }
    
    // MARK: - Result Icon
    
    private var resultIcon: some View {
        ZStack {
            Circle()
                .fill(isWin ? Color.hintCorrect.opacity(0.2) : Color.accentGold.opacity(0.2))
                .frame(width: 100, height: 100)
            
            Image(systemName: isWin ? "trophy.fill" : "music.mic")
                .font(.system(size: 44))
                .foregroundColor(isWin ? .hintCorrect : .accentGold)
        }
    }
    
    // MARK: - Correct Artist Card
    
    private func correctArtistCard(_ artist: Artist) -> some View {
        VStack(spacing: 12) {
            Text("The answer was")
                .font(.system(size: 14))
                .foregroundColor(.textMuted)
            
            HStack(spacing: 16) {
                correctArtistThumb(artist)
                
                VStack(alignment: .leading, spacing: 4) {
                    Text(artist.name)
                        .font(.system(size: 20, weight: .bold))
                        .foregroundColor(.textPrimary)
                    
                    HStack(spacing: 8) {
                        if let nationality = artist.nationality {
                            Label(nationality, systemImage: "globe")
                                .font(.system(size: 13))
                                .foregroundColor(.textSecondary)
                        }
                        
                        if let year = artist.debutYear {
                            Label(String(year), systemImage: "calendar")
                                .font(.system(size: 13))
                                .foregroundColor(.textSecondary)
                        }
                    }
                }
                
                Spacer()
            }
            .padding(16)
            .cardStyle()
        }
    }
    
    @ViewBuilder
    private func correctArtistThumb(_ artist: Artist) -> some View {
        Group {
            if let urlString = artist.imageUrl, let url = URL(string: urlString) {
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .success(let image):
                        image.resizable().scaledToFill()
                    case .failure(_), .empty:
                        placeholderThumb(artist)
                    @unknown default:
                        placeholderThumb(artist)
                    }
                }
            } else {
                placeholderThumb(artist)
            }
        }
        .frame(width: 60, height: 60)
        .clipShape(Circle())
        .overlay(Circle().stroke(Color.accentSpotify.opacity(0.3), lineWidth: 1))
    }
    
    private func placeholderThumb(_ artist: Artist) -> some View {
        Circle()
            .fill(Color.accentSpotify.opacity(0.2))
            .overlay(
                Text(String(artist.name.prefix(1)).uppercased())
                    .font(.system(size: 24, weight: .bold))
                    .foregroundColor(.accentSpotify)
            )
    }
    
    // MARK: - Track section (opens in Spotify on appear)
    
    @ViewBuilder
    private func trackSection(_ artist: Artist) -> some View {
        let urlString = artist.topTrackUri ?? "https://open.spotify.com/artist/\(artist.id)"
        if let url = URL(string: urlString) {
            VStack(spacing: 12) {
                if let name = artist.topTrackName, !name.isEmpty {
                    Text(name)
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(.textSecondary)
                }
                Button(action: { openURL(url) }) {
                    HStack {
                        Image(systemName: "play.circle.fill")
                        Text("Listen on Spotify")
                            .font(.buttonText)
                    }
                    .foregroundColor(.gameBackground)
                    .frame(maxWidth: .infinity)
                    .frame(height: 48)
                    .background(Color.accentSpotify)
                    .cornerRadius(24)
                }
            }
            .padding(16)
            .cardStyle()
        }
    }
    
    // MARK: - Share Button
    
    private var shareButton: some View {
        Button(action: shareResults) {
            HStack {
                Image(systemName: "square.and.arrow.up")
                Text("Share Results")
                    .font(.buttonText)
            }
            .foregroundColor(.gameBackground)
            .frame(maxWidth: .infinity)
            .frame(height: 54)
            .background(Color.accentSpotify)
            .cornerRadius(27)
        }
    }
    
    // MARK: - Share
    
    private func shareResults() {
        let emoji = isWin ? "🎵" : "😢"
        let result = isWin ? "\(guessCount)/10" : "X/10"
        
        let text = """
        Tracksy \(emoji)
        \(result)
        
        Play at: tracksy.app
        """
        
        // In a real app, this would use UIActivityViewController
        UIPasteboard.general.string = text
    }
}

#Preview {
    GameResultView()
        .environmentObject(GameManager())
}
