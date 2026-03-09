import SwiftUI

// MARK: - Color Theme

extension Color {
    // Main background
    static let gameBackground = Color(hex: "121212")
    static let cardBackground = Color(hex: "1E1E1E")
    static let cardBorder = Color(hex: "333333")
    
    // Hint colors
    static let hintCorrect = Color(hex: "22C55E")      // Green
    static let hintClose = Color(hex: "EAB308")        // Yellow/Gold
    static let hintWrong = Color(hex: "6B7280")        // Gray
    static let hintUnknown = Color(hex: "4B5563")      // Dark gray
    
    // Arrows
    static let arrowHigher = Color(hex: "EF4444")      // Red (need to go up)
    static let arrowLower = Color(hex: "3B82F6")       // Blue (need to go down)
    
    // Text
    static let textPrimary = Color.white
    static let textSecondary = Color(hex: "9CA3AF")
    static let textMuted = Color(hex: "6B7280")
    
    // Accent
    static let accentSpotify = Color(hex: "1DB954")
    static let accentGold = Color(hex: "F59E0B")
}

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3:
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6:
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8:
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}

// MARK: - Typography

extension Font {
    static let gameTitle = Font.system(size: 28, weight: .bold)
    static let guessCounter = Font.system(size: 16, weight: .semibold)
    static let artistName = Font.system(size: 18, weight: .bold)
    static let attributeLabel = Font.system(size: 11, weight: .medium)
    static let attributeValue = Font.system(size: 13, weight: .bold)
    static let searchInput = Font.system(size: 17)
    static let searchResult = Font.system(size: 16)
    static let buttonText = Font.system(size: 16, weight: .semibold)
}

// MARK: - View Modifiers

struct CardStyle: ViewModifier {
    var backgroundColor: Color = .cardBackground
    
    func body(content: Content) -> some View {
        content
            .background(backgroundColor)
            .cornerRadius(12)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.cardBorder, lineWidth: 1)
            )
    }
}

extension View {
    func cardStyle(backgroundColor: Color = .cardBackground) -> some View {
        modifier(CardStyle(backgroundColor: backgroundColor))
    }
}

// MARK: - Hint Color Mapping

extension HintResult {
    var backgroundColor: Color {
        switch self {
        case .correct:
            return .hintCorrect
        case .incorrect:
            return .hintWrong
        case .higher, .lower:
            return .hintWrong
        case .close:
            return .hintClose
        case .unknown:
            return .hintUnknown
        }
    }
    
    var arrowIcon: String? {
        switch self {
        case .higher:
            return "arrow.up"
        case .lower:
            return "arrow.down"
        case .close(let direction):
            switch direction {
            case .higher: return "arrow.up"
            case .lower: return "arrow.down"
            case .none: return nil
            }
        default:
            return nil
        }
    }
    
    var arrowColor: Color {
        switch self {
        case .higher, .close(direction: .higher):
            return .arrowHigher
        case .lower, .close(direction: .lower):
            return .arrowLower
        default:
            return .clear
        }
    }
}
