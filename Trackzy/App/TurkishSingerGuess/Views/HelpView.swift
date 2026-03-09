import SwiftUI

struct HelpView: View {
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        NavigationView {
            ZStack {
                Color.gameBackground
                    .ignoresSafeArea()
                
                ScrollView {
                    VStack(alignment: .leading, spacing: 24) {
                        // How to play
                        howToPlaySection
                        
                        // Hint colors
                        hintColorsSection
                        
                        // Attributes
                        attributesSection
                    }
                    .padding(20)
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                    .foregroundColor(.accentSpotify)
                }
                
                ToolbarItem(placement: .principal) {
                    Text("How to Play")
                        .font(.system(size: 17, weight: .semibold))
                        .foregroundColor(.textPrimary)
                }
            }
            .toolbarBackground(Color.gameBackground, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
        .preferredColorScheme(.dark)
    }
    
    // MARK: - How to Play
    
    private var howToPlaySection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("How to Play")
            
            VStack(alignment: .leading, spacing: 8) {
                ruleRow(number: 1, text: "Guess the Turkish singer of the day")
                ruleRow(number: 2, text: "You have 10 attempts to find the correct artist")
                ruleRow(number: 3, text: "After each guess, hints will show how close you are")
                ruleRow(number: 4, text: "Use the hints to narrow down your next guess")
                ruleRow(number: 5, text: "Everyone gets the same artist each day")
            }
        }
        .padding(16)
        .cardStyle()
    }
    
    private func ruleRow(number: Int, text: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Text("\(number)")
                .font(.system(size: 14, weight: .bold))
                .foregroundColor(.accentSpotify)
                .frame(width: 24, height: 24)
                .background(Color.accentSpotify.opacity(0.2))
                .cornerRadius(12)
            
            Text(text)
                .font(.system(size: 15))
                .foregroundColor(.textPrimary)
        }
    }
    
    // MARK: - Hint Colors
    
    private var hintColorsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("Hint Colors")
            
            VStack(spacing: 8) {
                hintColorRow(color: .hintCorrect, label: "Correct", description: "Exact match!")
                hintColorRow(color: .hintClose, label: "Close", description: "Very close to the answer")
                hintColorRow(color: .hintWrong, label: "Wrong", description: "Not a match")
                hintColorRow(color: .hintUnknown, label: "Unknown", description: "Data not available")
            }
        }
        .padding(16)
        .cardStyle()
    }
    
    private func hintColorRow(color: Color, label: String, description: String) -> some View {
        HStack(spacing: 12) {
            RoundedRectangle(cornerRadius: 6)
                .fill(color)
                .frame(width: 40, height: 28)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(.textPrimary)
                
                Text(description)
                    .font(.system(size: 13))
                    .foregroundColor(.textSecondary)
            }
            
            Spacer()
        }
    }
    
    // MARK: - Attributes
    
    private var attributesSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("Attributes Compared")
            
            VStack(spacing: 8) {
                attributeRow(icon: "calendar", name: "Debut Year", hint: "Shows higher/lower arrows")
                attributeRow(icon: "person.2.fill", name: "Type", hint: "Solo, Duo, or Group")
                attributeRow(icon: "person.fill", name: "Gender", hint: "Male, Female, or Mixed")
                attributeRow(icon: "music.note", name: "Genre", hint: "Pop, Rock, etc.")
                attributeRow(icon: "globe", name: "Nationality", hint: "Artist's country")
                attributeRow(icon: "headphones", name: "Listeners", hint: "Monthly listener count")
            }
        }
        .padding(16)
        .cardStyle()
    }
    
    private func attributeRow(icon: String, name: String, hint: String) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 16))
                .foregroundColor(.accentSpotify)
                .frame(width: 28)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(name)
                    .font(.system(size: 15, weight: .medium))
                    .foregroundColor(.textPrimary)
                
                Text(hint)
                    .font(.system(size: 13))
                    .foregroundColor(.textSecondary)
            }
            
            Spacer()
        }
    }
    
    // MARK: - Helpers
    
    private func sectionTitle(_ title: String) -> some View {
        Text(title)
            .font(.system(size: 18, weight: .bold))
            .foregroundColor(.textPrimary)
    }
}

#Preview {
    HelpView()
}
