/**
 * API adresleri: önce Flask'ın __DERBY_API_ROOT__ (tam URL, sonda /) ile.
 * Yoksa sayfa URL’sini dizin olarak normalize eder.
 * Not: new URL('api/x', 'http://host/.../derby') son segment dosya sayılır → yanlış yol;
 * bu yüzden base her zaman .../derby/ ile biter.
 */
function derbyApiRoot() {
  const ex = typeof window.__DERBY_API_ROOT__ === "string" ? window.__DERBY_API_ROOT__.trim() : "";
  if (ex) {
    return ex.replace(/\/?$/, "/");
  }
  try {
    const u = new URL(window.location.href);
    if (!u.pathname.endsWith("/")) {
      u.pathname += "/";
    }
    return u.href;
  } catch (e) {
    return window.location.origin + "/";
  }
}

function apiUrl(path) {
  const rel = path.replace(/^\//, "");
  const base = derbyApiRoot();
  return new URL(rel, base).href;
}

const SUGGEST_MIN = 2;

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

function renderMatchBanner(ch) {
  el("match-banner").innerHTML = `
    <div class="banner-season">${escapeHtml(ch.season_label)} · ${ch.round}. hafta</div>
    <div class="banner-teams">
      <span class="banner-home">${escapeHtml(ch.home_team)}</span>
      <span class="banner-vs">vs</span>
      <span class="banner-away">${escapeHtml(ch.away_team)}</span>
    </div>
  `;
}

function escapeHtml(s) {
  if (!s) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function buildGoalRow(ch, g) {
  const side = g.is_home ? "Ev" : "Dep";
  const add = g.added_time != null ? `+${g.added_time}` : "";
  const row = document.createElement("div");
  row.className = "event-row";
  row.dataset.kind = "goal";
  row.dataset.idx = String(g.idx);
  row.innerHTML = `
    <div class="ev-meta">${g.minute}'${add ? " " + add : ""} · ${side}</div>
    <div class="ev-input-wrap">
      <input type="text" class="ev-input" placeholder="Gol atan" autocomplete="off" />
      <ul class="suggest-list hidden"></ul>
    </div>
    <button type="button" class="btn-primary btn-sm btn-guess">Tahmin</button>
    <button type="button" class="btn-ghost btn-sm btn-reveal">İpucu</button>
    <div class="ev-reveal"></div>
  `;
  return row;
}

function buildCardRow(ch, c) {
  const side = c.is_home ? "Ev" : "Dep";
  const ct =
    c.card_type === "yellowRed"
      ? "İkinci sarı"
      : c.card_type === "red"
        ? "Kırmızı"
        : "Sarı";
  const add = c.added_time != null ? `+${c.added_time}` : "";
  const row = document.createElement("div");
  row.className = "event-row";
  row.dataset.kind = "card";
  row.dataset.idx = String(c.idx);
  row.innerHTML = `
    <div class="ev-meta">${c.minute}'${add ? " " + add : ""} · ${ct} · ${side}</div>
    <div class="ev-input-wrap">
      <input type="text" class="ev-input" placeholder="Oyuncu" autocomplete="off" />
      <ul class="suggest-list hidden"></ul>
    </div>
    <button type="button" class="btn-primary btn-sm btn-guess">Tahmin</button>
    <button type="button" class="btn-ghost btn-sm btn-reveal">İpucu</button>
    <div class="ev-reveal"></div>
  `;
  return row;
}

function buildSubRow(ch, s) {
  const side = s.is_home ? "Ev" : "Dep";
  const row = document.createElement("div");
  row.className = "event-row event-row-sub";
  row.dataset.kind = "sub";
  row.dataset.idx = String(s.idx);
  row.innerHTML = `
    <div class="ev-meta">${s.minute}' · ${side}</div>
    <div class="sub-inputs">
      <div class="ev-input-wrap">
        <input type="text" class="ev-input ev-out" placeholder="Çıkan" autocomplete="off" />
        <ul class="suggest-list hidden"></ul>
      </div>
      <div class="ev-input-wrap">
        <input type="text" class="ev-input ev-in" placeholder="Giren" autocomplete="off" />
        <ul class="suggest-list hidden"></ul>
      </div>
    </div>
    <button type="button" class="btn-primary btn-sm btn-guess">Tahmin</button>
    <button type="button" class="btn-ghost btn-sm btn-reveal">İpucu</button>
    <div class="ev-reveal"></div>
  `;
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
        li.addEventListener("click", () => {
          input.value = it.name;
          ul.classList.add("hidden");
        });
        ul.appendChild(li);
      });
      ul.classList.toggle("hidden", items.length === 0);
    }, 160);
  });
}

function wireGame(ch) {
  const gl = el("goals-list");
  const cl = el("cards-list");
  const sl = el("subs-list");
  gl.innerHTML = "";
  cl.innerHTML = "";
  sl.innerHTML = "";

  const goals = Array.isArray(ch.goals) ? ch.goals : [];
  const cards = Array.isArray(ch.cards) ? ch.cards : [];
  const subs = Array.isArray(ch.subs) ? ch.subs : [];

  goals.forEach((g) => {
    const row = buildGoalRow(ch, g);
    gl.appendChild(row);
    const inp = row.querySelector(".ev-input");
    const ul = row.querySelector(".suggest-list");
    wireSuggest(inp, ul);
  });
  cards.forEach((c) => {
    const row = buildCardRow(ch, c);
    cl.appendChild(row);
    const inp = row.querySelector(".ev-input");
    const ul = row.querySelector(".suggest-list");
    wireSuggest(inp, ul);
  });
  subs.forEach((s) => {
    const row = buildSubRow(ch, s);
    sl.appendChild(row);
    row.querySelectorAll(".ev-input-wrap").forEach((w) => {
      wireSuggest(w.querySelector(".ev-input"), w.querySelector(".suggest-list"));
    });
  });

  document.querySelectorAll("#panel-game .event-row").forEach((row) => {
    row.querySelector(".btn-guess").addEventListener("click", () => onGuessRow(row));
    row.querySelector(".btn-reveal").addEventListener("click", () => onRevealRow(row));
  });

  el("btn-guess-score").onclick = onGuessScore;
  el("btn-reveal-score").onclick = onRevealScore;
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
    body.name = row.querySelector(".ev-input").value;
  } else if (kind === "card") {
    path = "/api/guess-card";
    body.name = row.querySelector(".ev-input").value;
  } else if (kind === "sub") {
    path = "/api/guess-sub";
    body.player_out = row.querySelector(".ev-out").value;
    body.player_in = row.querySelector(".ev-in").value;
  }
  const { res, data } = await post(path, body);
  const rev = row.querySelector(".ev-reveal");
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
  const { res, data } = await post("/api/reveal", {
    game_id: state.gameId,
    kind: kind === "goal" ? "goal" : kind === "card" ? "card" : "sub",
    idx,
  });
  if (!res.ok) return;
  const rev = row.querySelector(".ev-reveal");
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
  show(el("panel-game"), false);
  show(el("panel-result"), false);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initDerbyUi);
} else {
  initDerbyUi();
}
</think>


<｜tool▁calls▁begin｜><｜tool▁call▁begin｜>
Read