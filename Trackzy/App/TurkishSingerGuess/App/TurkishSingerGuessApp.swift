import SwiftUI

@main
struct TurkishSingerGuessApp: App {
    
    @StateObject private var gameManager = GameManager()
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(gameManager)
        }
    }
}

/// Main content view - shows Home menu first, then Game when user taps Play
struct ContentView: View {
    @EnvironmentObject var gameManager: GameManager
    @State private var showingGame = false
    @State private var showingHelp = false
    @State private var showingStats = false
    
    var body: some View {
        Group {
            if showingGame {
                GameView()
            } else {
                HomeView(
                    onPlay: {
                        await gameManager.initialize()
                        showingGame = true
                    },
                    onHowToPlay: { showingHelp = true },
                    onStats: { showingStats = true }
                )
            }
        }
        .sheet(isPresented: $showingHelp) {
            HelpView()
        }
        .sheet(isPresented: $showingStats) {
            StatsView()
                .environmentObject(gameManager)
        }
    }
}

// MARK: - Game Manager (Dependency Container)

/// Observable object that manages all game dependencies
final class GameManager: ObservableObject {
    
    let dataService: ArtistDataService
    let searchService: SearchService
    let dailyArtistService: DailyArtistService
    let hintEngine: HintEngine
    let persistence: GamePersistence
    let gameEngine: GameEngine
    
    @Published var isLoaded = false
    @Published var loadError: Error?
    
    init() {
        // Initialize services
        self.dataService = ArtistDataService()
        self.searchService = SearchService(dataService: dataService)
        self.dailyArtistService = DailyArtistService(dataService: dataService)
        self.hintEngine = HintEngine()
        self.persistence = GamePersistence()
        self.gameEngine = GameEngine(
            dataService: dataService,
            dailyArtistService: dailyArtistService,
            hintEngine: hintEngine,
            persistence: persistence
        )
    }
    
    /// Loads all required data and starts the game
    func initialize() async {
        do {
            try dataService.loadArtists()
            try gameEngine.startNewGame()
            
            await MainActor.run {
                isLoaded = true
            }
        } catch {
            await MainActor.run {
                loadError = error
            }
        }
    }
    
    /// Searches for artists by name
    func searchArtists(query: String) -> [Artist] {
        searchService.searchWithTurkishSupport(query: query)
    }
    
    /// Makes a guess
    func guess(_ artist: Artist) -> GuessResult {
        gameEngine.makeGuess(artist)
    }
    
    /// Returns current game state
    var currentState: GameState? {
        gameEngine.currentState
    }
    
    /// Returns the correct artist (for display after game over)
    var correctArtist: Artist? {
        gameEngine.correctArtist
    }
}
