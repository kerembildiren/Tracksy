/**
 * Tracksy - Game Logic
 */

// Spotify Embed API: store when loaded (script loads async)
window.onSpotifyIframeApiReady = (IFrameAPI) => {
    window.__spotifyEmbedApi = IFrameAPI;
};

// ============================================================
// State
// ============================================================

let gameState = {
    guesses: [],
    status: 'playing',
    remaining: 10
};

let guessedIds = new Set();
let searchTimeout = null;
let countdownSeconds = 0;
let countdownInterval = null;
/** @type { { pause?: () => void; destroy?: () => void } | null } */
let resultSpotifyController = null;

// ============================================================
// Initialize
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    // Always start with home screen unless URL has a custom puzzle link
    showHomeScreen();
    const params = new URLSearchParams(window.location.search);
    const customArtistId = params.get('artist');
    if (customArtistId && customArtistId.trim()) {
        showGameScreen();
        initGame();
        initCountdown();
    }
    initSearch();
    initCreateModal();
});

function showHomeScreen() {
    document.getElementById('homeScreen').classList.remove('screen-hidden');
    document.getElementById('gameScreen').classList.add('screen-hidden');
}

function showGameScreen() {
    document.getElementById('homeScreen').classList.add('screen-hidden');
    document.getElementById('gameScreen').classList.remove('screen-hidden');
}

function goBackToHome() {
    const hasQuery = window.location.search && window.location.search.trim() !== '';
    if (hasQuery) {
        // Came from a custom puzzle link; go to clean URL so backend resets to daily game
        window.location.replace(window.location.origin + window.location.pathname);
        return;
    }
    document.getElementById('gameScreen').classList.add('screen-hidden');
    document.getElementById('homeScreen').classList.remove('screen-hidden');
}

async function startTurkish() {
    showGameScreen();
    await initGame();
    await initCountdown();
}

function showComingSoon(which) {
    const messages = {
        all: 'More singers from other nationalities coming soon. You\'ll need a separate playlist to play.',
        create: 'Create a custom puzzle: pick an artist, get a link, and share it. Whoever opens the link will try to find that artist.'
    };
    document.getElementById('comingSoonMessage').textContent = messages[which] || 'Coming soon.';
    document.getElementById('comingSoonModal').classList.add('active');
}

function hideComingSoon() {
    document.getElementById('comingSoonModal').classList.remove('active');
}

// ============================================================
// Create puzzle modal
// ============================================================

let createSearchTimeout = null;
let selectedCreateArtistId = null;
let selectedCreateArtistName = null;

function showCreateModal() {
    selectedCreateArtistId = null;
    selectedCreateArtistName = null;
    document.getElementById('createSearchInput').value = '';
    document.getElementById('createClearBtn').classList.remove('visible');
    document.getElementById('createSearchResults').innerHTML = '<div class="empty-state"><p>Type to search and pick an artist</p></div>';
    document.getElementById('createLinkSection').classList.add('screen-hidden');
    document.getElementById('createModal').classList.add('active');
    setTimeout(() => document.getElementById('createSearchInput').focus(), 200);
}

function hideCreateModal() {
    document.getElementById('createModal').classList.remove('active');
}

function initCreateModal() {
    const input = document.getElementById('createSearchInput');
    const clearBtn = document.getElementById('createClearBtn');
    input.addEventListener('input', () => {
        const q = input.value.trim();
        clearBtn.classList.toggle('visible', q.length > 0);
        if (createSearchTimeout) clearTimeout(createSearchTimeout);
        createSearchTimeout = setTimeout(() => searchCreateArtists(q), 250);
    });
}

async function searchCreateArtists(query) {
    const container = document.getElementById('createSearchResults');
    if (!query) {
        container.innerHTML = '<div class="empty-state"><p>Type to search and pick an artist</p></div>';
        return;
    }
    try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        const artists = await response.json();
        if (artists.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No artists found</p></div>';
            return;
        }
        container.innerHTML = artists.map(artist => {
            const thumb = artist.image_url
                ? `<img class="artist-avatar-img" src="${escapeHtml(artist.image_url)}" alt="">`
                : `<span class="artist-avatar-initial">${(artist.name || '?').charAt(0).toUpperCase()}</span>`;
            const nameEsc = escapeHtml(artist.name || '');
            const idEsc = escapeHtml(artist.id);
            return `<div class="search-result-item create-result-item" data-artist-id="${idEsc}" data-artist-name="${nameEsc}" onclick="selectCreateArtistFromEl(this)">
                <div class="artist-avatar">${thumb}</div>
                <div class="artist-info">
                    <div class="name">${nameEsc}</div>
                    ${artist.nationality ? `<div class="nationality">${escapeHtml(artist.nationality)}</div>` : ''}
                </div>
            </div>`;
        }).join('');
    } catch (e) {
        container.innerHTML = '<div class="empty-state"><p>Search failed</p></div>';
    }
}

function selectCreateArtistFromEl(el) {
    const artistId = el && el.dataset && el.dataset.artistId;
    const artistName = el && el.dataset && el.dataset.artistName;
    if (!artistId) return;
    selectedCreateArtistId = artistId;
    selectedCreateArtistName = artistName || 'Artist';
    const base = window.location.origin + window.location.pathname;
    const link = base + (base.includes('?') ? '&' : '?') + 'artist=' + encodeURIComponent(artistId);
    document.getElementById('createSelectedLabel').textContent = 'Selected: ' + selectedCreateArtistName;
    document.getElementById('createLinkInput').value = link;
    document.getElementById('createLinkSection').classList.remove('screen-hidden');
}

function copyCreateLink() {
    const input = document.getElementById('createLinkInput');
    input.select();
    input.setSelectionRange(0, 99999);
    navigator.clipboard.writeText(input.value).then(() => {
        const btn = document.querySelector('.create-copy-btn');
        if (btn) { btn.textContent = 'Copied!'; setTimeout(() => { btn.textContent = 'Copy'; }, 2000); }
    });
}

function playCreatePuzzle() {
    if (!selectedCreateArtistId) return;
    const base = window.location.origin + window.location.pathname;
    const link = base + (base.includes('?') ? '&' : '?') + 'artist=' + encodeURIComponent(selectedCreateArtistId);
    hideCreateModal();
    window.location.href = link;
}

function clearCreateSearch() {
    document.getElementById('createSearchInput').value = '';
    document.getElementById('createClearBtn').classList.remove('visible');
    document.getElementById('createSearchResults').innerHTML = '<div class="empty-state"><p>Type to search and pick an artist</p></div>';
}

async function initGame() {
    try {
        // Load game state
        const response = await fetch('/api/state');
        gameState = await response.json();
        
        // Track guessed IDs
        guessedIds = new Set((gameState.guesses || []).map(g => g.artist_id));
        
        // Render UI (only if game screen is visible)
        if (!document.getElementById('gameScreen').classList.contains('screen-hidden')) {
            renderDots();
            renderGuesses();
            updateActionButton();
            loadDebugAnswer();
        }
        
        // Show result if game is over and we're on game screen
        const gameScreenVisible = !document.getElementById('gameScreen').classList.contains('screen-hidden');
        if (gameScreenVisible && gameState.status !== 'playing') {
            setTimeout(() => showResult(), 500);
        }
    } catch (error) {
        console.error('Failed to load game:', error);
    }
}

const DEBUG_ANSWER_HIDDEN = '[TEST MODE] Answer hidden — press Reveal to see it.';

async function loadDebugAnswer() {
    const debugEl = document.getElementById('debugAnswer');
    if (!debugEl) return;
    debugEl.textContent = DEBUG_ANSWER_HIDDEN;
}

async function revealDebugAnswer() {
    const debugEl = document.getElementById('debugAnswer');
    if (!debugEl) return;
    if (debugEl.textContent !== DEBUG_ANSWER_HIDDEN) return; // already revealed
    try {
        const response = await fetch('/api/debug/answer');
        const artist = await response.json();
        debugEl.textContent = `TEST MODE: Correct answer is ${artist.name}.`;
    } catch (error) {
        console.error('Failed to load debug answer:', error);
        debugEl.textContent = 'TEST MODE: Could not load answer.';
    }
}

// ============================================================
// Countdown Timer (Turkey Timezone)
// ============================================================

async function initCountdown() {
    await fetchCountdown();
    if (countdownSeconds > 0) {
        countdownInterval = setInterval(updateCountdown, 1000);
    }
}

async function fetchCountdown() {
    try {
        const response = await fetch('/api/next-reset');
        if (!response.ok) {
            throw new Error('Failed to fetch');
        }
        const data = await response.json();
        countdownSeconds = data.seconds_remaining || 0;
        updateCountdownDisplay();
        console.log('Countdown initialized:', countdownSeconds, 'seconds remaining');
    } catch (error) {
        console.error('Failed to fetch countdown:', error);
        document.getElementById('countdownTime').textContent = '--:--:--';
    }
}

function updateCountdown() {
    if (countdownSeconds > 0) {
        countdownSeconds--;
        updateCountdownDisplay();
    } else {
        clearInterval(countdownInterval);
        location.reload();
    }
}

function updateCountdownDisplay() {
    const el = document.getElementById('countdownTime');
    if (!el) return;
    
    const hours = Math.floor(countdownSeconds / 3600);
    const minutes = Math.floor((countdownSeconds % 3600) / 60);
    const seconds = countdownSeconds % 60;
    
    const timeStr = [
        hours.toString().padStart(2, '0'),
        minutes.toString().padStart(2, '0'),
        seconds.toString().padStart(2, '0')
    ].join(':');
    
    el.textContent = timeStr;
}

// ============================================================
// Render Functions
// ============================================================

function renderDots() {
    const dotsContainer = document.getElementById('guessDots');
    dotsContainer.innerHTML = '';
    
    for (let i = 0; i < 10; i++) {
        const dot = document.createElement('div');
        dot.className = 'dot';
        
        if (i < gameState.guesses.length) {
            if (i === gameState.guesses.length - 1 && gameState.status === 'won') {
                dot.classList.add('correct');
            } else {
                dot.classList.add('used');
            }
        }
        
        dotsContainer.appendChild(dot);
    }
}

function renderGuesses() {
    const container = document.getElementById('guessesContainer');
    container.innerHTML = '';
    
    // Reverse order: newest guess at top
    const reversedGuesses = [...gameState.guesses].reverse();
    reversedGuesses.forEach(guess => {
        const card = createGuessCard(guess);
        container.appendChild(card);
    });
    
    // Scroll to top to show newest guess
    container.scrollTop = 0;
}

function createGuessCard(guess) {
    const card = document.createElement('div');
    card.className = 'guess-card';
    
    const artist = guess.artist;
    const hints = guess.hints;
    const imgHtml = artist.image_url
        ? `<img class="guess-artist-img" src="${escapeHtml(artist.image_url)}" alt="">`
        : `<div class="guess-artist-placeholder">${(artist.name || '?').charAt(0).toUpperCase()}</div>`;
    
    card.innerHTML = `
        <div class="guess-header">
            <div class="guess-artist-thumb">${imgHtml}</div>
            <span class="artist-name">${escapeHtml(artist.name)}</span>
            ${guess.is_correct ? '<span class="check-icon">✓</span>' : ''}
        </div>
        <div class="hint-grid">
            ${createHintCell('BIRTH YEAR', formatYear(artist.debut_year), hints.debut_year)}
            ${createHintCell('GROUP SIZE', formatGroupSize(artist.group_size), hints.group_size)}
            ${createHintCell('GENDER', formatGender(artist.gender), hints.gender)}
            ${createHintCell('GENRE', formatGenres(artist), hints.genre)}
            ${createHintCell('NATION', formatNationality(artist.nationality), hints.nationality)}
            ${createHintCell('POPULARITY', formatPopularity(artist.popularity), hints.popularity)}
        </div>
    `;
    
    return card;
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function createHintCell(label, value, hint) {
    const resultClass = getHintClass(hint);
    const arrow = getArrow(hint);
    
    return `
        <div class="hint-cell">
            <span class="hint-label">${label}</span>
            <div class="hint-value ${resultClass}">
                <span>${value}</span>
                ${arrow ? `<span class="arrow">${arrow}</span>` : ''}
            </div>
        </div>
    `;
}

function getHintClass(hint) {
    if (!hint) return 'wrong';
    // Only 3 colors: green (correct), yellow (close), default (wrong)
    if (hint.result === 'correct') return 'correct';
    if (hint.result === 'close') return 'close';
    return 'wrong';
}

function getArrow(hint) {
    if (!hint) return null;
    
    if (hint.result === 'higher') return '↑';
    if (hint.result === 'lower') return '↓';
    if (hint.result === 'close' && hint.direction === 'higher') return '↑';
    if (hint.result === 'close' && hint.direction === 'lower') return '↓';
    
    return null;
}

function updateActionButton() {
    const btn = document.getElementById('actionBtn');
    
    if (gameState.status === 'won') {
        btn.innerHTML = `
            <span>🏆</span>
            <span>View Results</span>
        `;
        btn.onclick = showResult;
    } else if (gameState.status === 'lost') {
        btn.innerHTML = `
            <span>👁️</span>
            <span>See Answer</span>
        `;
        btn.classList.add('gold');
        btn.onclick = showResult;
    } else {
        btn.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/>
                <path d="m21 21-4.35-4.35"/>
            </svg>
            <span>Make a Guess</span>
        `;
        btn.onclick = showSearch;
    }
}

// ============================================================
// Formatting Helpers
// ============================================================

function formatYear(year) {
    return year ? String(year) : '?';
}

function formatGender(gender) {
    if (!gender) return '?';
    if (gender.toLowerCase() === 'male') return 'Male';
    if (gender.toLowerCase() === 'female') return 'Female';
    if (gender.toLowerCase() === 'mixed') return 'Mixed';
    return gender;
}

function formatNationality(nationality) {
    if (!nationality) return '?';
    if (nationality.toLowerCase() === 'turkish') return 'TR';
    return nationality.substring(0, 3).toUpperCase();
}

function formatPopularity(rank) {
    if (rank == null || rank === '') return '?';
    return '#' + Number(rank);
}

function formatGroupSize(size) {
    if (!size) return '?';
    return size === 1 ? 'Solo' : 'Group';
}

function formatGenres(artist) {
    if (!artist) return '?';
    const g = artist.genres;
    if (Array.isArray(g) && g.length) return g.join(', ');
    return '?';
}

// ============================================================
// Search
// ============================================================

function initSearch() {
    const input = document.getElementById('searchInput');
    const clearBtn = document.getElementById('clearBtn');
    
    input.addEventListener('input', (e) => {
        const query = e.target.value;
        
        // Show/hide clear button
        clearBtn.classList.toggle('visible', query.length > 0);
        
        // Debounce search
        if (searchTimeout) clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            searchArtists(query);
        }, 200);
    });
}

async function searchArtists(query) {
    const resultsContainer = document.getElementById('searchResults');
    
    if (!query.trim()) {
        resultsContainer.innerHTML = `
            <div class="empty-state">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M12 18.5a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13ZM12 8v4M12 14h.01"/>
                </svg>
                <p>Start typing to search</p>
            </div>
        `;
        return;
    }
    
    try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        const artists = await response.json();
        
        if (artists.length === 0) {
            resultsContainer.innerHTML = `
                <div class="empty-state">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <circle cx="11" cy="11" r="8"/>
                        <path d="m21 21-4.35-4.35"/>
                    </svg>
                    <p>No artists found</p>
                </div>
            `;
            return;
        }
        
        resultsContainer.innerHTML = artists.map(artist => {
            const isGuessed = guessedIds.has(artist.id);
            const thumb = artist.image_url
                ? `<img class="artist-avatar-img" src="${escapeHtml(artist.image_url)}" alt="">`
                : `<span class="artist-avatar-initial">${(artist.name || '?').charAt(0).toUpperCase()}</span>`;
            return `
                <div class="search-result-item ${isGuessed ? 'disabled' : ''}" 
                     onclick="${isGuessed ? '' : `selectArtist('${artist.id}')`}">
                    <div class="artist-avatar">${thumb}</div>
                    <div class="artist-info">
                        <div class="name">${escapeHtml(artist.name)}</div>
                        ${artist.nationality ? `<div class="nationality">${escapeHtml(artist.nationality)}</div>` : ''}
                    </div>
                    ${isGuessed ? '<span class="guessed-badge">Guessed</span>' : ''}
                </div>
            `;
        }).join('');
        
    } catch (error) {
        console.error('Search failed:', error);
    }
}

async function selectArtist(artistId) {
    if (guessedIds.has(artistId)) return;
    
    try {
        const response = await fetch('/api/guess', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ artist_id: artistId })
        });
        
        const result = await response.json();
        
        if (result.error) {
            alert(result.error);
            return;
        }
        
        // Update state
        gameState.guesses.push(result.guess);
        gameState.status = result.status;
        gameState.remaining = result.remaining;
        guessedIds.add(artistId);
        
        // Update UI
        hideSearch();
        renderDots();
        renderGuesses();
        updateActionButton();
        
        // Show result if game over
        if (result.status !== 'playing') {
            setTimeout(() => showResult(), 500);
        }
        
    } catch (error) {
        console.error('Guess failed:', error);
    }
}

function clearSearch() {
    const input = document.getElementById('searchInput');
    const clearBtn = document.getElementById('clearBtn');
    
    input.value = '';
    clearBtn.classList.remove('visible');
    searchArtists('');
    input.focus();
}

// ============================================================
// Modals
// ============================================================

function showSearch() {
    if (gameState.status !== 'playing') return;
    
    const modal = document.getElementById('searchModal');
    modal.classList.add('active');
    
    setTimeout(() => {
        document.getElementById('searchInput').focus();
    }, 300);
}

function hideSearch() {
    const modal = document.getElementById('searchModal');
    modal.classList.remove('active');
    
    // Clear search
    document.getElementById('searchInput').value = '';
    document.getElementById('clearBtn').classList.remove('visible');
}

async function showResult() {
    const modal = document.getElementById('resultModal');
    const isWin = gameState.status === 'won';
    
    // Set icon
    const iconEl = document.getElementById('resultIcon');
    iconEl.className = `result-icon ${isWin ? 'win' : 'lose'}`;
    iconEl.textContent = isWin ? '🏆' : '🎵';
    
    // Set title
    document.getElementById('resultTitle').textContent = isWin ? 'Congratulations!' : 'Game Over';
    
    // Set subtitle
    const guessCount = gameState.guesses.length;
    document.getElementById('resultSubtitle').textContent = isWin 
        ? `You found the artist in ${guessCount} guess${guessCount === 1 ? '' : 'es'}!`
        : 'Better luck next time!';
    
    // Load correct artist and optional preview / Spotify link
    try {
        const response = await fetch('/api/answer');
        const artist = await response.json();
        
        const answerImg = artist.image_url
            ? `<img class="avatar-img" src="${escapeHtml(artist.image_url)}" alt="">`
            : `<span class="avatar-initial">${(artist.name || '?').charAt(0).toUpperCase()}</span>`;
        document.getElementById('correctArtistCard').innerHTML = `
            <div class="label">The answer was</div>
            <div class="artist-row">
                <div class="avatar">${answerImg}</div>
                <div class="details">
                    <div class="name">${escapeHtml(artist.name)}</div>
                    <div class="meta">
                        ${artist.nationality ? `🌍 ${artist.nationality}` : ''}
                        ${artist.debut_year ? ` • 📅 ${artist.debut_year}` : ''}
                    </div>
                </div>
            </div>
        `;

        // Play track: Spotify embed with auto-play when ready. Fallback: link to artist/track.
        const audioEl = document.getElementById('resultAudio');
        const spotifyUrl = artist.top_track_uri || `https://open.spotify.com/artist/${artist.id}`;
        if (artist.top_track_id) {
            const trackUri = `spotify:track:${artist.top_track_id}`;
            const labelHtml = artist.top_track_name ? `<div class="result-preview-label">${escapeHtml(artist.top_track_name)}</div>` : '';
            audioEl.innerHTML = `
                <div class="result-preview">
                    ${labelHtml}
                    <div id="resultSpotifyEmbed" class="result-spotify-embed-container"></div>
                    <a href="${escapeHtml(spotifyUrl)}" target="_blank" rel="noopener" class="result-spotify-link">Open in Spotify</a>
                </div>
            `;
            audioEl.classList.remove('screen-hidden');

            const container = document.getElementById('resultSpotifyEmbed');
            if (container && window.__spotifyEmbedApi) {
                resultSpotifyController = null;
                window.__spotifyEmbedApi.createController(container, {
                    uri: trackUri,
                    width: 300,
                    height: 152
                }, (embedController) => {
                    resultSpotifyController = embedController;
                    embedController.addListener('ready', () => {
                        embedController.play();
                    });
                });
            } else {
                const embedUrl = `https://open.spotify.com/embed/track/${encodeURIComponent(artist.top_track_id)}?utm_source=generator`;
                container.innerHTML = `<iframe class="result-spotify-embed" src="${escapeHtml(embedUrl)}" width="100%" height="152" frameBorder="0" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy" title="Spotify track"></iframe>`;
            }
        } else {
            audioEl.innerHTML = `
                <div class="result-preview">
                    <a href="${escapeHtml(spotifyUrl)}" target="_blank" rel="noopener" class="action-btn result-spotify-btn">Listen on Spotify</a>
                </div>
            `;
            audioEl.classList.remove('screen-hidden');
        }
    } catch (error) {
        console.error('Failed to load answer:', error);
        document.getElementById('resultAudio').innerHTML = '';
    }
    
    modal.classList.add('active');
}

function hideResult() {
    if (resultSpotifyController) {
        try {
            if (typeof resultSpotifyController.pause === 'function') resultSpotifyController.pause();
            if (typeof resultSpotifyController.destroy === 'function') resultSpotifyController.destroy();
        } catch (_) {}
        resultSpotifyController = null;
    }
    const audioEl = document.getElementById('resultAudio');
    if (audioEl) audioEl.innerHTML = '';
    document.getElementById('resultModal').classList.remove('active');
}

function showHelp() {
    document.getElementById('helpModal').classList.add('active');
}

function hideHelp() {
    document.getElementById('helpModal').classList.remove('active');
}

function showStats() {
    // For now, just show the result modal with stats
    showResult();
}

// ============================================================
// Stats (Local Storage)
// ============================================================

function loadStats() {
    const saved = localStorage.getItem('tsg_stats');
    if (saved) {
        return JSON.parse(saved);
    }
    return { played: 0, won: 0, streak: 0, maxStreak: 0 };
}

function saveStats(won) {
    const stats = loadStats();
    stats.played++;
    if (won) {
        stats.won++;
        stats.streak++;
        stats.maxStreak = Math.max(stats.maxStreak, stats.streak);
    } else {
        stats.streak = 0;
    }
    localStorage.setItem('tsg_stats', JSON.stringify(stats));
}

// ============================================================
// Share
// ============================================================

function shareResults() {
    const isWin = gameState.status === 'won';
    const guessCount = gameState.guesses.length;
    const result = isWin ? `${guessCount}/10` : 'X/10';
    
    // Create emoji grid
    const grid = gameState.guesses.map(g => {
        const hints = g.hints;
        return [
            getEmojiForHint(hints.debut_year),
            getEmojiForHint(hints.group_size),
            getEmojiForHint(hints.gender),
            getEmojiForHint(hints.genre),
            getEmojiForHint(hints.nationality),
            getEmojiForHint(hints.popularity)
        ].join('');
    }).join('\n');
    
    const text = `Tracksy 🎵\n${result}\n\n${grid}`;
    
    if (navigator.share) {
        navigator.share({ text });
    } else {
        navigator.clipboard.writeText(text).then(() => {
            alert('Copied to clipboard!');
        });
    }
}

function getEmojiForHint(hint) {
    if (!hint) return '⬛';
    switch (hint.result) {
        case 'correct': return '🟩';
        case 'close': return '🟨';
        default: return '⬛';
    }
}

// ============================================================
// Debug / Testing
// ============================================================

async function resetGame() {
    try {
        await fetch('/api/reset', { method: 'POST' });
        location.reload();
    } catch (error) {
        console.error('Failed to reset game:', error);
    }
}
