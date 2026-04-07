(function () {
  "use strict";

  function apiRoot() {
    const ex = typeof window.__PLAYER_GUESS_ROOT__ === "string" ? window.__PLAYER_GUESS_ROOT__.trim() : "";
    if (ex) return ex.replace(/\/?$/, "/");
    return new URL("/sportsguesser/football/guess/", window.location.origin).href;
  }

  function apiUrl(path) {
    const rel = path.replace(/^\//, "");
    return new URL(rel, apiRoot()).href;
  }

  let gameState = { guesses: [], status: "playing", remaining: 10 };
  let searchTimer = null;
  let createTimer = null;
  let selectedCreateId = null;
  let refreshDeadlineMs = 0;

  const el = (id) => document.getElementById(id);

  function formatHMS(totalSec) {
    const t = Math.max(0, Math.floor(totalSec));
    const h = Math.floor(t / 3600);
    const m = Math.floor((t % 3600) / 60);
    const s = t % 60;
    return [h, m, s].map((n) => String(n).padStart(2, "0")).join(":");
  }

  function syncRefreshDeadline(sec) {
    if (typeof sec === "number" && sec >= 0) {
      refreshDeadlineMs = Date.now() + sec * 1000;
    }
  }

  function tickRefresh() {
    const line = el("pgRefreshText");
    if (!line) return;
    const leftSec = Math.max(0, Math.floor((refreshDeadlineMs - Date.now()) / 1000));
    if (leftSec <= 0) {
      line.textContent = "Günlük oyuncu yenilendi; yeni gün için sayfayı yenileyin.";
      return;
    }
    line.textContent = `Günlük oyuncunun yenilenmesine: ${formatHMS(leftSec)}`;
  }

  function showHome() {
    el("pgHome").classList.remove("hidden");
    el("pgGame").classList.add("hidden");
  }

  function showGame() {
    el("pgHome").classList.add("hidden");
    el("pgGame").classList.remove("hidden");
  }

  async function fetchState() {
    const res = await fetch(apiUrl("api/state"), { credentials: "same-origin" });
    if (!res.ok) throw new Error("state");
    gameState = await res.json();
    syncRefreshDeadline(gameState.seconds_until_refresh);
    tickRefresh();
    renderDots();
    renderGuesses();
    updateAction();
  }

  function renderDots() {
    const box = el("pgDots");
    if (!box) return;
    box.innerHTML = "";
    for (let i = 0; i < 10; i++) {
      const d = document.createElement("div");
      d.className = "dot";
      if (i < gameState.guesses.length) {
        const last = i === gameState.guesses.length - 1;
        const won = last && gameState.status === "won";
        d.classList.add(won ? "correct" : "used");
      }
      box.appendChild(d);
    }
  }

  function hintClass(h) {
    if (!h) return "wrong";
    if (h.result === "correct") return "correct";
    if (h.result === "close") return "close";
    return "wrong";
  }

  function hintArrow(h) {
    if (!h) return "";
    if (h.result === "higher") return "↑";
    if (h.result === "lower") return "↓";
    if (h.result === "close" && h.direction === "higher") return "↑";
    if (h.result === "close" && h.direction === "lower") return "↓";
    return "";
  }

  function posLabel(p) {
    const m = { G: "KL", D: "DF", M: "OS", F: "FW" };
    return m[p] || p || "?";
  }

  function escapeHtml(s) {
    if (s == null) return "";
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function renderGuesses() {
    const container = el("pgGuesses");
    if (!container) return;
    container.innerHTML = "";
    const list = [...gameState.guesses].reverse();
    list.forEach((g) => {
      const p = g.player;
      const h = g.hints || {};
      const card = document.createElement("div");
      card.className = "pg-card";
      const chk = g.is_correct ? " ✓" : "";
      const birthDisp =
        p.birth_year != null && p.birth_year !== "" ? String(p.birth_year) : "?";
      card.innerHTML = `
        <div class="pg-card-head">${escapeHtml(p.name)}${chk}</div>
        <div class="pg-hint-grid">
          ${cell("Pozisyon", posLabel(p.position), h.position, true)}
          ${cell("G+A", String(p.goals_assists != null ? p.goals_assists : "?"), h.goals_assists)}
          ${cell("Doğum", birthDisp, h.birth_year)}
          ${cell("Ülke", p.nationality || "?", h.nationality)}
          ${cell("Sezon", String(p.seasons_played ?? "?"), h.seasons_played)}
          ${cell("Kulüp", p.top_club_name || "?", h.top_club)}
        </div>`;
      container.appendChild(card);
    });
    const scroll = el("pgGuessesScroll");
    if (scroll) scroll.scrollTop = 0;
  }

  function cell(label, value, hint, noArrow) {
    const cls = hintClass(hint);
    const ar = noArrow ? "" : hintArrow(hint);
    return `<div class="pg-cell">
      <span class="pg-cell-label">${escapeHtml(label)}</span>
      <div class="pg-cell-val ${cls}"><span>${escapeHtml(value)}</span>${ar ? `<span class="pg-arrow">${ar}</span>` : ""}</div>
    </div>`;
  }

  function updateAction() {
    const btn = el("pgActionBtn");
    if (!btn) return;
    if (gameState.status === "won") {
      btn.textContent = "Sonuç";
      btn.onclick = showResult;
    } else if (gameState.status === "lost") {
      btn.textContent = "Cevabı gör";
      btn.onclick = showResult;
    } else {
      btn.textContent = "Tahmin yap";
      btn.onclick = openSearch;
    }
  }

  function openSearch() {
    el("pgSearchPanel").classList.remove("hidden");
    el("pgSearchInput").value = "";
    el("pgSearchResults").innerHTML = "";
    el("pgSearchInput").focus();
  }

  function closeSearch() {
    el("pgSearchPanel").classList.add("hidden");
  }

  async function runSearch(q) {
    const res = await fetch(apiUrl(`api/search?q=${encodeURIComponent(q)}`), {
      credentials: "same-origin",
    });
    if (!res.ok) return;
    const rows = await res.json();
    const ul = el("pgSearchResults");
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
    const data = await res.json();
    if (!res.ok) {
      alert(data.error || "Hata");
      return;
    }
    try {
      await fetchState();
    } catch (e) {
      console.error(e);
    }
    if (gameState.status !== "playing") {
      showResult();
    }
  }

  async function showResult() {
    const res = await fetch(apiUrl("api/answer"), { credentials: "same-origin" });
    const ans = res.ok ? await res.json() : {};
    const title = gameState.status === "won" ? "Kazandın!" : "Bitti";
    const body =
      gameState.status === "won"
        ? `Doğru: ${ans.name || ""}`
        : `Doğru cevap: ${ans.name || "—"}`;
    el("pgResultTitle").textContent = title;
    el("pgResultBody").textContent = body;
    el("pgResultModal").classList.remove("hidden");
  }

  function hideResult() {
    el("pgResultModal").classList.add("hidden");
  }

  function init() {
    el("btnDaily").addEventListener("click", async () => {
      showGame();
      try {
        await fetchState();
      } catch (e) {
        console.error(e);
        alert("Oyun yüklenemedi.");
      }
    });

    el("btnBack").addEventListener("click", () => {
      showHome();
      window.location.href = "/sportsguesser/football/guess/";
    });

    el("pgSearchClose").addEventListener("click", closeSearch);
    el("pgSearchInput").addEventListener("input", () => {
      const q = el("pgSearchInput").value.trim();
      if (searchTimer) clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        if (q.length >= 2) runSearch(q);
        else el("pgSearchResults").innerHTML = "";
      }, 200);
    });

    el("pgResultOk").addEventListener("click", () => {
      hideResult();
    });
    el("pgResultBackdrop").addEventListener("click", hideResult);

    /* Create modal */
    el("btnCreate").addEventListener("click", () => {
      el("pgCreateModal").classList.remove("hidden");
      selectedCreateId = null;
      el("pgCreateInput").value = "";
      el("pgCreateResults").innerHTML = "";
      el("pgCreateLinkWrap").classList.add("hidden");
    });
    el("pgCreateClose").addEventListener("click", () => el("pgCreateModal").classList.add("hidden"));
    el("pgCreateBackdrop").addEventListener("click", () => el("pgCreateModal").classList.add("hidden"));

    el("pgCreateInput").addEventListener("input", () => {
      const q = el("pgCreateInput").value.trim();
      if (createTimer) clearTimeout(createTimer);
      createTimer = setTimeout(async () => {
        if (q.length < 2) {
          el("pgCreateResults").innerHTML = "";
          return;
        }
        const res = await fetch(apiUrl(`api/search?q=${encodeURIComponent(q)}`), {
          credentials: "same-origin",
        });
        if (!res.ok) return;
        const rows = await res.json();
        el("pgCreateResults").innerHTML = rows
          .map(
            (r) =>
              `<li data-id="${r.player_id}"><strong>${escapeHtml(r.name)}</strong><div class="nat">${escapeHtml(r.nationality || "")}</div></li>`
          )
          .join("");
        el("pgCreateResults").querySelectorAll("li").forEach((li) => {
          li.addEventListener("click", () => {
            selectedCreateId = Number(li.dataset.id);
            const base = window.location.origin + "/sportsguesser/football/guess/";
            const link = base + "?player=" + selectedCreateId;
            el("pgCreateLink").value = link;
            el("pgCreateLinkWrap").classList.remove("hidden");
          });
        });
      }, 200);
    });

    el("pgCreateCopy").addEventListener("click", () => {
      const inp = el("pgCreateLink");
      inp.select();
      navigator.clipboard.writeText(inp.value);
    });

    el("pgCreatePlay").addEventListener("click", () => {
      if (!selectedCreateId) return;
      window.location.href = el("pgCreateLink").value;
    });

    setInterval(tickRefresh, 1000);

    const resetBtn = el("pgResetGame");
    if (resetBtn) {
      resetBtn.addEventListener("click", async () => {
        const res = await fetch(apiUrl("api/reset"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: "{}",
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          alert(data.error || "Sıfırlanamadı");
          return;
        }
        gameState = data;
        syncRefreshDeadline(gameState.seconds_until_refresh);
        tickRefresh();
        renderDots();
        renderGuesses();
        updateAction();
        const rm = el("pgResultModal");
        if (rm) rm.classList.add("hidden");
      });
    }

    const revealBtn = el("pgRevealBtn");
    if (revealBtn) {
      revealBtn.addEventListener("click", async () => {
        const res = await fetch(apiUrl("api/reveal-target"), { credentials: "same-origin" });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          alert(data.error || "Cevap alınamadı.");
          return;
        }
        alert(data.name ? `Doğru oyuncu: ${data.name}` : "İsim bulunamadı.");
      });
    }

    const params = new URLSearchParams(window.location.search);
    if (params.get("player")) {
      showGame();
      fetchState()
        .then(() => {
          if (gameState.status !== "playing") showResult();
        })
        .catch(() => alert("Yüklenemedi"));
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
