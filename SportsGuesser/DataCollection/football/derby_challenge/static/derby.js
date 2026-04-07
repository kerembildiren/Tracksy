/**
 * API base: .../sportsguesser/football/derby/ — no ?query on base URL.
 */
function derbyApiRoot() {
  const fromTemplate =
    typeof window.__DERBY_API_ROOT__ === "string" ? window.__DERBY_API_ROOT__.trim() : "";
  if (fromTemplate) {
    return fromTemplate.replace(/\/?$/, "/");
  }
  try {
    const u = new URL(window.location.href);
    u.search = "";
    u.hash = "";
    if (!u.pathname.endsWith("/")) {
      u.pathname += "/";
    }
    return u.href;
  } catch (e) {
    return new URL("/sportsguesser/football/derby/", window.location.origin).href;
  }
}

function apiUrl(path) {
  const rel = path.replace(/^\//, "");
  const base = derbyApiRoot();
  return new URL(rel, base).href;
}

const SUGGEST_MIN = 2;
const KIND_ORDER = { goal: 0, card: 1, sub: 2 };

let state = {
  gameId: null,
  activeInput: null,
  teamHint: { side: null, pages: [], focus: 0, hasMore: false },
};

function el(id) {
  return document.getElementById(id);
}

function show(elm, on) {
  if (!elm) return;
  elm.classList.toggle("hidden", !on);
}

function setMsg(id, text, isErr) {
  const n = el(id);
  if (!n) return;
  n.textContent = text || "";
  n.classList.toggle("err", !!isErr);
}

async function post(path, body) {
  let url;
  try {
    url = apiUrl(path);
  } catch (e) {
    console.error("[Derbi] apiUrl", path, e);
    return { res: { ok: false, status: 0 }, data: { error: "İstek adresi oluşturulamadı" } };
  }
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      credentials: "same-origin",
    });
    let data = {};
    try {
      data = await res.json();
    } catch (_) {
      data = {};
    }
    return { res, data };
  } catch (e) {
    console.error("[Derbi] fetch", url, e);
    return { res: { ok: false, status: 0 }, data: { error: "Ağ hatası" } };
  }
}

function escapeHtml(s) {
  if (!s) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function minuteLabel(obj) {
  const m = obj.minute;
  const add = obj.added_time != null && obj.added_time !== "" ? obj.added_time : null;
  if (add != null && add !== "") return `${m}' +${add}`;
  return `${m}'`;
}

function cardIcon(ct) {
  if (ct === "red") return "🟥";
  if (ct === "yellowRed") return "🟨🟥";
  return "🟨";
}

function isRedLikeCardType(ct) {
  const s = String(ct || "yellow").toLowerCase();
  return s === "red" || s === "yellowred";
}

function sortKeyFor(ev, kind) {
  const m = Number(ev.minute) || 0;
  const add =
    ev.added_time != null && ev.added_time !== "" ? Number(ev.added_time) : 0;
  return m * 10000 + add * 100 + KIND_ORDER[kind];
}

function mergeEvents(ch) {
  const out = [];
  (ch.goals || []).forEach((g) => {
    out.push({ kind: "goal", ...g, _sk: sortKeyFor(g, "goal") });
  });
  (ch.cards || []).forEach((c) => {
    if (!isRedLikeCardType(c.card_type)) return;
    out.push({ kind: "card", ...c, _sk: sortKeyFor(c, "card") });
  });
  out.sort((a, b) => {
    if (a._sk !== b._sk) return a._sk - b._sk;
    const ko = KIND_ORDER[a.kind] - KIND_ORDER[b.kind];
    if (ko !== 0) return ko;
    return (a.idx || 0) - (b.idx || 0);
  });
  return out;
}

function renderMatchBanner(ch) {
  const roundLine = ch.round_label
    ? escapeHtml(ch.round_label)
    : `${Number(ch.round) || 0}. hafta`;
  el("match-banner").innerHTML = `<div class="banner-season-line">${escapeHtml(ch.season_label)} · ${roundLine}</div>`;
  el("name-home-display").textContent = ch.home_team || "";
  el("name-away-display").textContent = ch.away_team || "";
}

function buildTimelineRow(ev) {
  const isHome = ev.is_home;
  const side = isHome ? "home" : "away";
  const row = document.createElement("div");
  row.className = `timeline-row timeline-row--${side}`;
  row.dataset.kind = ev.kind;
  row.dataset.idx = String(ev.idx);

  let icon = "";
  let inner = "";
  if (ev.kind === "goal") {
    icon = "⚽";
    const mask = escapeHtml(ev.name_blank || "—");
    inner = `
      <div class="goal-guess-block">
        <div class="goal-name-mask" aria-hidden="true">${mask}</div>
        <div class="ev-input-wrap">
          <input type="text" class="ev-input ev-input--dashed ev-input--guess" placeholder="Gol atan" autocomplete="off" spellcheck="false" />
          <ul class="suggest-list hidden"></ul>
        </div>
      </div>`;
  } else {
    icon = cardIcon(ev.card_type);
    inner = `
      <div class="ev-input-wrap">
        <input type="text" class="ev-input ev-input--dashed ev-input--guess" placeholder="Kırmızı kart gören" autocomplete="off" spellcheck="false" />
        <ul class="suggest-list hidden"></ul>
      </div>`;
  }

  row.innerHTML = `
    <div class="timeline-pack">
      <span class="ev-kind-icon" aria-hidden="true">${icon}</span>
      <span class="ev-minute">${escapeHtml(minuteLabel(ev))}</span>
      ${inner}
      <div class="ev-actions">
        <button type="button" class="btn-primary btn-sm btn-guess" title="Tahmin (Enter)">✓</button>
        <button type="button" class="btn-ghost btn-sm btn-reveal">İpucu</button>
      </div>
      <span class="ev-reveal"></span>
    </div>`;
  return row;
}

function wireSuggest(input, ul) {
  let t = null;
  input.addEventListener("input", () => {
    clearTimeout(t);
    t = setTimeout(async () => {
      const q = input.value.trim();
      ul.innerHTML = "";
      if (q.length < SUGGEST_MIN) {
        ul.classList.add("hidden");
        return;
      }
      const { res, data } = await post("/api/suggest", { q });
      if (!res.ok) return;
      const items = data.suggestions || [];
      items.forEach((it) => {
        const li = document.createElement("li");
        li.textContent = it.name;
        li.addEventListener("mousedown", (e) => {
          e.preventDefault();
          input.value = it.name;
          ul.classList.add("hidden");
        });
        ul.appendChild(li);
      });
      ul.classList.toggle("hidden", items.length === 0);
    }, 160);
  });
}

function wireRowInputs(row) {
  const kind = row.dataset.kind;
  const wraps = row.querySelectorAll(".ev-input-wrap");
  wraps.forEach((w) => {
    const inp = w.querySelector(".ev-input");
    const ul = w.querySelector(".suggest-list");
    if (inp && ul) wireSuggest(inp, ul);
  });

  const guessBtn = row.querySelector(".btn-guess");
  const revBtn = row.querySelector(".btn-reveal");
  if (guessBtn) guessBtn.addEventListener("click", () => onGuessRow(row));
  if (revBtn) revBtn.addEventListener("click", () => onRevealRow(row));

  row.querySelectorAll(".ev-input--guess").forEach((inp) => {
    inp.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        onGuessRow(row);
      }
    });
  });
}

function closeTeamHintPop() {
  const p = el("team-hint-pop");
  if (p) {
    p.classList.add("hidden");
    p.setAttribute("aria-hidden", "true");
  }
}

function syncTeamHintTrack() {
  const track = el("team-hint-track");
  const th = state.teamHint;
  if (!track) return;
  const n = th.pages.length;
  if (!n) {
    track.style.transform = "";
    return;
  }
  th.focus = Math.max(0, Math.min(n - 1, th.focus));
  track.style.transform = `translateX(-${th.focus * 100}%)`;
  const prev = el("team-hint-prev");
  const nextNav = el("team-hint-next-nav");
  const nextRev = el("team-hint-next-reveal");
  if (prev) prev.disabled = th.focus <= 0;
  if (nextNav) nextNav.disabled = th.focus >= n - 1;
  if (nextRev) nextRev.disabled = !th.hasMore;
}

function renderTeamHintPages() {
  const track = el("team-hint-track");
  if (!track) return;
  const th = state.teamHint;
  track.innerHTML = "";
  if (!th.pages.length) {
    const page = document.createElement("div");
    page.className = "hint-carousel-page";
    page.innerHTML =
      '<p class="derby-hint-empty">Bu takım için sarı kart veya değişiklik kaydı yok.</p>';
    track.appendChild(page);
    track.style.transform = "";
    const nextRev = el("team-hint-next-reveal");
    if (nextRev) nextRev.disabled = true;
    const prev = el("team-hint-prev");
    const nextNav = el("team-hint-next-nav");
    if (prev) prev.disabled = true;
    if (nextNav) nextNav.disabled = true;
    return;
  }
  th.pages.forEach((text) => {
    const page = document.createElement("div");
    page.className = "hint-carousel-page";
    const p = document.createElement("p");
    p.className = "derby-hint-page-text";
    p.textContent = text;
    page.appendChild(p);
    track.appendChild(page);
  });
  syncTeamHintTrack();
}

function bumpTeamHintFocus(delta) {
  const th = state.teamHint;
  if (!th.pages.length) return;
  th.focus += delta;
  syncTeamHintTrack();
}

async function openTeamHint(side) {
  if (!state.gameId) return;
  let { res, data } = await post("/api/team-hint", {
    game_id: state.gameId,
    side,
    advance: false,
  });
  if (!res.ok) {
    setMsg("msg-global", (data && data.error) || "İpucu yüklenemedi", true);
    return;
  }
  if (data.ok === false && data.error) {
    setMsg("msg-global", data.error, true);
    return;
  }
  let pages = data.pages || [];
  const total = typeof data.total === "number" ? data.total : 0;
  if (pages.length === 0 && total > 0) {
    ({ res, data } = await post("/api/team-hint", {
      game_id: state.gameId,
      side,
      advance: true,
    }));
    if (!res.ok) {
      setMsg("msg-global", (data && data.error) || "İpucu alınamadı", true);
      return;
    }
    if (data.ok === false) {
      setMsg("msg-global", (data && data.error) || "İpucu alınamadı", true);
      return;
    }
    pages = data.pages || [];
  }
  const titleEl = side === "home" ? el("name-home-display") : el("name-away-display");
  const tname = titleEl ? titleEl.textContent.trim() : side;
  el("team-hint-title").textContent = `${tname} — ipuçları`;
  state.teamHint = {
    side,
    pages,
    focus:
      typeof data.focus === "number"
        ? data.focus
        : Math.max(0, pages.length - 1),
    hasMore: !!data.has_more,
  };
  renderTeamHintPages();
  const pop = el("team-hint-pop");
  if (pop) {
    pop.classList.remove("hidden");
    pop.setAttribute("aria-hidden", "false");
  }
}

async function onTeamHintNextReveal() {
  if (!state.gameId || !state.teamHint.side) return;
  const { res, data } = await post("/api/team-hint", {
    game_id: state.gameId,
    side: state.teamHint.side,
    advance: true,
  });
  if (!res.ok) return;
  if (data.ok === false) {
    setMsg("msg-global", data.error || "İpucu kalmadı", true);
    state.teamHint.hasMore = false;
    const nr = el("team-hint-next-reveal");
    if (nr) nr.disabled = true;
    return;
  }
  state.teamHint.pages = data.pages || [];
  state.teamHint.focus =
    typeof data.focus === "number"
      ? data.focus
      : Math.max(0, state.teamHint.pages.length - 1);
  state.teamHint.hasMore = !!data.has_more;
  renderTeamHintPages();
}

function wireTeamHintUi() {
  const pop = el("team-hint-pop");
  const closeB = el("team-hint-close");
  const prev = el("team-hint-prev");
  const nextNav = el("team-hint-next-nav");
  const nextRev = el("team-hint-next-reveal");
  const bh = el("btn-hint-home");
  const ba = el("btn-hint-away");
  const vp = el("team-hint-viewport");

  if (bh) {
    bh.addEventListener("click", (e) => {
      e.preventDefault();
      openTeamHint("home");
    });
  }
  if (ba) {
    ba.addEventListener("click", (e) => {
      e.preventDefault();
      openTeamHint("away");
    });
  }
  if (closeB) closeB.addEventListener("click", () => closeTeamHintPop());
  if (pop) {
    pop.addEventListener("click", (e) => {
      if (e.target === pop) closeTeamHintPop();
    });
  }
  if (prev) prev.addEventListener("click", () => bumpTeamHintFocus(-1));
  if (nextNav) nextNav.addEventListener("click", () => bumpTeamHintFocus(1));
  if (nextRev) nextRev.addEventListener("click", () => onTeamHintNextReveal());

  if (vp) {
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
        if (dx < 0) bumpTeamHintFocus(1);
        else bumpTeamHintFocus(-1);
      },
      { passive: true }
    );
  }
}

function unlockEventsPhase() {
  const ph = el("events-phase");
  if (!ph) return;
  ph.classList.remove("hidden");
}

function wireGame(ch) {
  const list = el("timeline-list");
  const empty = el("timeline-empty");
  list.innerHTML = "";
  show(empty, false);

  const merged = mergeEvents(ch);
  if (merged.length === 0) {
    show(empty, true);
  }
  merged.forEach((ev) => {
    list.appendChild(buildTimelineRow(ev));
  });

  list.querySelectorAll(".timeline-row").forEach((row) => wireRowInputs(row));

  el("btn-guess-score").onclick = onGuessScore;
  el("btn-reveal-score").onclick = onRevealScore;

  const evPh = el("events-phase");
  if (evPh) evPh.classList.add("hidden");
}

async function onGuessScore() {
  if (!state.gameId) return;
  const hs = el("score-home").value;
  const aw = el("score-away").value;
  const { res, data } = await post("/api/guess-score", {
    game_id: state.gameId,
    home_score: hs,
    away_score: aw,
  });
  if (!res.ok) {
    setMsg("msg-score", data.error || "Hata", true);
    return;
  }
  if (data.ok === false) {
    setMsg("msg-score", data.error || "İşlem yapılamadı", true);
    return;
  }
  if (data.correct) setMsg("msg-score", "Doğru.", false);
  else setMsg("msg-score", "Yanlış skor, tekrar deneyin.", true);
  if (data.correct) {
    unlockEventsPhase();
  }
  await checkAutoDone();
}

async function onRevealScore() {
  if (!state.gameId) return;
  const { res, data } = await post("/api/reveal", { game_id: state.gameId, kind: "score" });
  if (!res.ok) return;
  setMsg(
    "msg-score",
    `Skor: ${data.home_score} — ${data.away_score} (ipucu ile açıldı)`,
    false
  );
  el("score-home").value = data.home_score;
  el("score-away").value = data.away_score;
  el("score-home").disabled = true;
  el("score-away").disabled = true;
  el("btn-guess-score").disabled = true;
  el("btn-reveal-score").disabled = true;
  unlockEventsPhase();
  await checkAutoDone();
}

async function onGuessRow(row) {
  const kind = row.dataset.kind;
  const idx = parseInt(row.dataset.idx, 10);
  if (!state.gameId) return;
  let path = "";
  let body = { game_id: state.gameId, idx };
  if (kind === "goal") {
    path = "/api/guess-goal";
    body.name = row.querySelector(".ev-input--guess")?.value || "";
  } else if (kind === "card") {
    path = "/api/guess-card";
    body.name = row.querySelector(".ev-input--guess")?.value || "";
  }
  if (!path) return;
  const { res, data } = await post(path, body);
  const rev = row.querySelector(".ev-reveal");
  if (!rev) return;
  if (!res.ok) {
    rev.textContent = data.error || "";
    return;
  }
  if (data.ok === false) {
    rev.textContent = data.error || "";
    return;
  }
  if (data.correct) rev.textContent = "Doğru";
  else rev.textContent = "Yanlış";
  await checkAutoDone();
}

async function onRevealRow(row) {
  const kind = row.dataset.kind;
  const idx = parseInt(row.dataset.idx, 10);
  if (!state.gameId) return;
  const rev = row.querySelector(".ev-reveal");
  const { res, data } = await post("/api/reveal", {
    game_id: state.gameId,
    kind: kind === "goal" ? "goal" : kind === "card" ? "card" : "sub",
    idx,
  });
  if (!res.ok) {
    if (rev) rev.textContent = (data && data.error) || "";
    return;
  }
  if (data.kind === "goal") rev.textContent = data.scorer;
  else if (data.kind === "card") rev.textContent = data.player;
  else rev.textContent = `Çıkan: ${data.player_out} → Giren: ${data.player_in}`;
  row.querySelectorAll(".ev-input").forEach((i) => {
    i.disabled = true;
  });
  row.querySelector(".btn-guess").disabled = true;
  const br = row.querySelector(".btn-reveal");
  if (br) br.disabled = true;
  await checkAutoDone();
}

async function checkAutoDone() {
  if (!state.gameId) return;
  const { res, data } = await post("/api/status", { game_id: state.gameId });
  if (res.ok && data.done) {
    await doFinish();
  }
}

async function doFinish() {
  if (!state.gameId) return;
  await post("/api/finish", { game_id: state.gameId });
  state.gameId = null;
  show(el("panel-game"), false);
  show(el("panel-empty"), false);
  show(el("panel-result"), true);
  const rs = el("result-summary");
  if (rs) rs.textContent = "Skor, goller ve kırmızı kartlar tamamlandı.";
}

async function newGame() {
  setMsg("msg-global", "");
  show(el("panel-result"), false);
  show(el("panel-empty"), false);
  try {
    const { res, data } = await post("/api/new-game", {});
    if (!res.ok || !data || !data.game_id) {
      setMsg("msg-global", (data && data.error) || "Maç yüklenemedi", true);
      show(el("panel-empty"), true);
      return;
    }
    state.gameId = data.game_id;
    closeTeamHintPop();
    el("score-home").value = "";
    el("score-away").value = "";
    el("score-home").disabled = false;
    el("score-away").disabled = false;
    el("btn-guess-score").disabled = false;
    el("btn-reveal-score").disabled = false;
    setMsg("msg-score", "");
    renderMatchBanner(data);
    wireGame(data);
    show(el("panel-game"), true);
  } catch (e) {
    console.error(e);
    setMsg("msg-global", "Bağlantı hatası — sayfayı yenileyin.", true);
    show(el("panel-empty"), true);
  }
}

async function derbyFinishFromToolbar() {
  if (!state.gameId) return;
  await doFinish();
}

function initDerbyUi() {
  window.__derbyNewGame = newGame;
  window.__derbyFinishGame = derbyFinishFromToolbar;

  const n1 = el("btn-new-match");
  const n2 = el("btn-after");
  const fin = el("btn-finish");
  if (n1) {
    n1.addEventListener("click", (e) => {
      e.preventDefault();
      newGame();
    });
  }
  if (n2) {
    n2.addEventListener("click", (e) => {
      e.preventDefault();
      newGame();
    });
  }
  if (fin) {
    fin.addEventListener("click", (e) => {
      e.preventDefault();
      derbyFinishFromToolbar();
    });
  }

  wireTeamHintUi();

  show(el("panel-game"), false);
  show(el("panel-result"), false);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initDerbyUi);
} else {
  initDerbyUi();
}
