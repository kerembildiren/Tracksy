import Foundation

/// Engine for comparing artists and generating hints
protocol HintEngineProtocol {
    func compare(guessed: Artist, correct: Artist) -> GuessHints
}

final class HintEngine: HintEngineProtocol {
    
    /// Thresholds for "close" hints
    struct Thresholds {
        static let debutYearClose = 10          // Within 10 years
        static let popularityCloseRanks = 15    // Within 15 ranks (popularity = 1..259)
    }
    
    /// Compares a guessed artist with the correct artist and returns hints
    func compare(guessed: Artist, correct: Artist) -> GuessHints {
        // If same artist, return all correct
        if guessed.id == correct.id {
            return .allCorrect
        }
        
        return GuessHints(
            debutYear: compareDebutYear(guessed: guessed.debutYear, correct: correct.debutYear),
            groupSize: compareGroupSize(guessed: guessed.groupSize, correct: correct.groupSize),
            gender: compareGender(guessed: guessed.gender, correct: correct.gender),
            genre: compareGenre(guessed: guessed.genre, correct: correct.genre),
            nationality: compareNationality(guessed: guessed.nationality, correct: correct.nationality),
            popularity: comparePopularity(guessed: guessed.popularity, correct: correct.popularity)
        )
    }
    
    // MARK: - Individual Comparisons
    
    /// Compares debut years with higher/lower and close hints
    private func compareDebutYear(guessed: Int?, correct: Int?) -> HintResult {
        guard let guessed = guessed, let correct = correct else {
            return .unknown
        }
        
        if guessed == correct {
            return .correct
        }
        
        let difference = abs(guessed - correct)
        let direction: HintResult.Direction = correct > guessed ? .higher : .lower
        
        if difference <= Thresholds.debutYearClose {
            return .close(direction: direction)
        }
        
        return correct > guessed ? .higher : .lower
    }
    
    /// Compares group size (exact match only)
    private func compareGroupSize(guessed: Artist.GroupSize?, correct: Artist.GroupSize?) -> HintResult {
        guard let guessed = guessed, let correct = correct else {
            return .unknown
        }
        
        return guessed == correct ? .correct : .incorrect
    }
    
    /// Compares gender (exact match only)
    private func compareGender(guessed: Artist.Gender?, correct: Artist.Gender?) -> HintResult {
        guard let guessed = guessed, let correct = correct else {
            return .unknown
        }
        
        return guessed == correct ? .correct : .incorrect
    }
    
    /// Compares genre (exact match only, case-insensitive)
    private func compareGenre(guessed: String?, correct: String?) -> HintResult {
        guard let guessed = guessed, let correct = correct else {
            return .unknown
        }
        
        return guessed.lowercased() == correct.lowercased() ? .correct : .incorrect
    }
    
    /// Compares nationality (exact match only, case-insensitive)
    private func compareNationality(guessed: String?, correct: String?) -> HintResult {
        guard let guessed = guessed, let correct = correct else {
            return .unknown
        }
        
        return guessed.lowercased() == correct.lowercased() ? .correct : .incorrect
    }
    
    /// Compares popularity (rank: 1 = most streams). Lower number = more popular. Close = within 15 ranks.
    private func comparePopularity(guessed: Int, correct: Int) -> HintResult {
        if guessed == correct {
            return .correct
        }
        
        let diff = abs(guessed - correct)
        // "higher" = correct is more popular = correct has lower rank number
        let direction: HintResult.Direction = correct < guessed ? .higher : .lower
        
        if diff <= Thresholds.popularityCloseRanks {
            return .close(direction: direction)
        }
        
        return correct < guessed ? .higher : .lower
    }
}
