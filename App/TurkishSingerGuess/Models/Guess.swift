import Foundation

/// Represents a single guess made by the player
struct Guess: Identifiable, Equatable {
    let id: UUID
    let artist: Artist
    let hints: GuessHints
    let timestamp: Date
    
    init(artist: Artist, hints: GuessHints, timestamp: Date = Date()) {
        self.id = UUID()
        self.artist = artist
        self.hints = hints
        self.timestamp = timestamp
    }
    
    /// Returns true if this guess was the correct artist
    var isCorrect: Bool {
        hints.isAllCorrect
    }
}
