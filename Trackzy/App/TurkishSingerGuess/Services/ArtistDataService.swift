import Foundation

/// Service responsible for loading and providing artist data
protocol ArtistDataServiceProtocol {
    var artists: [Artist] { get }
    func loadArtists() throws
    func artist(byId id: String) -> Artist?
    func artist(byName name: String) -> Artist?
}

final class ArtistDataService: ArtistDataServiceProtocol {
    
    private(set) var artists: [Artist] = []
    private var artistsById: [String: Artist] = [:]
    private var artistsByName: [String: Artist] = [:]
    
    enum DataError: Error, LocalizedError {
        case fileNotFound
        case parsingFailed(Error)
        case emptyDataset
        
        var errorDescription: String? {
            switch self {
            case .fileNotFound:
                return "Artists data file not found in bundle"
            case .parsingFailed(let error):
                return "Failed to parse artists data: \(error.localizedDescription)"
            case .emptyDataset:
                return "No artists found in dataset"
            }
        }
    }
    
    /// Loads artists from the bundled JSON file
    func loadArtists() throws {
        guard let url = Bundle.main.url(forResource: "artists", withExtension: "json") else {
            throw DataError.fileNotFound
        }
        
        do {
            let data = try Data(contentsOf: url)
            let rawArtists = try JSONDecoder().decode([RawArtist].self, from: data)
            
            guard !rawArtists.isEmpty else {
                throw DataError.emptyDataset
            }
            
            self.artists = rawArtists.map { $0.toArtist() }
            buildIndexes()
            
        } catch let error as DataError {
            throw error
        } catch {
            throw DataError.parsingFailed(error)
        }
    }
    
    /// Loads artists from raw JSON data (useful for testing)
    func loadArtists(from data: Data) throws {
        do {
            let rawArtists = try JSONDecoder().decode([RawArtist].self, from: data)
            
            guard !rawArtists.isEmpty else {
                throw DataError.emptyDataset
            }
            
            self.artists = rawArtists.map { $0.toArtist() }
            buildIndexes()
            
        } catch let error as DataError {
            throw error
        } catch {
            throw DataError.parsingFailed(error)
        }
    }
    
    func artist(byId id: String) -> Artist? {
        artistsById[id]
    }
    
    func artist(byName name: String) -> Artist? {
        artistsByName[name.lowercased()]
    }
    
    private func buildIndexes() {
        artistsById = Dictionary(uniqueKeysWithValues: artists.map { ($0.id, $0) })
        artistsByName = Dictionary(uniqueKeysWithValues: artists.map { ($0.name.lowercased(), $0) })
    }
}
