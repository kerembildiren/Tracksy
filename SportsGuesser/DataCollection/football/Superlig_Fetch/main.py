"""
Trendyol Süper Lig API — sofascore-wrapper 1.1.1
League (unique tournament) ID: 52

Startup (Windows):
    uvicorn main:app --loop asyncio
"""

import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.openapi.docs import get_swagger_ui_html
from sofascore_wrapper.api import SofascoreAPI
from sofascore_wrapper.league import League
from sofascore_wrapper.team import Team
from sofascore_wrapper.match import Match
from sofascore_wrapper.player import Player
from sofascore_wrapper.search import Search

LEAGUE_ID = 52  # Trendyol Süper Lig

# Catogarical explanions for API documentation
tags_metadata = [
    {"name": "Genel", "description": "Sezon bilgileri ve temel sorgular."},
    {"name": "Lig", "description": "Puan durumu, istatistikler ve lig genel verileri."},
    {"name": "Fikstür", "description": "Geçmiş, gelecek ve canlı maç sonuçları."},
    {"name": "TOTW", "description": "Haftanın 11'i (Team of the Week) verileri."},
    {"name": "Maç", "description": "Maç detayları, istatistikler ve canlı anlatım."},
    {"name": "Takım", "description": "Takım profilleri, kadrolar ve transferler."},
    {"name": "Oyuncu", "description": "Oyuncu özellikleri, istatistikleri ve geçmişi."},
    {"name": "Arama", "description": "Sistem genelinde takım, oyuncu ve maç arama."},
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(
    title="Trendyol Süper Lig API",
    description="""
**sofascore-wrapper 1.1.1 tabanlı Süper Lig verisi.**

""",
    version="1.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
    docs_url=None,  # Varsayılanı kapattık, custom UI kullanıyoruz
    redoc_url=None  # ReDoc tamamen iptal edildi
)

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css",
        # DefaultModelsExpandDepth: -1 parametresi en alttaki kalabalık "Models" kısmını gizler.
        swagger_ui_parameters={"defaultModelsExpandDepth": -1, "displayRequestDuration": True} 
    )

# ══════════════════════════════════════════════════════════════════════════════
# HELPFUL METHODS
# ══════════════════════════════════════════════════════════════════════════════
async def resolve_season(api: SofascoreAPI, season_id: Optional[int]) -> int:
    if season_id is not None:
        return season_id
    season = await League(api, LEAGUE_ID).current_season()
    return season["id"]

# ══════════════════════════════════════════════════════════════════════════════
# ANA SAYFA (ROOT DASHBOARD)
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/", tags=["Genel"], response_class=HTMLResponse)
async def root():
    # Homepage styled with Tailwind CSS for a modern look (ReDoc removed, Swagger centered)
    html_content = """
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Trendyol Süper Lig API</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            body { background-color: #0f172a; color: #f8fafc; font-family: 'Inter', sans-serif; }
            .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); }
        </style>
    </head>
    <body class="min-h-screen flex items-center justify-center p-6">
        <div class="glass max-w-2xl w-full rounded-2xl shadow-2xl p-10 transform transition-all hover:scale-[1.01]">
            <div class="flex items-center justify-between mb-8 border-b border-slate-700 pb-6">
                <div>
                    <h1 class="text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-cyan-500">
                        Trendyol Süper Lig API
                    </h1>
                    <p class="text-slate-400 mt-2">v1.0 • Powered by sofascore-wrapper</p>
                </div>
                <div class="text-6xl">⚽</div>
            </div>
            
            <div class="flex flex-col items-center mb-8">
                <div class="bg-slate-800 rounded-xl p-8 border border-slate-700 w-full text-center">
                    <h3 class="text-2xl font-bold mb-3 text-emerald-400">Geliştirici Arayüzü</h3>
                    <p class="text-slate-300 mb-6 text-md">Tüm endpoint'leri test etmek ve interaktif API dokümantasyonunu incelemek için Swagger UI kullanın.</p>
                    <a href="/docs" class="inline-block bg-emerald-500 hover:bg-emerald-400 text-slate-900 font-bold py-3 px-8 rounded-lg transition-all duration-300 shadow-[0_0_15px_rgba(16,185,129,0.5)] hover:shadow-[0_0_25px_rgba(16,185,129,0.8)]">
                        Swagger Dokümantasyonuna Git 🚀
                    </a>
                </div>
            </div>
            
            <div class="bg-slate-900 rounded-xl p-4 text-sm text-slate-400 text-center font-mono border border-slate-800">
                💡 İpucu: Çoğu sorgu için önce <span class="text-cyan-400">/seasons</span> endpoint'inden sezon ID'sini almayı unutmayın.
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)

@app.get("/seasons", tags=["Genel"])
async def seasons():
    api = SofascoreAPI()
    try:
        data = await League(api, LEAGUE_ID).get_seasons()
        return {"seasons": data}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/season/current", tags=["Genel"])
async def current_season():
    api = SofascoreAPI()
    try:
        return await League(api, LEAGUE_ID).current_season()
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

# ══════════════════════════════════════════════════════════════════════════════
# LEAGUE
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/standings", tags=["Lig"])
async def standings(season_id: Optional[int] = Query(None, description="Sezon ID (boş = mevcut sezon)")):
    api = SofascoreAPI()
    try:
        sid = await resolve_season(api, season_id)
        return await League(api, LEAGUE_ID).standings(sid)
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/standings/home", tags=["Lig"])
async def standings_home(season_id: Optional[int] = Query(None, description="Sezon ID")):
    api = SofascoreAPI()
    try:
        sid = await resolve_season(api, season_id)
        return await League(api, LEAGUE_ID).standings_home(sid)
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/standings/away", tags=["Lig"])
async def standings_away(season_id: Optional[int] = Query(None, description="Sezon ID")):
    api = SofascoreAPI()
    try:
        sid = await resolve_season(api, season_id)
        return await League(api, LEAGUE_ID).standings_away(sid)
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/rounds", tags=["Lig"])
async def rounds(season_id: Optional[int] = Query(None, description="Sezon ID")):
    api = SofascoreAPI()
    try:
        sid = await resolve_season(api, season_id)
        return await League(api, LEAGUE_ID).rounds(sid)
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/info", tags=["Lig"])
async def league_info(season_id: Optional[int] = Query(None, description="Sezon ID")):
    api = SofascoreAPI()
    try:
        sid = await resolve_season(api, season_id)
        return await League(api, LEAGUE_ID).get_info(sid)
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/top-players", tags=["Lig"])
async def top_players(season_id: Optional[int] = Query(None, description="Sezon ID")):
    api = SofascoreAPI()
    try:
        sid = await resolve_season(api, season_id)
        return await League(api, LEAGUE_ID).top_players(sid)
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/top-teams", tags=["Lig"])
async def top_teams(season_id: Optional[int] = Query(None, description="Sezon ID")):
    api = SofascoreAPI()
    try:
        sid = await resolve_season(api, season_id)
        return await League(api, LEAGUE_ID).top_teams(sid)
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/highlights", tags=["Lig"])
async def highlights():
    api = SofascoreAPI()
    try:
        return await League(api, LEAGUE_ID).get_latest_highlights()
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/player-of-season", tags=["Lig"])
async def player_of_season(season_id: Optional[int] = Query(None, description="Sezon ID")):
    api = SofascoreAPI()
    try:
        sid = await resolve_season(api, season_id)
        return await League(api, LEAGUE_ID).player_of_the_season(sid)
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

# ══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/fixtures", tags=["Fikstür"])
async def fixtures(hafta: int = Query(..., description="Hafta numarası"), season_id: Optional[int] = Query(None, description="Sezon ID")):
    api = SofascoreAPI()
    try:
        sid = await resolve_season(api, season_id)
        return await League(api, LEAGUE_ID).fixtures(sid, hafta)
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/fixtures/all", tags=["Fikstür"])
async def all_fixtures(hafta: int = Query(..., description="Hafta numarası"), season_id: Optional[int] = Query(None, description="Sezon ID")):
    api = SofascoreAPI()
    try:
        sid = await resolve_season(api, season_id)
        return await League(api, LEAGUE_ID).league_fixtures_per_round(sid, hafta)
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/fixtures/last", tags=["Fikstür"])
async def last_fixtures():
    api = SofascoreAPI()
    try:
        data = await League(api, LEAGUE_ID).last_fixtures()
        return {"events": data}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/fixtures/next", tags=["Fikstür"])
async def next_fixtures():
    api = SofascoreAPI()
    try:
        data = await League(api, LEAGUE_ID).next_fixtures()
        return {"events": data}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/live", tags=["Fikstür"])
async def live_matches():
    api = SofascoreAPI()
    try:
        data = await Match(api).live_games()
        events = data.get("events", [])
        superlig = [e for e in events if e.get("tournament", {}).get("uniqueTournament", {}).get("id") == LEAGUE_ID]
        return {"count": len(superlig), "events": superlig}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

# ══════════════════════════════════════════════════════════════════════════════
# (TOTW)
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/totw/rounds", tags=["TOTW"])
async def totw_rounds(season_id: Optional[int] = Query(None, description="Sezon ID")):
    api = SofascoreAPI()
    try:
        sid = await resolve_season(api, season_id)
        return await League(api, LEAGUE_ID).totw_rounds(sid)
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/totw", tags=["TOTW"])
async def team_of_the_week(round_id: Optional[int] = Query(None, description="roundId"), season_id: Optional[int] = Query(None, description="Sezon ID")):
    api = SofascoreAPI()
    try:
        sid = await resolve_season(api, season_id)
        league = League(api, LEAGUE_ID)
        if round_id is None:
            rounds_data = await league.totw_rounds(sid)
            all_rounds = rounds_data.get("rounds", [])
            if not all_rounds:
                raise HTTPException(404, "Bu sezon için TOTW verisi bulunamadı.")
            round_id = all_rounds[-1]["roundId"]
        return await league.totw(sid, round_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

# ══════════════════════════════════════════════════════════════════════════════
# MATCH
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/match/{match_id}", tags=["Maç"])
async def match_detail(match_id: int):
    api = SofascoreAPI()
    try:
        m = Match(api, match_id)
        info, home_lu, away_lu, incidents, stats = await asyncio.gather(
            m.get_match(), m.lineups_home(), m.lineups_away(), m.incidents(), m.stats(), return_exceptions=True
        )
        return {
            "match": info if not isinstance(info, Exception) else {"error": str(info)},
            "lineups": {
                "home": home_lu if not isinstance(home_lu, Exception) else None,
                "away": away_lu if not isinstance(away_lu, Exception) else None,
            },
            "incidents": incidents if not isinstance(incidents, Exception) else None,
            "statistics": stats if not isinstance(stats, Exception) else None,
        }
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/match/{match_id}/extra", tags=["Maç"])
async def match_extra(match_id: int):
    api = SofascoreAPI()
    try:
        m = Match(api, match_id)
        results = await asyncio.gather(
            m.h2h(), m.shotmap(), m.motm(), m.win_probability(), m.votes(), m.pre_match_form(), return_exceptions=True
        )
        keys = ["h2h", "shotmap", "motm", "win_probability", "votes", "pre_match_form"]
        return {k: (v if not isinstance(v, Exception) else None) for k, v in zip(keys, results)}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/match/{match_id}/commentary", tags=["Maç"])
async def match_commentary(match_id: int):
    api = SofascoreAPI()
    try:
        return await Match(api, match_id).commentary()
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

# ══════════════════════════════════════════════════════════════════════════════
# TEAM
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/team/{team_id}", tags=["Takım"])
async def team_info(team_id: int):
    api = SofascoreAPI()
    try:
        return await Team(api, team_id).get_team()
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/team/{team_id}/squad", tags=["Takım"])
async def team_squad(team_id: int):
    api = SofascoreAPI()
    try:
        return await Team(api, team_id).squad()
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/team/{team_id}/stats", tags=["Takım"])
async def team_stats(team_id: int, season_id: Optional[int] = Query(None, description="Sezon ID")):
    api = SofascoreAPI()
    try:
        sid = await resolve_season(api, season_id)
        return await Team(api, team_id).league_stats(LEAGUE_ID, sid)
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/team/{team_id}/top-players", tags=["Takım"])
async def team_top_players(team_id: int, season_id: Optional[int] = Query(None, description="Sezon ID")):
    api = SofascoreAPI()
    try:
        sid = await resolve_season(api, season_id)
        return await Team(api, team_id).top_players(LEAGUE_ID, sid)
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/team/{team_id}/fixtures/last", tags=["Takım"])
async def team_last_fixtures(team_id: int):
    api = SofascoreAPI()
    try:
        data = await Team(api, team_id).last_fixtures()
        return {"events": data}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/team/{team_id}/fixtures/next", tags=["Takım"])
async def team_next_fixtures(team_id: int):
    api = SofascoreAPI()
    try:
        data = await Team(api, team_id).next_fixtures()
        return {"events": data}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/team/{team_id}/transfers/in", tags=["Takım"])
async def team_transfers_in(team_id: int):
    api = SofascoreAPI()
    try:
        data = await Team(api, team_id).transfers_in()
        return {"transfers": data}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/team/{team_id}/transfers/out", tags=["Takım"])
async def team_transfers_out(team_id: int):
    api = SofascoreAPI()
    try:
        data = await Team(api, team_id).transfers_out()
        return {"transfers": data}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

# ══════════════════════════════════════════════════════════════════════════════
# PLAYER
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/player/{player_id}", tags=["Oyuncu"])
async def player_info(player_id: int):
    api = SofascoreAPI()
    try:
        return await Player(api, player_id).get_player()
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/player/{player_id}/stats", tags=["Oyuncu"])
async def player_stats(player_id: int, season_id: Optional[int] = Query(None, description="Sezon ID")):
    api = SofascoreAPI()
    try:
        sid = await resolve_season(api, season_id)
        return await Player(api, player_id).league_stats(LEAGUE_ID, sid)
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/player/{player_id}/attributes", tags=["Oyuncu"])
async def player_attributes(player_id: int):
    api = SofascoreAPI()
    try:
        return await Player(api, player_id).attributes()
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/player/{player_id}/transfers", tags=["Oyuncu"])
async def player_transfers(player_id: int):
    api = SofascoreAPI()
    try:
        return await Player(api, player_id).transfer_history()
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

@app.get("/player/{player_id}/fixtures/last", tags=["Oyuncu"])
async def player_last_fixtures(player_id: int):
    api = SofascoreAPI()
    try:
        data = await Player(api, player_id).last_fixtures()
        return {"events": data}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

# ══════════════════════════════════════════════════════════════════════════════
# QUICK SEARCH
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/search", tags=["Arama"])
async def search(q: str = Query(..., description="Arama: oyuncu, takım veya maç adı")):
    api = SofascoreAPI()
    try:
        return await Search(api, q).search_all(sport="football")
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await api.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, loop="asyncio")