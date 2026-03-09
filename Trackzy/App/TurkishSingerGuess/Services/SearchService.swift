import Foundation

/// Service for autocomplete search functionality
protocol SearchServiceProtocol {
    func search(query: String, limit: Int) -> [Artist]
}

final class SearchService: SearchServiceProtocol {
    
    private let dataService: ArtistDataServiceProtocol
    
    init(dataService: ArtistDataServiceProtocol) {
        self.dataService = dataService
    }
    
    /// Searches artists by name with autocomplete-style matching
    /// - Parameters:
    ///   - query: The search query (case-insensitive)
    ///   - limit: Maximum number of results to return
    /// - Returns: Array of matching artists, sorted by relevance
    func search(query: String, limit: Int = 10) -> [Artist] {
        let trimmedQuery = query.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        
        guard !trimmedQuery.isEmpty else {
            return []
        }
        
        let results = dataService.artists.filter { artist in
            let artistName = artist.name.lowercased()
            return artistName.contains(trimmedQuery)
        }
        
        // Sort by relevance:
        // 1. Exact matches first
        // 2. Prefix matches second
        // 3. Contains matches third
        // Within each group, sort by popularity
        let sorted = results.sorted { a, b in
            let aName = a.name.lowercased()
            let bName = b.name.lowercased()
            
            let aExact = aName == trimmedQuery
            let bExact = bName == trimmedQuery
            if aExact != bExact { return aExact }
            
            let aPrefix = aName.hasPrefix(trimmedQuery)
            let bPrefix = bName.hasPrefix(trimmedQuery)
            if aPrefix != bPrefix { return aPrefix }
            
            // Higher popularity = lower number = better rank
            return a.popularity < b.popularity
        }
        
        return Array(sorted.prefix(limit))
    }
    
    /// Searches with Turkish character support
    /// Handles common Turkish character variations (ı/i, ö/o, ü/u, ş/s, ç/c, ğ/g)
    func searchWithTurkishSupport(query: String, limit: Int = 10) -> [Artist] {
        let trimmedQuery = query.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        
        guard !trimmedQuery.isEmpty else {
            return []
        }
        
        let normalizedQuery = normalizeTurkish(trimmedQuery)
        
        let results = dataService.artists.filter { artist in
            let normalizedName = normalizeTurkish(artist.name.lowercased())
            return normalizedName.contains(normalizedQuery)
        }
        
        let sorted = results.sorted { a, b in
            let aName = normalizeTurkish(a.name.lowercased())
            let bName = normalizeTurkish(b.name.lowercased())
            
            let aExact = aName == normalizedQuery
            let bExact = bName == normalizedQuery
            if aExact != bExact { return aExact }
            
            let aPrefix = aName.hasPrefix(normalizedQuery)
            let bPrefix = bName.hasPrefix(normalizedQuery)
            if aPrefix != bPrefix { return aPrefix }
            
            return a.popularity < b.popularity
        }
        
        return Array(sorted.prefix(limit))
    }
    
    /// Normalizes Turkish characters to their ASCII equivalents
    private func normalizeTurkish(_ text: String) -> String {
        let replacements: [Character: Character] = [
            "ı": "i", "İ": "i",
            "ö": "o", "Ö": "o",
            "ü": "u", "Ü": "u",
            "ş": "s", "Ş": "s",
            "ç": "c", "Ç": "c",
            "ğ": "g", "Ğ": "g"
        ]
        
        return String(text.map { replacements[$0] ?? $0 })
    }
}
