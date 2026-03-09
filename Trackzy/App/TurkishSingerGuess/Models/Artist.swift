import Foundation

/// Represents a Turkish singer/artist in the game
struct Artist: Codable, Identifiable, Equatable {
    let id: String
    let name: String
    let nationality: String?
    let popularity: Int  // Rank 1 = most streams, higher = less popular
    let imageUrl: String?
    let topTrackId: String?
    let topTrackName: String?
    let topTrackUri: String?
    
    let debutYear: Int?
    let groupSize: GroupSize?
    let gender: Gender?
    let genre: String?
    
    enum GroupSize: String, Codable, CaseIterable {
        case solo = "Solo"
        case group = "Group"
    }
    
    enum Gender: String, Codable, CaseIterable {
        case male = "Male"
        case female = "Female"
        case mixed = "Mixed"
    }
    
    enum CodingKeys: String, CodingKey {
        case id
        case name
        case nationality
        case popularity
        case imageUrl = "image_url"
        case topTrackId = "top_track_id"
        case topTrackName = "top_track_name"
        case topTrackUri = "top_track_uri"
        case debutYear = "debut"
        case groupSize = "group_size"
        case gender
        case genre
    }
    
    init(id: String, name: String, nationality: String?, popularity: Int, imageUrl: String? = nil,
         topTrackId: String? = nil, topTrackName: String? = nil, topTrackUri: String? = nil,
         debutYear: Int?, groupSize: GroupSize?, gender: Gender?, genre: String?) {
        self.id = id
        self.name = name
        self.nationality = nationality
        self.popularity = popularity
        self.imageUrl = imageUrl
        self.topTrackId = topTrackId
        self.topTrackName = topTrackName
        self.topTrackUri = topTrackUri
        self.debutYear = debutYear
        self.groupSize = groupSize
        self.gender = gender
        self.genre = genre
    }
}

// MARK: - Raw JSON Parsing (matches artists_raw.json from DataCollection/output)

struct RawArtist: Codable {
    let id: String
    let name: String
    let genres: [String]?
    let popularity: Int
    let debut: Int?
    let nationality: String?
    let groupSize: GroupSizeValue?
    let gender: String?
    let spotifyMonthlyStreams: Int?
    let imageUrl: String?
    let topTrackId: String?
    let topTrackName: String?
    let topTrackUri: String?

    enum CodingKeys: String, CodingKey {
        case id, name, genres, popularity, debut, nationality, gender
        case groupSize = "group_size"
        case spotifyMonthlyStreams = "spotify_monthly_streams"
        case imageUrl = "image_url"
        case topTrackId = "top_track_id"
        case topTrackName = "top_track_name"
        case topTrackUri = "top_track_uri"
    }
    
    /// group_size in JSON can be 1 (solo) or "group"
    enum GroupSizeValue: Codable {
        case int(Int)
        case string(String)
        
        init(from decoder: Decoder) throws {
            let c = try decoder.singleValueContainer()
            if let i = try? c.decode(Int.self) {
                self = .int(i)
            } else if let s = try? c.decode(String.self) {
                self = .string(s)
            } else {
                self = .int(1)
            }
        }
        
        func encode(to encoder: Encoder) throws {
            var c = encoder.singleValueContainer()
            switch self {
            case .int(let i): try c.encode(i)
            case .string(let s): try c.encode(s)
            }
        }
        
        var toGroupSize: Artist.GroupSize? {
            switch self {
            case .int(1): return .solo
            case .int: return .group
            case .string("group"): return .group
            case .string: return .solo
            }
        }
    }
    
    func toArtist() -> Artist {
        let gs: Artist.GroupSize? = groupSize?.toGroupSize
        let genderEnum: Artist.Gender? = {
            guard let g = gender else { return nil }
            switch g.lowercased() {
            case "male": return .male
            case "female": return .female
            case "mixed": return .mixed
            default: return nil
            }
        }()
        return Artist(
            id: id,
            name: name,
            nationality: nationality,
            popularity: popularity,
            imageUrl: imageUrl,
            topTrackId: topTrackId,
            topTrackName: topTrackName,
            topTrackUri: topTrackUri,
            debutYear: debut,
            groupSize: gs,
            gender: genderEnum,
            genre: genres?.first
        )
    }
}
