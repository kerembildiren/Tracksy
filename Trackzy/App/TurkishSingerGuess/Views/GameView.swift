import SwiftUI

struct GameView: View {
    @EnvironmentObject var gameManager: GameManager
    @State private var showingSearch = false
    @State private var showingStats = false
    @State private var showingResult = false
    @State private var showingHelp = false
    
    var body: some View {
        ZStack {
            Color.gameBackground
                .ignoresSafeArea()
            
            VStack(spacing: 0) {
                // Header
                headerView
                
                // Guess counter
                guessCounterView
                    .padding(.top, 16)
                
                // Guesses list
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 12) {
                            ForEach(gameManager.gameEngine.getGuessesWithHints()) { guess in
                                GuessRowView(guess: guess)
                                    .id(guess.id)
                            }
                        }
                        .padding(.horizontal, 16)
                        .padding(.top, 16)
                    }
                    .onChange(of: gameManager.currentState?.guesses.count) { _ in
                        if let lastGuess = gameManager.gameEngine.getGuessesWithHints().last {
                            withAnimation {
                                proxy.scrollTo(lastGuess.id, anchor: .bottom)
                            }
                        }
                    }
                }
                
                Spacer()
                
                // Bottom action area
                bottomActionView
            }
        }
        .sheet(isPresented: $showingSearch) {
            SearchView { artist in
                makeGuess(artist)
            }
            .environmentObject(gameManager)
        }
        .sheet(isPresented: $showingStats) {
            StatsView()
                .environmentObject(gameManager)
        }
        .sheet(isPresented: $showingResult) {
            GameResultView()
                .environmentObject(gameManager)
        }
        .sheet(isPresented: $showingHelp) {
            HelpView()
        }
        .onChange(of: gameManager.currentState?.status) { status in
            if status == .won || status == .lost {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                    showingResult = true
                }
            }
        }
    }
    
    // MARK: - Header
    
    private var headerView: some View {
        HStack {
            Button(action: { showingStats = true }) {
                Image(systemName: "chart.bar.fill")
                    .font(.system(size: 22))
                    .foregroundColor(.textSecondary)
            }
            
            Spacer()
            
            Text("Tracksy")
                .font(.gameTitle)
                .foregroundColor(.textPrimary)
            
            Spacer()
            
            Button(action: { showingHelp = true }) {
                Image(systemName: "questionmark.circle")
                    .font(.system(size: 22))
                    .foregroundColor(.textSecondary)
            }
        }
        .padding(.horizontal, 20)
        .padding(.top, 8)
    }
    
    // MARK: - Guess Counter
    
    private var guessCounterView: some View {
        HStack(spacing: 6) {
            ForEach(0..<10, id: \.self) { index in
                Circle()
                    .fill(guessIndicatorColor(for: index))
                    .frame(width: 10, height: 10)
            }
        }
    }
    
    private func guessIndicatorColor(for index: Int) -> Color {
        guard let state = gameManager.currentState else {
            return .cardBorder
        }
        
        let guessCount = state.guesses.count
        
        if index < guessCount {
            // Past guess
            if index == guessCount - 1 && state.status == .won {
                return .hintCorrect
            }
            return .textSecondary
        } else {
            // Future guess
            return .cardBorder
        }
    }
    
    // MARK: - Bottom Action
    
    private var bottomActionView: some View {
        VStack(spacing: 16) {
            if let state = gameManager.currentState {
                if state.isGameOver {
                    gameOverButton
                } else {
                    guessButton
                }
            } else {
                loadingView
            }
        }
        .padding(.horizontal, 20)
        .padding(.bottom, 24)
    }
    
    private var guessButton: some View {
        Button(action: { showingSearch = true }) {
            HStack {
                Image(systemName: "magnifyingglass")
                Text("Make a Guess")
                    .font(.buttonText)
            }
            .foregroundColor(.gameBackground)
            .frame(maxWidth: .infinity)
            .frame(height: 54)
            .background(Color.accentSpotify)
            .cornerRadius(27)
        }
    }
    
    private var gameOverButton: some View {
        Button(action: { showingResult = true }) {
            HStack {
                Image(systemName: gameManager.currentState?.status == .won ? "trophy.fill" : "eye.fill")
                Text(gameManager.currentState?.status == .won ? "View Results" : "See Answer")
                    .font(.buttonText)
            }
            .foregroundColor(.gameBackground)
            .frame(maxWidth: .infinity)
            .frame(height: 54)
            .background(gameManager.currentState?.status == .won ? Color.accentSpotify : Color.accentGold)
            .cornerRadius(27)
        }
    }
    
    private var loadingView: some View {
        ProgressView()
            .progressViewStyle(CircularProgressViewStyle(tint: .accentSpotify))
            .frame(height: 54)
    }
    
    // MARK: - Actions
    
    private func makeGuess(_ artist: Artist) {
        _ = gameManager.guess(artist)
    }
}

#Preview {
    GameView()
        .environmentObject(GameManager())
}
