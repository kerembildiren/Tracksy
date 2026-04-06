const SUGGEST_MIN = 3;
const HINTS_PER_PLAYER = 4;

function apiUrl(path) {
  const b = (typeof window.__GRID_BASE__ === "string" ? window.__GRID_BASE__ : "").replace(
    /\/$/,
    ""
  );
  const p = path.startsWith("/") ? path : `/${path}`;
  return b + p;
}

let state = {
  gameId: null,
  selected: null,
  grid: null,
  panelCell: null,
  playMode: null,
  currentTurn: null,
  winner: null,
  hintUi: {},
};

const el = (id) => document.getElementById(id);

function escapeHtml(s) {
  if (!s) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function showModeModal() {
  const m = el("mode-modal");
  if (m) m.classList.remove("hidden");
}

function hideModeModal() {
  const m = el("mode-modal");
  if (m) m.classList.add("hidden");
}

function renderHeaders(rows, cols) {
  for (let c = 0; c < 3; c++) {
    el(`ch-${c}`).innerHTML = `<strong>${escapeHtml(cols[c].label)}</strong>`;
  }
  for (let r = 0; r < 3; r++) {
    el(`rh-${r}`).innerHTML = `<strong>${escapeHtml(rows[r].label)}</strong>`;
  }
}

function updateTurnBanner() {
  const b = el("turn-banner");
  if (!b) return;
  if (!state.grid || state.grid.play_mode !== "versus") {
    b.classList.add("hidden");
    b.textContent = "";
    return;
  }
  b.classList.remove("hidden");
  if (state.winner === 1) {
    b.textContent = "Kazanan: Oyuncu 1 (X)";
    return;
  }
  if (state.winner === 2) {
    b.textContent = "Kazanan: Oyuncu 2 (O)";
    return;
  }
  if (state.winner === 0) {
    b.textContent = "Berabere";
    return;
  }
  const t = state.currentTurn || 1;
  b.textContent = `Sıra: Oyuncu ${t} (${t === 1 ? "X" : "O"})`;
}

function hideAllHintPops() {
  for (let r = 0; r < 3; r++) {
    for (let c = 0; c < 3; c++) {
      const pop = el(`hint-pop-${r}-${c}`);
      if (pop) {
        pop.classList.add("hidden");
        pop.setAttribute("aria-hidden", "true");
      }
    }
  }
  state.panelCell = null;
}

function renderCells(grid) {
  const cells = grid.cells;
  for (let r = 0; r < 3; r++) {
    for (let c = 0; c < 3; c++) {
      const div = el(`cell-${r}-${c}`);
      const pool = cells[r][c].pool_size;
      const alt = (r + c) % 2 === 1;
      div.className = "cell play" + (alt ? " alt" : "");
      div.innerHTML = `
        <div class="cell-jersey" aria-hidden="true"><span class="jersey-icon"></span></div>
        <div class="cell-footer">
          <span class="cell-pool-meta">${pool} olası</span>
          <button type="button" class="hint-open-btn" data-r="${r}" data-c="${c}">İpuçları</button>
        </div>
      `;
      div.dataset.row = String(r);
      div.dataset.col = String(c);
    }
  }

  document.querySelectorAll(".cell.play").forEach((node) => {
    node.addEventListener("click", (e) => {
      if (e.target.closest(".hint-open-btn")) return;
      if (node.classList.contains("solved")) return;
      if (state.grid && state.grid.play_mode === "versus" && state.winner != null) return;
      document.querySelectorAll(".cell.play").forEach((n) => n.classList.remove("selected"));
      node.classList.add("selected");
      const r = +node.dataset.row;
      const c = +node.dataset.col;
      state.selected = { r, c };
      el("guess").focus();
      refreshSuggest();
    });
  });

  document.querySelectorAll(".hint-open-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const r = +btn.dataset.r;
      const c = +btn.dataset.c;
      openHintPanel(r, c);
    });
  });
}

let suggestTimer = null;

async function refreshSuggest() {
  const q = (el("guess").value || "").trim();
  const sug = el("suggest");
  if (!state.gameId || !state.selected) {
    sug.classList.add("hidden");
    sug.innerHTML = "";
    return;
  }
  if (state.grid && state.grid.play_mode === "versus" && state.winner != null) {
    sug.classList.add("hidden");
    sug.innerHTML = "";
    return;
  }
  if (q.length < SUGGEST_MIN) {
    sug.classList.add("hidden");
    sug.innerHTML = "";
    return;
  }
  const { r, c } = state.selected;
  const res = await fetch(apiUrl("/api/suggest"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ game_id: state.gameId, row: r, col: c, q }),
  });
  const data = await res.json();
  const items = data.suggestions || [];
  sug.innerHTML = "";
  if (!items.length) {
    sug.classList.add("hidden");
    return;
  }
  items.forEach((it) => {
    const li = document.createElement("li");
    li.textContent = it.name;
    li.addEventListener("mousedown", (e) => {
      e.preventDefault();
    });
    li.addEventListener("click", () => {
      el("guess").value = it.name;
      sug.classList.add("hidden");
      submitGuess();
    });
    sug.appendChild(li);
  });
  sug.classList.remove("hidden");
}

function applyHintPanelState(r, c, data) {
  const qlen = data.hint_queue_length || 0;
  let pages = data.pages || [];
  const padded = [];
  for (let i = 0; i < qlen; i++) {
    padded.push(pages[i] ? [...pages[i]] : []);
  }
  const focus = typeof data.hint_focus === "number" ? data.hint_focus : 0;
  state.hintUi[`${r}-${c}`] = { focus, qlen };

  const track = el(`hint-track-${r}-${c}`);
  if (!track) return;
  track.innerHTML = "";
  for (let i = 0; i < qlen; i++) {
    const page = document.createElement("div");
    page.className = "hint-carousel-page";
    const tag = document.createElement("div");
    tag.className = "hint-page-label";
    tag.textContent = `Olası oyuncu ${i + 1}`;
    page.appendChild(tag);
    const ol = document.createElement("ol");
    ol.className = "hint-page-list";
    (padded[i] || []).forEach((text) => {
      const li = document.createElement("li");
      li.textContent = text;
      ol.appendChild(li);
    });
    page.appendChild(ol);
    track.appendChild(page);
  }
  track.style.transform = `translateX(-${focus * 100}%)`;
  track.dataset.qlen = String(qlen);

  const dots = el(`hint-dots-${r}-${c}`);
  if (dots) {
    dots.innerHTML = "";
    for (let i = 0; i < qlen; i++) {
      const d = document.createElement("button");
      d.type = "button";
      d.className = "hint-dot" + (i === focus ? " active" : "");
      d.setAttribute("aria-label", `Oyuncu ${i + 1}`);
      d.addEventListener("click", () => setHintFocus(r, c, i));
      dots.appendChild(d);
    }
  }

  const cellNode = el(`cell-${r}-${c}`);
  const solved = cellNode && cellNode.classList.contains("solved");
  const curHints = padded[focus] || [];
  const curComplete = curHints.length >= HINTS_PER_PLAYER;

  const nextBtn = document.querySelector(`.hint-pop-next[data-r="${r}"][data-c="${c}"]`);
  if (nextBtn) nextBtn.disabled = solved || curComplete;

  const sw = document.querySelector(`.hint-switch-player[data-r="${r}"][data-c="${c}"]`);
  if (sw) {
    const showSw = Boolean(data.can_switch_player);
    sw.classList.toggle("hidden", !showSw);
  }
}

async function setHintFocus(r, c, focusIdx) {
  if (!state.gameId) return;
  const res = await fetch(apiUrl("/api/hint-focus"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ game_id: state.gameId, row: r, col: c, focus: focusIdx }),
  });
  const data = await res.json();
  if (!res.ok) return;
  if (state.panelCell && state.panelCell.r === r && state.panelCell.c === c) {
    applyHintPanelState(r, c, data);
  }
}

function bumpHintFocus(r, c, delta) {
  const ui = state.hintUi[`${r}-${c}`] || { focus: 0, qlen: 0 };
  const n = ui.qlen || 0;
  if (n <= 0) return;
  const next = (ui.focus + delta + n * 10) % n;
  setHintFocus(r, c, next);
}

async function openHintPanel(r, c) {
  if (!state.gameId) return;
  hideAllHintPops();
  state.panelCell = { r, c };
  const pop = el(`hint-pop-${r}-${c}`);
  if (pop) {
    pop.classList.remove("hidden");
    pop.setAttribute("aria-hidden", "false");
  }

  const res = await fetch(apiUrl("/api/hint-list"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ game_id: state.gameId, row: r, col: c }),
  });
  const data = await res.json();
  applyHintPanelState(r, c, data);
}

async function requestNextHint(r, c) {
  if (!state.gameId) return;
  const cell = el(`cell-${r}-${c}`);
  if (cell.classList.contains("solved")) return;
  await doHint(r, c);
}

async function newGame(playMode) {
  el("msg").textContent = "Oyun yükleniyor…";
  el("msg").classList.remove("err");
  hideAllHintPops();
  state.hintUi = {};
  state.winner = null;
  const difficulty = el("difficulty").value;
  const res = await fetch(apiUrl("/api/new-game"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ difficulty, play_mode: playMode }),
  });
  const data = await res.json();
  if (!res.ok) {
    el("msg").textContent = data.error || "Hata";
    el("msg").classList.add("err");
    showModeModal();
    return;
  }
  state.gameId = data.game_id;
  state.grid = data;
  state.playMode = data.play_mode || playMode;
  state.currentTurn = data.current_turn != null ? data.current_turn : null;
  state.winner = data.winner != null ? data.winner : null;
  state.selected = null;
  renderHeaders(data.rows, data.cols);
  renderCells(data);
  el("guess").value = "";
  el("suggest").classList.add("hidden");
  el("msg").textContent = "";
  updateTurnBanner();
}

function getSolvedCellHtml(playerName, mark) {
  let sym = '<span class="jersey-mark jersey-mark-solo jersey-reveal">✓</span>';
  if (mark === "X") sym = '<span class="jersey-mark jersey-mark-x jersey-reveal">X</span>';
  if (mark === "O") sym = '<span class="jersey-mark jersey-mark-o jersey-reveal">O</span>';
  return `<div class="cell-jersey cell-jersey-solved" aria-hidden="true">${sym}</div>
    <div class="cell-footer cell-footer-solved">
      <span class="cell-solved-name">${escapeHtml(playerName)}</span>
    </div>`;
}

function disableHintNextForCell(r, c) {
  const nextBtn = document.querySelector(`.hint-pop-next[data-r="${r}"][data-c="${c}"]`);
  if (nextBtn) nextBtn.disabled = true;
}

function renderSolvedCell(r, c, playerName, mark) {
  const cell = el(`cell-${r}-${c}`);
  cell.classList.add("solved");
  cell.classList.remove("selected");
  cell.innerHTML = getSolvedCellHtml(playerName, mark);
  disableHintNextForCell(r, c);
}

function waitForTransition(elm, msFallback) {
  return new Promise((resolve) => {
    let done = false;
    const fin = () => {
      if (done) return;
      done = true;
      elm.removeEventListener("transitionend", onEnd);
      resolve();
    };
    const onEnd = (e) => {
      if (e.target !== elm) return;
      fin();
    };
    elm.addEventListener("transitionend", onEnd);
    window.setTimeout(fin, msFallback);
  });
}

async function runCellFlipReveal(r, c, playerName, mark) {
  const cell = el(`cell-${r}-${c}`);
  const wrap = cell.parentElement;
  if (!cell || !wrap || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    renderSolvedCell(r, c, playerName, mark);
    return;
  }

  cell.classList.remove("selected");
  const savedHtml = cell.innerHTML;
  const inner = document.createElement("div");
  inner.className = "cell-flip-inner";
  inner.innerHTML = savedHtml;
  cell.innerHTML = "";
  cell.appendChild(inner);
  wrap.classList.add("cell-flip-active");

  inner.style.transform = "rotateX(0deg)";
  inner.offsetHeight;
  inner.style.transition = "transform 0.34s cubic-bezier(0.45, 0, 0.55, 1)";
  inner.style.transform = "rotateX(90deg)";
  await waitForTransition(inner, 420);

  const solvedHtml = getSolvedCellHtml(playerName, mark);
  inner.style.transition = "none";
  inner.innerHTML = solvedHtml;
  inner.style.transform = "rotateX(-90deg)";
  inner.offsetHeight;
  await new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res)));
  inner.style.transition = "transform 0.36s cubic-bezier(0.34, 1.1, 0.64, 1)";
  inner.style.transform = "rotateX(0deg)";
  await waitForTransition(inner, 450);

  cell.classList.add("solved");
  cell.innerHTML = solvedHtml;
  inner.style.transition = "";
  inner.style.transform = "";
  wrap.classList.remove("cell-flip-active");
  disableHintNextForCell(r, c);
}

async function submitGuess() {
  const name = el("guess").value;
  if (!state.gameId || !state.selected) {
    el("msg").textContent = "Önce bir kutu seçin.";
    el("msg").classList.add("err");
    return;
  }
  if (state.grid && state.grid.play_mode === "versus" && state.winner != null) {
    el("msg").textContent = "Oyun bitti.";
    el("msg").classList.add("err");
    return;
  }
  const { r, c } = state.selected;
  const res = await fetch(apiUrl("/api/guess"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ game_id: state.gameId, row: r, col: c, name }),
  });
  const data = await res.json();

  if (state.grid && state.grid.play_mode === "versus") {
    if (data.pass_turn && !data.ok) {
      el("msg").classList.add("err");
      el("msg").textContent = data.error || "Yanlış — sıra değişti.";
      if (data.current_turn != null) {
        state.currentTurn = data.current_turn;
        state.grid.current_turn = data.current_turn;
      }
      updateTurnBanner();
      return;
    }
  }

  if (!data.ok) {
    el("msg").textContent = data.error || "Hatalı";
    el("msg").classList.add("err");
    return;
  }

  el("msg").classList.remove("err");
  if (data.play_mode === "versus") {
    el("msg").textContent = `Doğru (${data.mark}): ${data.player.name}`;
    if (data.current_turn != null) {
      state.currentTurn = data.current_turn;
      state.grid.current_turn = data.current_turn;
    }
    if (data.winner != null) {
      state.winner = data.winner;
      state.grid.winner = data.winner;
      if (data.winner === 0) {
        el("msg").textContent = "Berabere!";
      } else if (data.winner === 1) {
        el("msg").textContent = "Oyuncu 1 (X) kazandı!";
      } else if (data.winner === 2) {
        el("msg").textContent = "Oyuncu 2 (O) kazandı!";
      }
    }
    updateTurnBanner();
    await runCellFlipReveal(r, c, data.player.name, data.mark);
  } else {
    el("msg").textContent = `Doğru: ${data.player.name}`;
    await runCellFlipReveal(r, c, data.player.name, null);
  }
  el("guess").value = "";
  el("suggest").classList.add("hidden");
  hideAllHintPops();
}

async function doHint(r, c) {
  if (!state.gameId) return;
  const res = await fetch(apiUrl("/api/hint"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ game_id: state.gameId, row: r, col: c }),
  });
  const data = await res.json();
  if (!res.ok) {
    el("msg").textContent = data.error || "İpucu alınamadı";
    el("msg").classList.add("err");
    return;
  }
  if (state.panelCell && state.panelCell.r === r && state.panelCell.c === c) {
    applyHintPanelState(r, c, data);
  }
}

function initHintCarouselTouch() {
  document.querySelectorAll(".hint-carousel-viewport").forEach((vp) => {
    let sx = 0;
    let sy = 0;
    vp.addEventListener(
      "touchstart",
      (e) => {
        sx = e.touches[0].clientX;
        sy = e.touches[0].clientY;
      },
      { passive: true }
    );
    vp.addEventListener(
      "touchend",
      (e) => {
        const ex = e.changedTouches[0].clientX;
        const ey = e.changedTouches[0].clientY;
        const dx = ex - sx;
        const dy = ey - sy;
        if (Math.abs(dx) < 48 || Math.abs(dx) < Math.abs(dy)) return;
        const r = +vp.dataset.r;
        const c = +vp.dataset.c;
        if (dx < 0) bumpHintFocus(r, c, 1);
        else bumpHintFocus(r, c, -1);
      },
      { passive: true }
    );
  });
}

el("btn-new").addEventListener("click", () => {
  showModeModal();
});
el("mode-solo").addEventListener("click", () => {
  hideModeModal();
  newGame("solo");
});
el("mode-versus").addEventListener("click", () => {
  hideModeModal();
  newGame("versus");
});

el("btn-go").addEventListener("click", submitGuess);
el("guess").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    submitGuess();
  }
});
el("guess").addEventListener("input", () => {
  clearTimeout(suggestTimer);
  suggestTimer = setTimeout(refreshSuggest, 180);
});

document.querySelector(".grid-wrap").addEventListener("click", (e) => {
  const closeBtn = e.target.closest(".hint-pop-close");
  if (closeBtn) {
    e.stopPropagation();
    hideAllHintPops();
    return;
  }
  const nextBtn = e.target.closest(".hint-pop-next");
  if (nextBtn) {
    e.stopPropagation();
    requestNextHint(+nextBtn.dataset.r, +nextBtn.dataset.c);
    return;
  }
  const prevA = e.target.closest(".hint-carousel-prev");
  if (prevA) {
    e.stopPropagation();
    bumpHintFocus(+prevA.dataset.r, +prevA.dataset.c, -1);
    return;
  }
  const nextA = e.target.closest(".hint-carousel-next");
  if (nextA) {
    e.stopPropagation();
    bumpHintFocus(+nextA.dataset.r, +nextA.dataset.c, 1);
    return;
  }
  const sw = e.target.closest(".hint-switch-player");
  if (sw) {
    e.stopPropagation();
    bumpHintFocus(+sw.dataset.r, +sw.dataset.c, 1);
    return;
  }
});

document.addEventListener("click", (e) => {
  if (e.target.closest(".hint-pop") || e.target.closest(".hint-open-btn")) return;
  if (!e.target.closest(".grid-wrap")) hideAllHintPops();
});

initHintCarouselTouch();
showModeModal();
