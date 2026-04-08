(function () {
  'use strict';

  const START_SCORE = 501;
  const MAX_VALID_GUESS = 180;
  const MAX_SUGGESTIONS = 12;

  let players = [];
  let dartState = {
    p1: START_SCORE,
    p2: START_SCORE,
    current: 1,
    winner: null,
    guessedIds: new Set()
  };

  const screens = {
    home: document.getElementById('screen-home'),
    basketball: document.getElementById('screen-basketball'),
    football: document.getElementById('screen-football'),
    ticTacToe: document.getElementById('screen-tic-tac-toe'),
    dart: document.getElementById('screen-dart')
  };

  const footballFrame = document.getElementById('football-game-frame');
  const FOOTBALL_GAME_URL = '/sportsguesser/football/';
  const DERBY_PAGE_URL = '/sportsguesser/football/derby/';
  const PLAYER_GUESS_URL = '/sportsguesser/football/guess/';
  const CAREER_GUESS_URL = '/sportsguesser/football/career/';

  const scoreEls = {
    1: document.getElementById('score-p1'),
    2: document.getElementById('score-p2')
  };

  const turnIndicator = document.getElementById('turn-indicator');
  const dartFeedback = document.getElementById('dart-feedback');
  const dartGuess = document.getElementById('dart-guess');
  const dartSubmit = document.getElementById('dart-submit');
  const dartSuggestions = document.getElementById('dart-suggestions');

  let suggestionHighlight = -1;
  let currentSuggestions = [];

  function showScreen(id) {
    if (
      screens.ticTacToe &&
      screens.ticTacToe.classList.contains('active') &&
      id !== 'ticTacToe'
    ) {
      clearFootballFrame();
    }
    Object.values(screens).forEach(s => s && s.classList.remove('active'));
    const el = screens[id];
    if (el) el.classList.add('active');
  }

  function searchPlayers(query) {
    const q = (query || '').trim().toLowerCase();
    if (!q) return [];
    return players
      .filter(p => !dartState.guessedIds.has(p.id) && p.id.toLowerCase().includes(q))
      .slice(0, MAX_SUGGESTIONS);
  }

  function findPlayer(name) {
    const trimmed = (name || '').trim();
    if (!trimmed) return null;
    const lower = trimmed.toLowerCase();
    const exact = players.find(p => p.id.toLowerCase() === lower);
    if (exact) return exact;
    return players.find(p => p.id.toLowerCase().includes(lower)) || null;
  }

  function showSuggestions(list) {
    currentSuggestions = list;
    suggestionHighlight = -1;
    dartSuggestions.innerHTML = '';
    if (list.length === 0) {
      dartSuggestions.setAttribute('aria-expanded', 'false');
      return;
    }
    dartGuess.setAttribute('aria-expanded', 'true');
    list.forEach((p, i) => {
      const li = document.createElement('li');
      li.textContent = p.id;
      li.setAttribute('role', 'option');
      li.setAttribute('aria-selected', 'false');
      li.dataset.index = String(i);
      li.addEventListener('click', () => selectSuggestion(p));
      dartSuggestions.appendChild(li);
    });
  }

  function selectSuggestion(player) {
    dartGuess.value = player.id;
    showSuggestions([]);
    dartGuess.focus();
    dartSubmitGuess();
  }

  function updateHighlight() {
    const items = dartSuggestions.querySelectorAll('li');
    items.forEach((li, i) => li.setAttribute('aria-selected', i === suggestionHighlight));
    if (suggestionHighlight >= 0 && items[suggestionHighlight]) {
      items[suggestionHighlight].scrollIntoView({ block: 'nearest' });
    }
  }

  function renderDartScores() {
    scoreEls[1].textContent = dartState.p1;
    scoreEls[2].textContent = dartState.p2;
    document.querySelectorAll('.player-score').forEach(el => {
      const p = parseInt(el.dataset.player, 10);
      el.classList.toggle('active', !dartState.winner && dartState.current === p);
    });
  }

  function setDartFeedback(msg, isError) {
    dartFeedback.textContent = msg;
    dartFeedback.className = 'dart-feedback' + (isError ? ' error' : ' success');
  }

  function dartSubmitGuess() {
    if (dartState.winner) return;
    showSuggestions([]);
    const name = dartGuess.value.trim();
    if (!name) {
      setDartFeedback('Enter or pick a player name.', true);
      return;
    }
    const player = findPlayer(name);
    if (!player) {
      setDartFeedback('Player not found. Type to search and pick from the list.', true);
      dartGuess.value = '';
      return;
    }
    if (dartState.guessedIds.has(player.id)) {
      setDartFeedback(`${player.id} was already guessed. Pick another player.`, true);
      dartState.current = dartState.current === 1 ? 2 : 1;
      turnIndicator.textContent = `Player ${dartState.current}'s turn`;
      dartGuess.value = '';
      renderDartScores();
      return;
    }
    const value = player['30plus_games'];
    const currentScore = dartState.current === 1 ? dartState.p1 : dartState.p2;
    if (value > MAX_VALID_GUESS) {
      setDartFeedback(`${player.id} has ${value} (max ${MAX_VALID_GUESS}). Guess invalid.`, true);
      dartState.current = dartState.current === 1 ? 2 : 1;
      turnIndicator.textContent = `Player ${dartState.current}'s turn`;
      dartGuess.value = '';
      renderDartScores();
      return;
    }
    if (value > currentScore) {
      setDartFeedback(`${player.id} has ${value}. Would go below zero. Guess invalid.`, true);
      dartState.current = dartState.current === 1 ? 2 : 1;
      turnIndicator.textContent = `Player ${dartState.current}'s turn`;
      dartGuess.value = '';
      renderDartScores();
      return;
    }
    dartState.guessedIds.add(player.id);
    const newScore = currentScore - value;
    if (dartState.current === 1) dartState.p1 = newScore;
    else dartState.p2 = newScore;
    if (newScore === 0) {
      dartState.winner = dartState.current;
      setDartFeedback(`Player ${dartState.current} wins! ${player.id} (${value}) → 0.`, false);
      turnIndicator.textContent = `Player ${dartState.current} wins!`;
      dartGuess.disabled = true;
      dartSubmit.disabled = true;
    } else {
      setDartFeedback(`${player.id} = ${value}. New score: ${newScore}.`, false);
      dartState.current = dartState.current === 1 ? 2 : 1;
      turnIndicator.textContent = `Player ${dartState.current}'s turn`;
      dartGuess.value = '';
    }
    renderDartScores();
  }

  function initDart() {
    dartState = {
      p1: START_SCORE,
      p2: START_SCORE,
      current: 1,
      winner: null,
      guessedIds: new Set()
    };
    dartGuess.value = '';
    dartGuess.disabled = false;
    dartSubmit.disabled = false;
    turnIndicator.textContent = "Player 1's turn";
    setDartFeedback('', false);
    showSuggestions([]);
    renderDartScores();
  }

  function initDartInput() {
    dartGuess.addEventListener('input', () => {
      const list = searchPlayers(dartGuess.value);
      showSuggestions(list);
      updateHighlight();
    });
    dartGuess.addEventListener('keydown', (e) => {
      if (currentSuggestions.length === 0) {
        if (e.key === 'Enter') dartSubmitGuess();
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        suggestionHighlight = (suggestionHighlight + 1) % currentSuggestions.length;
        updateHighlight();
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        suggestionHighlight = suggestionHighlight <= 0 ? currentSuggestions.length - 1 : suggestionHighlight - 1;
        updateHighlight();
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        if (suggestionHighlight >= 0 && currentSuggestions[suggestionHighlight]) {
          selectSuggestion(currentSuggestions[suggestionHighlight]);
        } else {
          dartSubmitGuess();
        }
        return;
      }
      if (e.key === 'Escape') {
        showSuggestions([]);
        dartGuess.blur();
      }
    });
    dartGuess.addEventListener('blur', () => {
      setTimeout(() => showSuggestions([]), 150);
    });
  }

  function loadFootballGameFrame() {
    if (!footballFrame) return;
    const url = new URL(FOOTBALL_GAME_URL, window.location.origin);
    footballFrame.src = url.href;
  }

  function clearFootballFrame() {
    if (footballFrame) footballFrame.src = 'about:blank';
  }

  function initNavigation() {
    document.querySelectorAll('.sport-card:not(.disabled)').forEach(btn => {
      btn.addEventListener('click', () => {
        const sport = btn.dataset.sport;
        if (sport === 'basketball') showScreen('basketball');
        if (sport === 'football') showScreen('football');
      });
    });
    document.querySelectorAll('.game-card').forEach(btn => {
      btn.addEventListener('click', () => {
        const game = btn.dataset.game;
        if (game === 'dart') {
          initDart();
          showScreen('dart');
        }
        if (game === 'tic-tac-toe') {
          loadFootballGameFrame();
          showScreen('ticTacToe');
        }
        if (game === 'derby-challenge') {
          window.location.assign(new URL(DERBY_PAGE_URL, window.location.origin).href);
        }
        if (game === 'player-guess') {
          window.location.assign(new URL(PLAYER_GUESS_URL, window.location.origin).href);
        }
        if (game === 'career-guess') {
          window.location.assign(new URL(CAREER_GUESS_URL, window.location.origin).href);
        }
      });
    });
    document.querySelectorAll('.back-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const back = btn.dataset.back;
        if (back) showScreen(back);
      });
    });
    dartSubmit.addEventListener('click', dartSubmitGuess);
    initDartInput();
  }

  async function loadPlayers() {
    try {
      const res = await fetch('api/allplayers');
      if (!res.ok) throw new Error('Failed to load players');
      players = await res.json();
    } catch (e) {
      console.error(e);
      players = [];
    }
  }

  async function init() {
    await loadPlayers();
    initNavigation();
  }

  init();
})();
