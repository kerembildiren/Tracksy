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

function updatePoints(p) {
  el("points-total").textContent = `Puan: ${p}`;
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
    out.push({ kind: "card", ...c, _sk: sortKeyFor(c, "card") });
  });
  (ch.subs || []).forEach((s) => {
    out.push({ kind: "sub", ...s, _sk: sortKeyFor(s, "sub") });
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
    inner = `
      <div class="ev-input-wrap">
        <input type="text" class="ev-input ev-input--dashed ev-input--guess" placeholder="Gol atan" autocomplete="off" spellcheck="false" />
        <ul class="suggest-list hidden"></ul>
      </div>`;
  } else if (ev.kind === "card") {
    icon = cardIcon(ev.card_type);
    inner = `
      <div class="ev-input-wrap">
        <input type="text" class="ev-input ev-input--dashed ev-input--guess" placeholder="Kart gören" autocomplete="off" spellcheck="false" />
        <ul class="suggest-list hidden"></ul>
      </div>`;
  } else {
    icon = "🔁";
    inner = `
      <div class="sub-pair">
        <div class="ev-input-wrap">
          <input type="text" class="ev-input ev-input--dashed ev-out" placeholder="Çıkan" autocomplete="off" spellcheck="false" />
          <ul class="suggest-list hidden"></ul>
        </div>
        <div class="ev-input-wrap">
          <input type="text" class="ev-input ev-input--dashed ev-in" placeholder="Giren" autocomplete="off" spellcheck="false" />
          <ul class="suggest-list hidden"></ul>
        </div>
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

  row.querySelectorAll(".ev-input--guess, .ev-out, .ev-in").forEach((inp) => {
    inp.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        onGuessRow(row);
      }
    });
  });
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
  if (data.points) setMsg("msg-score", `Doğru! +${data.points} puan`, false);
  else if (data.correct) setMsg("msg-score", "Doğru.", false);
  else setMsg("msg-score", "Yanlış skor, tekrar deneyin.", true);
  updatePoints(data.total_points ?? 0);
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
    `Skor: ${data.home_score} — ${data.away_score} (ipucu — bu bölüm için puan yok)`,
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
  } else if (kind === "sub") {
    path = "/api/guess-sub";
    body.player_out = row.querySelector(".ev-out")?.value || "";
    body.player_in = row.querySelector(".ev-in")?.value || "";
  }
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
  if (data.points > 0) rev.textContent = `+${data.points} puan`;
  else if (data.correct) rev.textContent = "Doğru";
  else rev.textContent = kind === "sub" && !data.correct ? "En az biri yanlış" : "Yanlış";
  updatePoints(data.total_points ?? 0);
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
    await doFinish(data.total_points);
  }
}

async function doFinish(knownTotal) {
  if (!state.gameId) return;
  const { res, data } = await post("/api/finish", { game_id: state.gameId });
  const total = res.ok ? data.total_points : knownTotal;
  state.gameId = null;
  show(el("panel-game"), false);
  show(el("panel-empty"), false);
  show(el("panel-result"), true);
  el("result-points").textContent = `Toplam: ${total} puan`;
  updatePoints(total);
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
    updatePoints(0);
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
  const { res, data } = await post("/api/status", { game_id: state.gameId });
  const tp = res.ok ? data.total_points : 0;
  await doFinish(tp);
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

  show(el("panel-game"), false);
  show(el("panel-result"), false);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initDerbyUi);
} else {
  initDerbyUi();
}
