import SwiftUI

struct SearchView: View {
    @EnvironmentObject var gameManager: GameManager
    @Environment(\.dismiss) var dismiss
    
    @State private var searchText = ""
    @FocusState private var isSearchFocused: Bool
    
    let onSelect: (Artist) -> Void
    
    var searchResults: [Artist] {
        gameManager.searchArtists(query: searchText)
    }
    
    var body: some View {
        NavigationView {
            ZStack {
                Color.gameBackground
                    .ignoresSafeArea()
                
                VStack(spacing: 0) {
                    // Search input
                    searchInputView
                        .padding(.horizontal, 16)
                        .padding(.top, 16)
                    
                    // Results
                    if searchText.isEmpty {
                        emptyStateView
                    } else if searchResults.isEmpty {
                        noResultsView
                    } else {
                        resultsList
                    }
                    
                    Spacer()
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                    .foregroundColor(.accentSpotify)
                }
                
                ToolbarItem(placement: .principal) {
                    Text("Search Artist")
                        .font(.system(size: 17, weight: .semibold))
                        .foregroundColor(.textPrimary)
                }
            }
            .toolbarBackground(Color.gameBackground, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
        .preferredColorScheme(.dark)
        .onAppear {
            isSearchFocused = true
        }
    }
    
    // MARK: - Search Input
    
    private var searchInputView: some View {
        HStack(spacing: 12) {
            Image(systemName: "magnifyingglass")
                .foregroundColor(.textSecondary)
            
            TextField("Type artist name...", text: $searchText)
                .font(.searchInput)
                .foregroundColor(.textPrimary)
                .autocorrectionDisabled()
                .textInputAutocapitalization(.words)
                .focused($isSearchFocused)
            
            if !searchText.isEmpty {
                Button(action: { searchText = "" }) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.textSecondary)
                }
            }
        }
        .padding(.horizontal, 16)
        .frame(height: 50)
        .background(Color.cardBackground)
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(isSearchFocused ? Color.accentSpotify : Color.cardBorder, lineWidth: 1)
        )
    }
    
    // MARK: - Results List
    
    private var resultsList: some View {
        ScrollView {
            LazyVStack(spacing: 0) {
                ForEach(searchResults) { artist in
                    SearchResultRow(
                        artist: artist,
                        isAlreadyGuessed: isAlreadyGuessed(artist)
                    ) {
                        selectArtist(artist)
                    }
                    
                    if artist.id != searchResults.last?.id {
                        Divider()
                            .background(Color.cardBorder)
                            .padding(.leading, 16)
                    }
                }
            }
            .cardStyle()
            .padding(.horizontal, 16)
            .padding(.top, 16)
        }
    }
    
    // MARK: - Empty States
    
    private var emptyStateView: some View {
        VStack(spacing: 16) {
            Spacer()
            
            Image(systemName: "music.mic")
                .font(.system(size: 48))
                .foregroundColor(.textMuted)
            
            Text("Start typing to search")
                .font(.system(size: 16))
                .foregroundColor(.textSecondary)
            
            Spacer()
        }
    }
    
    private var noResultsView: some View {
        VStack(spacing: 16) {
            Spacer()
            
            Image(systemName: "magnifyingglass")
                .font(.system(size: 48))
                .foregroundColor(.textMuted)
            
            Text("No artists found")
                .font(.system(size: 16))
                .foregroundColor(.textSecondary)
            
            Text("Try a different search term")
                .font(.system(size: 14))
                .foregroundColor(.textMuted)
            
            Spacer()
        }
    }
    
    // MARK: - Helpers
    
    private func isAlreadyGuessed(_ artist: Artist) -> Bool {
        guard let state = gameManager.currentState else { return false }
        return state.guesses.contains { $0.artistId == artist.id }
    }
    
    private func selectArtist(_ artist: Artist) {
        guard !isAlreadyGuessed(artist) else { return }
        onSelect(artist)
        dismiss()
    }
}

// MARK: - Search Result Row

struct SearchResultRow: View {
    let artist: Artist
    let isAlreadyGuessed: Bool
    let onTap: () -> Void
    
    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 12) {
                artistThumb
                
                VStack(alignment: .leading, spacing: 2) {
                    Text(artist.name)
                        .font(.searchResult)
                        .foregroundColor(isAlreadyGuessed ? .textMuted : .textPrimary)
                    
                    if let nationality = artist.nationality {
                        Text(nationality)
                            .font(.system(size: 13))
                            .foregroundColor(.textMuted)
                    }
                }
                
                Spacer()
                
                if isAlreadyGuessed {
                    Text("Guessed")
                        .font(.system(size: 12))
                        .foregroundColor(.textMuted)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.cardBorder)
                        .cornerRadius(4)
                } else {
                    Image(systemName: "chevron.right")
                        .foregroundColor(.textMuted)
                        .font(.system(size: 14))
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .contentShape(Rectangle())
        }
        .disabled(isAlreadyGuessed)
    }
    
    @ViewBuilder
    private var artistThumb: some View {
        Group {
            if let urlString = artist.imageUrl, let url = URL(string: urlString) {
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
        .frame(width: 44, height: 44)
        .clipShape(Circle())
        .background(Color.cardBorder)
    }
    
    private var placeholderView: some View {
        Text(String(artist.name.prefix(1)).uppercased())
            .font(.system(size: 18, weight: .bold))
            .foregroundColor(.textSecondary)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

#Preview {
    SearchView { artist in
        print("Selected: \(artist.name)")
    }
    .environmentObject(GameManager())
}
