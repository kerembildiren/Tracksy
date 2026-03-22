const SUGGEST_MIN = 3;

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

function renderHeaders(rows, cols) {
  for (let c = 0; c < 3; c++) {
    el(`ch-${c}`).innerHTML = `<strong>${escapeHtml(cols[c].label)}</strong>`;
  }
  for (let r = 0; r < 3; r++) {
    el(`rh-${r}`).innerHTML = `<strong>${escapeHtml(rows[r].label)}</strong>`;
  }
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
    li.addEventListener("click", () => {
      el("guess").value = it.name;
      sug.classList.add("hidden");
    });
    sug.appendChild(li);
  });
  sug.classList.remove("hidden");
}

function renderHintListFor(r, c, hints) {
  const ol = el(`hint-list-${r}-${c}`);
  if (!ol) return;
  ol.innerHTML = "";
  (hints || []).forEach((text) => {
    const li = document.createElement("li");
    li.textContent = text;
    ol.appendChild(li);
  });
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
  renderHintListFor(r, c, data.hints || []);

  const cell = el(`cell-${r}-${c}`);
  const solved = cell.classList.contains("solved");
  const nextBtn = document.querySelector(`.hint-pop-next[data-r="${r}"][data-c="${c}"]`);
  if (nextBtn) nextBtn.disabled = solved;
}

async function requestNextHint(r, c) {
  if (!state.gameId) return;
  const cell = el(`cell-${r}-${c}`);
  if (cell.classList.contains("solved")) return;
  await doHint(r, c);
}

async function newGame() {
  el("msg").textContent = "Oyun yükleniyor…";
  el("msg").classList.remove("err");
  hideAllHintPops();
  const difficulty = el("difficulty").value;
  const res = await fetch(apiUrl("/api/new-game"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ difficulty }),
  });
  const data = await res.json();
  if (!res.ok) {
    el("msg").textContent = data.error || "Hata";
    el("msg").classList.add("err");
    return;
  }
  state.gameId = data.game_id;
  state.grid = data;
  state.selected = null;
  renderHeaders(data.rows, data.cols);
  renderCells(data);
  el("guess").value = "";
  el("suggest").classList.add("hidden");
  el("msg").textContent = "";
}

async function submitGuess() {
  const name = el("guess").value;
  if (!state.gameId || !state.selected) {
    el("msg").textContent = "Önce bir kutu seçin.";
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
  if (!data.ok) {
    el("msg").textContent = data.error || "Hatalı";
    el("msg").classList.add("err");
    return;
  }
  el("msg").classList.remove("err");
  el("msg").textContent = `Doğru: ${data.player.name}`;
  el("guess").value = "";
  el("suggest").classList.add("hidden");
  const cell = el(`cell-${r}-${c}`);
  cell.classList.add("solved");
  cell.classList.remove("selected");
  cell.innerHTML = `<div class="cell-jersey cell-jersey-solved" aria-hidden="true"><span class="jersey-check">✓</span></div>
    <div class="cell-footer cell-footer-solved">
      <span class="cell-solved-name">${escapeHtml(data.player.name)}</span>
    </div>`;
  const nextBtn = document.querySelector(`.hint-pop-next[data-r="${r}"][data-c="${c}"]`);
  if (nextBtn) nextBtn.disabled = true;
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
    renderHintListFor(r, c, data.hints || []);
  }
}

el("btn-new").addEventListener("click", newGame);
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
  }
});

document.addEventListener("click", (e) => {
  if (e.target.closest(".hint-pop") || e.target.closest(".hint-open-btn")) return;
  if (!e.target.closest(".grid-wrap")) hideAllHintPops();
});

newGame();
