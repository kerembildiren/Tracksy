import SwiftUI

struct GuessRowView: View {
    let guess: Guess
    
    var body: some View {
        VStack(spacing: 12) {
            // Artist row: image + name + check
            HStack(spacing: 12) {
                artistThumb
                Text(guess.artist.name)
                    .font(.artistName)
                    .foregroundColor(.textPrimary)
                Spacer()
                if guess.isCorrect {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.hintCorrect)
                        .font(.system(size: 20))
                }
            }
            
            // Attribute hints grid (3x2)
            LazyVGrid(columns: [
                GridItem(.flexible(), spacing: 8),
                GridItem(.flexible(), spacing: 8),
                GridItem(.flexible(), spacing: 8)
            ], spacing: 8) {
                AttributeCard(
                    label: "DEBUT",
                    value: formatYear(guess.artist.debutYear),
                    hint: guess.hints.debutYear
                )
                
                AttributeCard(
                    label: "TYPE",
                    value: guess.artist.groupSize?.rawValue ?? "?",
                    hint: guess.hints.groupSize
                )
                
                AttributeCard(
                    label: "GENDER",
                    value: formatGender(guess.artist.gender),
                    hint: guess.hints.gender
                )
                
                AttributeCard(
                    label: "GENRE",
                    value: guess.artist.genre ?? "?",
                    hint: guess.hints.genre
                )
                
                AttributeCard(
                    label: "NATION",
                    value: formatNationality(guess.artist.nationality),
                    hint: guess.hints.nationality
                )
                
                AttributeCard(
                    label: "POPULARITY",
                    value: formatPopularity(guess.artist.popularity),
                    hint: guess.hints.popularity
                )
            }
        }
        .padding(16)
        .cardStyle()
    }
    
    @ViewBuilder
    private var artistThumb: some View {
        Group {
            if let urlString = guess.artist.imageUrl, let url = URL(string: urlString) {
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .success(let image):
                        image.resizable().scaledToFill()
                    case .failure(_), .empty:
                        placeholderView
                    @unknown default:
                        placeholderView
                    }
                }
            } else {
                placeholderView
            }
        }
        .frame(width: 48, height: 48)
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .background(Color.cardBorder)
    }
    
    private var placeholderView: some View {
        Text(String((guess.artist.name).prefix(1)).uppercased())
            .font(.system(size: 20, weight: .bold))
            .foregroundColor(.textSecondary)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
    
    // MARK: - Formatting Helpers
    
    private func formatYear(_ year: Int?) -> String {
        guard let year = year else { return "?" }
        return String(year)
    }
    
    private func formatGender(_ gender: Artist.Gender?) -> String {
        guard let gender = gender else { return "?" }
        switch gender {
        case .male: return "M"
        case .female: return "F"
        case .mixed: return "Mix"
        }
    }
    
    private func formatNationality(_ nationality: String?) -> String {
        guard let nat = nationality else { return "?" }
        // Show first 3 characters or flag emoji
        if nat.lowercased() == "turkish" {
            return "TR"
        }
        return String(nat.prefix(3)).uppercased()
    }
    
    private func formatPopularity(_ rank: Int) -> String {
        return "#\(rank)"
    }
}

// MARK: - Attribute Card

struct AttributeCard: View {
    let label: String
    let value: String
    let hint: HintResult
    
    var body: some View {
        VStack(spacing: 4) {
            Text(label)
                .font(.attributeLabel)
                .foregroundColor(.textMuted)
            
            ZStack {
                RoundedRectangle(cornerRadius: 8)
                    .fill(hint.backgroundColor)
                    .frame(height: 36)
                
                HStack(spacing: 4) {
                    Text(value)
                        .font(.attributeValue)
                        .foregroundColor(.white)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                    
                    if let arrow = hint.arrowIcon {
                        Image(systemName: arrow)
                            .font(.system(size: 10, weight: .bold))
                            .foregroundColor(.white)
                    }
                }
                .padding(.horizontal, 6)
            }
        }
    }
}

#Preview {
    ZStack {
        Color.gameBackground
            .ignoresSafeArea()
        
        VStack(spacing: 16) {
            GuessRowView(guess: Guess(
                artist: Artist(
                    id: "1",
                    name: "Tarkan",
                    nationality: "Turkish",
                    popularity: 4,
                    imageUrl: nil,
                    debutYear: 1992,
                    groupSize: .solo,
                    gender: .male,
                    genre: "Pop"
                ),
                hints: GuessHints(
                    debutYear: .close(direction: .higher),
                    groupSize: .correct,
                    gender: .correct,
                    genre: .incorrect,
                    nationality: .correct,
                    popularity: .higher
                )
            ))
            
            GuessRowView(guess: Guess(
                artist: Artist(
                    id: "2",
                    name: "Sezen Aksu",
                    nationality: "Turkish",
                    popularity: 5,
                    imageUrl: nil,
                    debutYear: 1975,
                    groupSize: .solo,
                    gender: .female,
                    genre: "Pop"
                ),
                hints: .allCorrect
            ))
        }
        .padding()
    }
}
