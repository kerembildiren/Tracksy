import Foundation

/// Result of comparing a guessed attribute with the correct answer
enum HintResult: Equatable {
    case correct                    // Exact match
    case incorrect                  // No match, no direction hint
    case higher                     // Correct value is higher
    case lower                      // Correct value is lower
    case close(direction: Direction) // Within threshold, with direction
    case unknown                    // Data not available for comparison
    
    enum Direction: String {
        case higher = "higher"
        case lower = "lower"
        case none = "none"
    }
    
    var isCorrect: Bool {
        self == .correct
    }
    
    var isClose: Bool {
        if case .close = self { return true }
        return false
    }
}

/// All hints for a single guess
struct GuessHints: Equatable {
    let debutYear: HintResult
    let groupSize: HintResult
    let gender: HintResult
    let genre: HintResult
    let nationality: HintResult
    let popularity: HintResult
    
    /// Returns true if all available hints are correct (artist found)
    var isAllCorrect: Bool {
        debutYear.isCorrect &&
        groupSize.isCorrect &&
        gender.isCorrect &&
        genre.isCorrect &&
        nationality.isCorrect &&
        popularity.isCorrect
    }
    
    /// Creates hints when correct artist is guessed
    static var allCorrect: GuessHints {
        GuessHints(
            debutYear: .correct,
            groupSize: .correct,
            gender: .correct,
            genre: .correct,
            nationality: .correct,
            popularity: .correct
        )
    }
}
