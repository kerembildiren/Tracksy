import Foundation

/// Service for deterministic daily artist selection
protocol DailyArtistServiceProtocol {
    func getDailyArtist(for date: Date) -> Artist?
    func getTodaysArtist() -> Artist?
    func getDateString(for date: Date) -> String
}

final class DailyArtistService: DailyArtistServiceProtocol {
    
    private let dataService: ArtistDataServiceProtocol
    private let calendar: Calendar
    
    /// A fixed seed date for consistent artist rotation
    /// All daily artist calculations are relative to this epoch
    private static let epochDate: Date = {
        var components = DateComponents()
        components.year = 2025
        components.month = 1
        components.day = 1
        return Calendar(identifier: .gregorian).date(from: components)!
    }()
    
    init(dataService: ArtistDataServiceProtocol, calendar: Calendar = .current) {
        self.dataService = dataService
        self.calendar = calendar
    }
    
    /// Returns the artist for a specific date
    /// Uses deterministic selection based on days since epoch
    func getDailyArtist(for date: Date) -> Artist? {
        let artists = dataService.artists
        guard !artists.isEmpty else { return nil }
        
        let daysSinceEpoch = daysBetween(from: Self.epochDate, to: date)
        let index = deterministicIndex(day: daysSinceEpoch, artistCount: artists.count)
        
        return artists[index]
    }
    
    /// Returns today's artist
    func getTodaysArtist() -> Artist? {
        getDailyArtist(for: Date())
    }
    
    /// Returns a date string in YYYY-MM-DD format
    func getDateString(for date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.timeZone = TimeZone(identifier: "Europe/Istanbul") // Turkish timezone
        return formatter.string(from: date)
    }
    
    /// Returns today's date string
    func getTodaysDateString() -> String {
        getDateString(for: Date())
    }
    
    /// Calculates days between two dates (ignoring time)
    private func daysBetween(from startDate: Date, to endDate: Date) -> Int {
        let start = calendar.startOfDay(for: startDate)
        let end = calendar.startOfDay(for: endDate)
        let components = calendar.dateComponents([.day], from: start, to: end)
        return components.day ?? 0
    }
    
    /// Generates a deterministic index using a seeded random approach
    /// This ensures the same day always produces the same artist,
    /// but the sequence appears random and doesn't repeat predictably
    private func deterministicIndex(day: Int, artistCount: Int) -> Int {
        // Use a simple but effective hash-like approach
        // Combines the day number with a large prime to create pseudo-random distribution
        let seed = UInt64(abs(day))
        let hash = seed &* 6364136223846793005 &+ 1442695040888963407
        return Int(hash % UInt64(artistCount))
    }
}
