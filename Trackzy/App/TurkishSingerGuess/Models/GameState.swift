import Foundation

/// Current state of the daily game
struct GameState: Codable, Equatable {
    let dateString: String          // YYYY-MM-DD format for the puzzle day
    let correctArtistId: String
    var guesses: [GuessRecord]
    var status: GameStatus
    
    static let maxGuesses = 10
    
    var remainingGuesses: Int {
        Self.maxGuesses - guesses.count
    }
    
    var isGameOver: Bool {
        status != .inProgress
    }
    
    init(dateString: String, correctArtistId: String) {
        self.dateString = dateString
        self.correctArtistId = correctArtistId
        self.guesses = []
        self.status = .inProgress
    }
}

/// Lightweight record of a guess for persistence
struct GuessRecord: Codable, Equatable, Identifiable {
    let id: UUID
    let artistId: String
    let artistName: String
    let isCorrect: Bool
    let timestamp: Date
    
    init(from guess: Guess) {
        self.id = guess.id
        self.artistId = guess.artist.id
        self.artistName = guess.artist.name
        self.isCorrect = guess.isCorrect
        self.timestamp = guess.timestamp
    }
}

/// Status of the current game
enum GameStatus: String, Codable, Equatable {
    case inProgress = "in_progress"
    case won = "won"
    case lost = "lost"
}

/// Statistics tracked across all games
struct GameStatistics: Codable, Equatable {
    var gamesPlayed: Int = 0
    var gamesWon: Int = 0
    var currentStreak: Int = 0
    var maxStreak: Int = 0
    var guessDistribution: [Int: Int] = [:]  // guess count -> number of wins
    var lastPlayedDate: String?
    
    var winPercentage: Double {
        guard gamesPlayed > 0 else { return 0 }
        return Double(gamesWon) / Double(gamesPlayed) * 100
    }
    
    mutating func recordWin(guessCount: Int, dateString: String) {
        gamesPlayed += 1
        gamesWon += 1
        guessDistribution[guessCount, default: 0] += 1
        
        if lastPlayedDate == previousDay(of: dateString) {
            currentStreak += 1
        } else {
            currentStreak = 1
        }
        maxStreak = max(maxStreak, currentStreak)
        lastPlayedDate = dateString
    }
    
    mutating func recordLoss(dateString: String) {
        gamesPlayed += 1
        currentStreak = 0
        lastPlayedDate = dateString
    }
    
    private func previousDay(of dateString: String) -> String? {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        guard let date = formatter.date(from: dateString),
              let previous = Calendar.current.date(byAdding: .day, value: -1, to: date) else {
            return nil
        }
        return formatter.string(from: previous)
    }
}
