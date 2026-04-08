(function () {
  "use strict";

  function apiRoot() {
    const ex = typeof window.__CAREER_GUESS_ROOT__ === "string" ? window.__CAREER_GUESS_ROOT__.trim() : "";
    if (ex) return ex.replace(/\/?$/, "/");
    return new URL("/sportsguesser/football/career/", window.location.origin).href;
  }

  function apiUrl(path) {
    return new URL(path.replace(/^\//, ""), apiRoot()).href;
  }

  const el = (id) => document.getElementById(id);

  let gameState = {
    career_rows: [],
    goals_revealed: false,
    profile_hints: {},
    profile_step: 0,
    profile_max_step: 3,
    guesses: [],
    status: "playing",
  };
  let searchTimer = null;

  function escapeHtml(s) {
    if (s == null) return "";
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  async function fetchState() {
    const res = await fetch(apiUrl("api/state"), { credentials: "same-origin" });
    if (!res.ok) throw new Error("state");
    gameState = await res.json();
    renderAll();
  }

  function renderTable() {
    const tb = el("cgTableBody");
    if (!tb) return;
    const rows = gameState.career_rows || [];
    const rev = gameState.goals_revealed;
    tb.innerHTML = rows
      .map((r) => {
        const g =
          rev && r.goals != null
            ? String(r.goals)
            : '<span class="cg-goals-hidden">—</span>';
        return `<tr><td>${escapeHtml(r.season)}</td><td>${escapeHtml(r.teams)}</td><td>${g}</td></tr>`;
      })
      .join("");

    const btnG = el("cgBtnGoals");
    if (btnG) {
      btnG.disabled = !!rev;
      btnG.textContent = rev ? "Goller açık" : "Golleri göster";
    }
  }

  function renderGuesses() {
    const box = el("cgGuesses");
    if (!box) return;
    const list = gameState.guesses || [];
    box.innerHTML = list
      .map((g) => {
        const p = g.player;
        const cls = g.correct ? "cg-win" : "cg-miss";
        const mark = g.correct ? " ✓" : "";
        return `<div class="cg-guess-chip ${cls}">${escapeHtml(p.name)}${mark}</div>`;
      })
      .join("");
  }

  function renderProfileModalContent() {
    const box = el("cgProfileLines");
    const next = el("cgProfileNext");
    if (!box) return;
    const h = gameState.profile_hints || {};
    const parts = [];
    if (h.position != null) parts.push(`<p><strong>Mevki:</strong> ${escapeHtml(h.position)}</p>`);
    if (h.birth_year != null) parts.push(`<p><strong>Doğum yılı:</strong> ${escapeHtml(h.birth_year)}</p>`);
    if (h.nationality) parts.push(`<p><strong>Milliyet:</strong> ${escapeHtml(h.nationality)}</p>`);
    box.innerHTML = parts.length ? parts.join("") : "<p class=\"cg-goals-hidden\">Henüz ipucu yok. «Sonraki ipucu» ile aç.</p>";

    const step = gameState.profile_step || 0;
    const max = gameState.profile_max_step || 3;
    if (next) {
      next.disabled = step >= max;
      next.textContent = step >= max ? "Tüm ipuçları açıldı" : "Sonraki ipucu";
    }
  }

  function renderAll() {
    renderTable();
    renderGuesses();
    renderProfileModalContent();
  }

  function openSearch() {
    el("cgSearchPanel").classList.remove("hidden");
    el("cgSearchInput").value = "";
    el("cgSearchResults").innerHTML = "";
    el("cgSearchInput").focus();
  }

  function closeSearch() {
    el("cgSearchPanel").classList.add("hidden");
  }

  async function runSearch(q) {
    const res = await fetch(apiUrl(`api/search?q=${encodeURIComponent(q)}`), { credentials: "same-origin" });
    if (!res.ok) return;
    const rows = await res.json();
    const ul = el("cgSearchResults");
    ul.innerHTML = rows
      .map(
        (r) =>
          `<li data-id="${r.player_id}"><strong>${escapeHtml(r.name)}</strong><div class="nat">${escapeHtml(r.nationality || "")}</div></li>`
      )
      .join("");
    ul.querySelectorAll("li").forEach((li) => {
      li.addEventListener("click", () => submitGuess(Number(li.dataset.id)));
    });
  }

  async function submitGuess(playerId) {
    closeSearch();
    const res = await fetch(apiUrl("api/guess"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ player_id: playerId }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      alert(data.error || "Hata");
      return;
    }
    gameState = data;
    renderAll();
  }

  async function postHintGoals() {
    const res = await fetch(apiUrl("api/hint/goals"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: "{}",
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return;
    gameState = data;
    renderAll();
  }

  async function postHintProfile() {
    const res = await fetch(apiUrl("api/hint/profile"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: "{}",
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return;
    gameState = data;
    renderProfileModalContent();
    renderTable();
  }

  function showProfileModal() {
    renderProfileModalContent();
    el("cgProfileModal").classList.remove("hidden");
  }

  function hideProfileModal() {
    el("cgProfileModal").classList.add("hidden");
  }

  function init() {
    fetchState().catch(() => alert("Oyun yüklenemedi."));

    el("cgBtnGuess").addEventListener("click", openSearch);
    el("cgSearchClose").addEventListener("click", closeSearch);
    el("cgSearchInput").addEventListener("input", () => {
      const q = el("cgSearchInput").value.trim();
      if (searchTimer) clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        if (q.length >= 2) runSearch(q);
        else el("cgSearchResults").innerHTML = "";
      }, 200);
    });

    el("cgBtnGoals").addEventListener("click", () => postHintGoals());
    el("cgBtnProfile").addEventListener("click", () => showProfileModal());
    el("cgProfileBackdrop").addEventListener("click", hideProfileModal);
    el("cgProfileClose").addEventListener("click", hideProfileModal);
    el("cgProfileNext").addEventListener("click", () => postHintProfile());

    el("cgBtnNew").addEventListener("click", () => window.location.reload());
  }

  document.addEventListener("DOMContentLoaded", init);
})();
