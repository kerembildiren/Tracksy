import Foundation

/// Core game engine that orchestrates gameplay
protocol GameEngineProtocol {
    var currentState: GameState? { get }
    var correctArtist: Artist? { get }
    
    func startNewGame() throws
    func makeGuess(_ artist: Artist) -> GuessResult
    func canGuess(_ artist: Artist) -> Bool
}

/// Result of making a guess
enum GuessResult {
    case success(Guess)
    case alreadyGuessed
    case gameOver
    case invalidArtist
}

final class GameEngine: GameEngineProtocol {
    
    private let dataService: ArtistDataServiceProtocol
    private let dailyArtistService: DailyArtistServiceProtocol
    private let hintEngine: HintEngineProtocol
    private let persistence: GamePersistenceProtocol
    
    private(set) var currentState: GameState?
    private(set) var correctArtist: Artist?
    private var statistics: GameStatistics
    
    init(
        dataService: ArtistDataServiceProtocol,
        dailyArtistService: DailyArtistServiceProtocol,
        hintEngine: HintEngineProtocol,
        persistence: GamePersistenceProtocol
    ) {
        self.dataService = dataService
        self.dailyArtistService = dailyArtistService
        self.hintEngine = hintEngine
        self.persistence = persistence
        self.statistics = persistence.loadStatistics() ?? GameStatistics()
    }
    
    /// Starts or resumes today's game
    func startNewGame() throws {
        let todayString = (dailyArtistService as? DailyArtistService)?.getTodaysDateString() 
            ?? dailyArtistService.getDateString(for: Date())
        
        // Try to resume existing game for today
        if let savedState = persistence.loadGameState(),
           savedState.dateString == todayString {
            self.currentState = savedState
            self.correctArtist = dataService.artist(byId: savedState.correctArtistId)
            return
        }
        
        // Start new game
        guard let artist = dailyArtistService.getTodaysArtist() else {
            throw GameEngineError.noArtistAvailable
        }
        
        self.correctArtist = artist
        self.currentState = GameState(dateString: todayString, correctArtistId: artist.id)
        saveState()
    }
    
    /// Makes a guess and returns the result with hints
    func makeGuess(_ artist: Artist) -> GuessResult {
        guard var state = currentState, let correct = correctArtist else {
            return .invalidArtist
        }
        
        guard !state.isGameOver else {
            return .gameOver
        }
        
        guard canGuess(artist) else {
            return .alreadyGuessed
        }
        
        let hints = hintEngine.compare(guessed: artist, correct: correct)
        let guess = Guess(artist: artist, hints: hints)
        let record = GuessRecord(from: guess)
        
        state.guesses.append(record)
        
        // Update game status
        if guess.isCorrect {
            state.status = .won
            statistics.recordWin(guessCount: state.guesses.count, dateString: state.dateString)
        } else if state.remainingGuesses == 0 {
            state.status = .lost
            statistics.recordLoss(dateString: state.dateString)
        }
        
        self.currentState = state
        saveState()
        saveStatistics()
        
        return .success(guess)
    }
    
    /// Checks if an artist can be guessed (not already guessed)
    func canGuess(_ artist: Artist) -> Bool {
        guard let state = currentState else { return false }
        return !state.guesses.contains { $0.artistId == artist.id }
    }
    
    /// Returns all guesses as full Guess objects with hints
    func getGuessesWithHints() -> [Guess] {
        guard let state = currentState, let correct = correctArtist else {
            return []
        }
        
        return state.guesses.compactMap { record in
            guard let artist = dataService.artist(byId: record.artistId) else {
                return nil
            }
            let hints = hintEngine.compare(guessed: artist, correct: correct)
            return Guess(artist: artist, hints: hints, timestamp: record.timestamp)
        }
    }
    
    /// Returns current statistics
    func getStatistics() -> GameStatistics {
        statistics
    }
    
    // MARK: - Private
    
    private func saveState() {
        guard let state = currentState else { return }
        persistence.saveGameState(state)
    }
    
    private func saveStatistics() {
        persistence.saveStatistics(statistics)
    }
}

enum GameEngineError: Error, LocalizedError {
    case noArtistAvailable
    case gameNotStarted
    
    var errorDescription: String? {
        switch self {
        case .noArtistAvailable:
            return "No artist available for today's game"
        case .gameNotStarted:
            return "Game has not been started"
        }
    }
}
