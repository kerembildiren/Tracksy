import Foundation

/// Protocol for game state persistence
protocol GamePersistenceProtocol {
    func saveGameState(_ state: GameState)
    func loadGameState() -> GameState?
    func clearGameState()
    
    func saveStatistics(_ stats: GameStatistics)
    func loadStatistics() -> GameStatistics?
}

/// UserDefaults-based persistence for game state
final class GamePersistence: GamePersistenceProtocol {
    
    private enum Keys {
        static let gameState = "com.turkishsingerguess.gameState"
        static let statistics = "com.turkishsingerguess.statistics"
    }
    
    private let defaults: UserDefaults
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder
    
    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        self.encoder = JSONEncoder()
        self.decoder = JSONDecoder()
    }
    
    // MARK: - Game State
    
    func saveGameState(_ state: GameState) {
        do {
            let data = try encoder.encode(state)
            defaults.set(data, forKey: Keys.gameState)
        } catch {
            print("Failed to save game state: \(error)")
        }
    }
    
    func loadGameState() -> GameState? {
        guard let data = defaults.data(forKey: Keys.gameState) else {
            return nil
        }
        
        do {
            return try decoder.decode(GameState.self, from: data)
        } catch {
            print("Failed to load game state: \(error)")
            return nil
        }
    }
    
    func clearGameState() {
        defaults.removeObject(forKey: Keys.gameState)
    }
    
    // MARK: - Statistics
    
    func saveStatistics(_ stats: GameStatistics) {
        do {
            let data = try encoder.encode(stats)
            defaults.set(data, forKey: Keys.statistics)
        } catch {
            print("Failed to save statistics: \(error)")
        }
    }
    
    func loadStatistics() -> GameStatistics? {
        guard let data = defaults.data(forKey: Keys.statistics) else {
            return nil
        }
        
        do {
            return try decoder.decode(GameStatistics.self, from: data)
        } catch {
            print("Failed to load statistics: \(error)")
            return nil
        }
    }
}

// MARK: - In-Memory Persistence (for testing)

final class InMemoryGamePersistence: GamePersistenceProtocol {
    
    private var gameState: GameState?
    private var statistics: GameStatistics?
    
    func saveGameState(_ state: GameState) {
        gameState = state
    }
    
    func loadGameState() -> GameState? {
        gameState
    }
    
    func clearGameState() {
        gameState = nil
    }
    
    func saveStatistics(_ stats: GameStatistics) {
        statistics = stats
    }
    
    func loadStatistics() -> GameStatistics? {
        statistics
    }
}
