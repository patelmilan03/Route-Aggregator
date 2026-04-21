from fastapi import FastAPI, HTTPException, status, Depends, Security
from fastapi.security import APIKeyHeader
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
import asyncio
import httpx
from app.schemas import RouteRequest, RouteResponse, WaypointTimeline, WeatherData
from app.services import build_itinerary
from app.config import settings
from app.database import engine, Base, get_db
from app.models import DBRoute, DBWaypoint

# Define the header name we expect
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header == settings.api_key:
        return api_key_header
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Could not validate API Key",
    )

# Create tables on startup. In production, use Alembic for migrations instead.
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title=settings.api_title, version=settings.api_version, lifespan=lifespan)

# --- KEEP-ALIVE DAEMON ---
async def keep_alive():
    url = "https://route-aggregator-api.onrender.com"
    async with httpx.AsyncClient() as client:
        while True:
            await asyncio.sleep(10 * 60)
            try:
                await client.get(url)
                print("Keep-alive ping successful.")
            except Exception as e:
                print(f"Keep-alive ping failed: {e}")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(keep_alive())
# -------------------------

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Logistics & Route Aggregator API</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg:        #080c10;
            --bg-card:   rgba(255,255,255,0.03);
            --border:    rgba(240,165,0,0.15);
            --amber:     #f0a500;
            --amber-dim: rgba(240,165,0,0.12);
            --teal:      #2dd4bf;
            --text:      #e8e0d0;
            --text-muted:#8a8070;
            --red:       #f87171;
        }

        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        html { scroll-behavior: smooth; }

        body {
            background-color: var(--bg);
            color: var(--text);
            font-family: 'DM Sans', sans-serif;
            font-weight: 300;
            min-height: 100vh;
            overflow-x: hidden;
            /* Topographic contour lines via SVG background */
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='400'%3E%3Cellipse cx='200' cy='200' rx='180' ry='120' fill='none' stroke='%23f0a500' stroke-width='0.4' stroke-opacity='0.06'/%3E%3Cellipse cx='200' cy='200' rx='140' ry='90' fill='none' stroke='%23f0a500' stroke-width='0.4' stroke-opacity='0.06'/%3E%3Cellipse cx='200' cy='200' rx='100' ry='62' fill='none' stroke='%23f0a500' stroke-width='0.4' stroke-opacity='0.06'/%3E%3Cellipse cx='200' cy='200' rx='60' ry='36' fill='none' stroke='%23f0a500' stroke-width='0.4' stroke-opacity='0.06'/%3E%3C/svg%3E");
            background-size: 400px 400px;
        }

        /* ── STATUS BAR ── */
        .status-bar {
            position: fixed;
            top: 0; left: 0; right: 0;
            z-index: 100;
            background: rgba(8,12,16,0.85);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 2rem;
            height: 44px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.72rem;
            letter-spacing: 0.08em;
        }
        .status-left { display: flex; align-items: center; gap: 10px; }
        .pulse-dot {
            width: 7px; height: 7px;
            background: var(--teal);
            border-radius: 50%;
            box-shadow: 0 0 0 0 rgba(45,212,191,0.6);
            animation: pulse-ring 2s infinite;
        }
        @keyframes pulse-ring {
            0%   { box-shadow: 0 0 0 0 rgba(45,212,191,0.6); }
            70%  { box-shadow: 0 0 0 7px rgba(45,212,191,0); }
            100% { box-shadow: 0 0 0 0 rgba(45,212,191,0); }
        }
        .status-label { color: var(--teal); text-transform: uppercase; }
        .status-sep { color: var(--text-muted); }
        .status-version { color: var(--text-muted); }
        .status-right { display: flex; align-items: center; gap: 1.5rem; }
        .status-right a {
            color: var(--text-muted);
            text-decoration: none;
            transition: color 0.2s;
            text-transform: uppercase;
        }
        .status-right a:hover { color: var(--amber); }

        /* ── LAYOUT ── */
        .page { max-width: 1080px; margin: 0 auto; padding: 0 2rem; }

        /* ── HERO ── */
        .hero {
            padding: 140px 0 80px;
            position: relative;
            display: flex;
            flex-direction: column;
            align-items: flex-start;
        }
        .radar-wrap {
            position: absolute;
            top: 80px; right: -60px;
            width: 420px; height: 420px;
            pointer-events: none;
            opacity: 0.18;
        }
        .radar-ring {
            position: absolute;
            top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            border-radius: 50%;
            border: 1px solid var(--amber);
            animation: radar-expand 3.5s ease-out infinite;
        }
        .radar-ring:nth-child(1) { width: 60px;  height: 60px;  animation-delay: 0s; }
        .radar-ring:nth-child(2) { width: 130px; height: 130px; animation-delay: 0.6s; }
        .radar-ring:nth-child(3) { width: 220px; height: 220px; animation-delay: 1.2s; }
        .radar-ring:nth-child(4) { width: 330px; height: 330px; animation-delay: 1.8s; }
        .radar-ring:nth-child(5) { width: 420px; height: 420px; animation-delay: 2.4s; }
        @keyframes radar-expand {
            0%   { opacity: 1; transform: translate(-50%,-50%) scale(0.6); }
            100% { opacity: 0; transform: translate(-50%,-50%) scale(1); }
        }

        .hero-eyebrow {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            letter-spacing: 0.18em;
            color: var(--amber);
            text-transform: uppercase;
            margin-bottom: 1.2rem;
            opacity: 0;
            animation: fade-up 0.6s 0.1s ease forwards;
        }
        .hero-title {
            font-family: 'Syne', sans-serif;
            font-weight: 800;
            font-size: clamp(2.4rem, 5vw, 4rem);
            line-height: 1.08;
            letter-spacing: -0.03em;
            margin-bottom: 1.4rem;
            opacity: 0;
            animation: fade-up 0.6s 0.2s ease forwards;
        }
        .hero-title span { color: var(--amber); }

        .hero-desc {
            font-size: 1.05rem;
            color: var(--text-muted);
            max-width: 520px;
            line-height: 1.75;
            margin-bottom: 2rem;
            opacity: 0;
            animation: fade-up 0.6s 0.35s ease forwards;
        }

        .coord-ticker {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.72rem;
            color: rgba(240,165,0,0.4);
            letter-spacing: 0.12em;
            margin-bottom: 2.5rem;
            overflow: hidden;
            white-space: nowrap;
            width: 100%;
            max-width: 520px;
            opacity: 0;
            animation: fade-up 0.6s 0.45s ease forwards;
        }
        .coord-inner {
            display: inline-block;
            animation: ticker 18s linear infinite;
        }
        @keyframes ticker {
            0%   { transform: translateX(0); }
            100% { transform: translateX(-50%); }
        }

        .hero-cta {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            background: var(--amber);
            color: #080c10;
            font-family: 'Syne', sans-serif;
            font-weight: 700;
            font-size: 0.9rem;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            text-decoration: none;
            padding: 14px 32px;
            border-radius: 3px;
            transition: background 0.2s, transform 0.2s;
            opacity: 0;
            animation: fade-up 0.6s 0.55s ease forwards;
        }
        .hero-cta:hover { background: #ffc229; transform: translateY(-2px); }
        .hero-cta svg { flex-shrink: 0; }

        @keyframes fade-up {
            from { opacity: 0; transform: translateY(16px); }
            to   { opacity: 1; transform: translateY(0); }
        }

        /* ── DIVIDER ── */
        .divider {
            border: none;
            border-top: 1px solid var(--border);
            margin: 0;
        }

        /* ── SECTION HEADER ── */
        .section { padding: 72px 0; }
        .section-label {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            letter-spacing: 0.2em;
            color: var(--amber);
            text-transform: uppercase;
            margin-bottom: 0.6rem;
        }
        .section-title {
            font-family: 'Syne', sans-serif;
            font-weight: 700;
            font-size: 1.6rem;
            letter-spacing: -0.02em;
            margin-bottom: 2.5rem;
        }

        /* ── FEATURE CARDS ── */
        .cards-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1px;
            background: var(--border);
            border: 1px solid var(--border);
            border-radius: 4px;
            overflow: hidden;
        }
        .card {
            background: var(--bg-card);
            padding: 1.8rem;
            position: relative;
            transition: background 0.2s, transform 0.2s;
            opacity: 0;
            animation: fade-up 0.5s ease forwards;
        }
        .card:nth-child(1) { animation-delay: 0.05s; }
        .card:nth-child(2) { animation-delay: 0.12s; }
        .card:nth-child(3) { animation-delay: 0.19s; }
        .card:nth-child(4) { animation-delay: 0.26s; }
        .card:nth-child(5) { animation-delay: 0.33s; }
        .card:hover {
            background: rgba(240,165,0,0.05);
            transform: translateY(-3px);
            z-index: 1;
        }
        .card-icon {
            font-size: 1.4rem;
            margin-bottom: 1rem;
            display: block;
        }
        .card-title {
            font-family: 'Syne', sans-serif;
            font-weight: 600;
            font-size: 0.95rem;
            margin-bottom: 0.6rem;
            letter-spacing: -0.01em;
        }
        .card-desc {
            font-size: 0.85rem;
            color: var(--text-muted);
            line-height: 1.65;
        }
        .card-tag {
            margin-top: 1.1rem;
            display: inline-block;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.65rem;
            letter-spacing: 0.1em;
            color: var(--amber);
            background: var(--amber-dim);
            padding: 3px 8px;
            border-radius: 2px;
            text-transform: uppercase;
        }

        /* ── TECH STACK ── */
        .stack-row {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 1.5rem;
        }
        .stack-pill {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.72rem;
            letter-spacing: 0.08em;
            color: var(--text-muted);
            border: 1px solid rgba(255,255,255,0.08);
            padding: 6px 14px;
            border-radius: 2px;
            transition: border-color 0.2s, color 0.2s;
        }
        .stack-pill:hover { border-color: var(--amber); color: var(--amber); }

        /* ── ORIGIN STORY ── */
        .origin-card {
            background: var(--amber-dim);
            border: 1px solid rgba(240,165,0,0.25);
            border-left: 3px solid var(--amber);
            border-radius: 4px;
            padding: 2rem 2.4rem;
        }
        .origin-card p {
            font-size: 1rem;
            line-height: 1.8;
            color: #c8b890;
        }
        .origin-card .origin-coords {
            margin-top: 1.2rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.72rem;
            color: var(--amber);
            letter-spacing: 0.12em;
        }

        /* ── CODE BLOCK ── */
        .code-wrap {
            background: #0d1117;
            border: 1px solid var(--border);
            border-radius: 4px;
            overflow: hidden;
        }
        .code-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.7rem 1.2rem;
            border-bottom: 1px solid var(--border);
            background: rgba(255,255,255,0.02);
        }
        .code-method {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.72rem;
            letter-spacing: 0.1em;
        }
        .method-post { color: #6ee7b7; }
        .code-path { color: var(--text-muted); margin-left: 8px; }
        .code-auth {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.65rem;
            color: var(--text-muted);
            background: var(--amber-dim);
            border: 1px solid rgba(240,165,0,0.2);
            padding: 2px 8px;
            border-radius: 2px;
        }
        pre {
            padding: 1.6rem;
            overflow-x: auto;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            line-height: 1.7;
            color: #c9d1d9;
        }
        .json-key   { color: #79c0ff; }
        .json-str   { color: #a5d6ff; }
        .json-num   { color: #f2cc60; }
        .json-bool  { color: #ff7b72; }

        /* ── ENDPOINTS ── */
        .endpoints-list { display: flex; flex-direction: column; gap: 12px; }
        .endpoint-row {
            display: flex;
            align-items: flex-start;
            gap: 1rem;
            padding: 1.1rem 1.4rem;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 3px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            transition: border-color 0.2s;
        }
        .endpoint-row:hover { border-color: rgba(240,165,0,0.4); }
        .ep-method { font-size: 0.68rem; letter-spacing: 0.1em; padding: 3px 8px; border-radius: 2px; flex-shrink: 0; margin-top: 1px; }
        .ep-post { background: rgba(110,231,183,0.1); color: #6ee7b7; }
        .ep-get  { background: rgba(96,165,250,0.1);  color: #60a5fa; }
        .ep-path { color: var(--text); }
        .ep-desc { color: var(--text-muted); font-family: 'DM Sans', sans-serif; font-size: 0.82rem; font-weight: 300; margin-top: 4px; }

        /* ── FOOTER ── */
        footer {
            border-top: 1px solid var(--border);
            padding: 2rem 0;
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.68rem;
            color: var(--text-muted);
            letter-spacing: 0.08em;
        }
        footer a { color: var(--text-muted); text-decoration: none; transition: color 0.2s; }
        footer a:hover { color: var(--amber); }

        /* ── RESPONSIVE ── */
        @media (max-width: 720px) {
            .cards-grid { grid-template-columns: 1fr; }
            .radar-wrap { display: none; }
            .status-right { display: none; }
            .hero { padding: 100px 0 60px; }
            footer { flex-direction: column; gap: 0.8rem; text-align: center; }
        }
    </style>
</head>
<body>

    <!-- STATUS BAR -->
    <div class="status-bar">
        <div class="status-left">
            <div class="pulse-dot"></div>
            <span class="status-label">System Operational</span>
            <span class="status-sep">//</span>
            <span class="status-version">v1.0.0</span>
        </div>
        <div class="status-right">
            <a href="/docs">Swagger UI</a>
            <a href="/redoc">ReDoc</a>
        </div>
    </div>

    <div class="page">

        <!-- HERO -->
        <section class="hero">
            <div class="radar-wrap" aria-hidden="true">
                <div class="radar-ring"></div>
                <div class="radar-ring"></div>
                <div class="radar-ring"></div>
                <div class="radar-ring"></div>
                <div class="radar-ring"></div>
            </div>

            <p class="hero-eyebrow">REST API &nbsp;·&nbsp; Route Engine &nbsp;·&nbsp; v1.0.0</p>
            <h1 class="hero-title">
                Logistics &<br><span>Route Aggregator</span>
            </h1>
            <p class="hero-desc">
                A high-performance asynchronous engine that ingests geographical waypoints,
                calculates real-world driving times, and aggregates live weather and daylight data
                to produce precision travel itineraries.
            </p>
            <div class="coord-ticker">
                <span class="coord-inner">
                    32.2464°N 77.1892°E [SPITI VALLEY] &nbsp;·&nbsp; 31.1048°N 77.1734°E [SHIMLA] &nbsp;·&nbsp; 32.0996°N 76.6451°E [KULLU] &nbsp;·&nbsp; 32.2399°N 77.1896°E [KAZA] &nbsp;·&nbsp; 30.7333°N 79.0667°E [BADRINATH] &nbsp;·&nbsp; 32.2464°N 77.1892°E [SPITI VALLEY] &nbsp;·&nbsp; 31.1048°N 77.1734°E [SHIMLA] &nbsp;·&nbsp; 32.0996°N 76.6451°E [KULLU] &nbsp;·&nbsp; 32.2399°N 77.1896°E [KAZA] &nbsp;·&nbsp; 30.7333°N 79.0667°E [BADRINATH] &nbsp;·&nbsp;
                </span>
            </div>
            <a href="/docs" class="hero-cta">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16M4 12h16M4 18h7"/></svg>
                Explore API Docs
            </a>
        </section>

        <hr class="divider">

        <!-- FEATURES -->
        <section class="section">
            <p class="section-label">Capabilities</p>
            <h2 class="section-title">What the Engine Does</h2>

            <div class="cards-grid">
                <div class="card">
                    <span class="card-icon">🗺️</span>
                    <p class="card-title">Dynamic OSRM Routing</p>
                    <p class="card-desc">Replaces static travel buffers with real-world driving durations from the Open Source Routing Machine. No API key required for routing.</p>
                    <span class="card-tag">OSRM · OpenStreetMap</span>
                </div>
                <div class="card">
                    <span class="card-icon">⚡</span>
                    <p class="card-title">Concurrent Aggregation</p>
                    <p class="card-desc">Uses <code style="font-family:'JetBrains Mono',monospace;font-size:0.8em;color:var(--amber)">asyncio.gather</code> and <code style="font-family:'JetBrains Mono',monospace;font-size:0.8em;color:var(--amber)">httpx</code> to fetch weather for all waypoints simultaneously — no I/O blocking, near-zero latency overhead.</p>
                    <span class="card-tag">asyncio · httpx</span>
                </div>
                <div class="card">
                    <span class="card-icon">🌅</span>
                    <p class="card-title">Temporal Daylight Engine</p>
                    <p class="card-desc">Compares calculated arrival times against localized UTC sunset data per waypoint and flags after-sunset arrivals as safety conflicts.</p>
                    <span class="card-tag">is_after_sunset flag</span>
                </div>
                <div class="card">
                    <span class="card-icon">🗄️</span>
                    <p class="card-title">Eager-Loaded Persistence</p>
                    <p class="card-desc">Async SQLAlchemy with <code style="font-family:'JetBrains Mono',monospace;font-size:0.8em;color:var(--amber)">aiosqlite</code> persists every route and its waypoints. Eager loading prevents lazy-load crashes in async contexts.</p>
                    <span class="card-tag">SQLAlchemy · SQLite</span>
                </div>
                <div class="card">
                    <span class="card-icon">🔐</span>
                    <p class="card-title">Header Authentication</p>
                    <p class="card-desc">All endpoints protected via <code style="font-family:'JetBrains Mono',monospace;font-size:0.8em;color:var(--amber)">X-API-KEY</code> header validation using FastAPI's Security dependency injection pattern.</p>
                    <span class="card-tag">FastAPI Security</span>
                </div>
            </div>
        </section>

        <hr class="divider">

        <!-- TECH STACK -->
        <section class="section" style="padding-top: 52px; padding-bottom: 52px;">
            <p class="section-label">Stack</p>
            <h2 class="section-title">Built With</h2>
            <div class="stack-row">
                <span class="stack-pill">Python 3.11</span>
                <span class="stack-pill">FastAPI</span>
                <span class="stack-pill">Uvicorn</span>
                <span class="stack-pill">SQLAlchemy (Async)</span>
                <span class="stack-pill">aiosqlite</span>
                <span class="stack-pill">httpx</span>
                <span class="stack-pill">Pydantic v2</span>
                <span class="stack-pill">OSRM</span>
                <span class="stack-pill">OpenWeatherMap API</span>
                <span class="stack-pill">Docker</span>
                <span class="stack-pill">Render CI/CD</span>
            </div>
        </section>

        <hr class="divider">

        <!-- ORIGIN STORY -->
        <section class="section">
            <p class="section-label">Origin</p>
            <h2 class="section-title">Why This Exists</h2>
            <div class="origin-card">
                <p>
                    This architecture was born out of necessity while mapping a complex <strong style="color:var(--amber)">Spiti Valley circuit</strong> — 
                    a high-altitude Himalayan route where standard map tools fail completely. Attempting to manually schedule 
                    a multi-day route from Rishikesh to Manali exposed a critical flaw: no tool could accurately forecast 
                    localised mountain driving times <em>combined</em> with strict pre-sunset arrival constraints at 
                    passes exceeding 4,500m. One wrong estimate means a night drive on an unlit cliff road.
                    This API automates that exact safety and logistical calculation.
                </p>
                <p class="origin-coords">// ORIGIN COORDINATES: 32.2464°N, 77.1892°E — SPITI VALLEY, HIMACHAL PRADESH</p>
            </div>
        </section>

        <hr class="divider">

        <!-- ENDPOINTS -->
        <section class="section">
            <p class="section-label">API Reference</p>
            <h2 class="section-title">Endpoints</h2>
            <div class="endpoints-list">
                <div class="endpoint-row">
                    <span class="ep-method ep-post">POST</span>
                    <div>
                        <div class="ep-path">/api/v1/routes/plan</div>
                        <div class="ep-desc">Submit a sequence of waypoints and receive a fully computed itinerary with driving times, weather data, and sunset flags.</div>
                    </div>
                </div>
                <div class="endpoint-row">
                    <span class="ep-method ep-get">GET</span>
                    <div>
                        <div class="ep-path">/api/v1/routes/{route_id}</div>
                        <div class="ep-desc">Retrieve a previously saved itinerary by its database ID, with full timeline reconstruction.</div>
                    </div>
                </div>
                <div class="endpoint-row">
                    <span class="ep-method ep-get">GET</span>
                    <div>
                        <div class="ep-path">/docs</div>
                        <div class="ep-desc">Interactive Swagger UI — explore, test, and authenticate directly in the browser.</div>
                    </div>
                </div>
            </div>
        </section>

        <hr class="divider">

        <!-- REQUEST EXAMPLE -->
        <section class="section">
            <p class="section-label">Usage</p>
            <h2 class="section-title">Request Example</h2>
            <div class="code-wrap">
                <div class="code-header">
                    <div>
                        <span class="code-method method-post">POST</span>
                        <span class="code-path">/api/v1/routes/plan</span>
                    </div>
                    <span class="code-auth">X-API-KEY required</span>
                </div>
                <pre><span class="json-key">{</span>
  <span class="json-key">"activity_name"</span>: <span class="json-str">"Spiti Valley Circuit — Day 1"</span>,
  <span class="json-key">"start_time"</span>:    <span class="json-str">"2026-05-29T04:00:00Z"</span>,
  <span class="json-key">"waypoints"</span>: [
    <span class="json-key">{</span>
      <span class="json-key">"name"</span>:                     <span class="json-str">"Shimla Bus Stand"</span>,
      <span class="json-key">"lat"</span>:                      <span class="json-num">31.1048</span>,
      <span class="json-key">"lon"</span>:                      <span class="json-num">77.1734</span>,
      <span class="json-key">"estimated_duration_mins"</span>:  <span class="json-num">30</span>
    <span class="json-key">}</span>,
    <span class="json-key">{</span>
      <span class="json-key">"name"</span>:                     <span class="json-str">"Narkanda"</span>,
      <span class="json-key">"lat"</span>:                      <span class="json-num">31.2707</span>,
      <span class="json-key">"lon"</span>:                      <span class="json-num">77.4587</span>,
      <span class="json-key">"estimated_duration_mins"</span>:  <span class="json-num">60</span>
    <span class="json-key">}</span>,
    <span class="json-key">{</span>
      <span class="json-key">"name"</span>:                     <span class="json-str">"Rampur Bushahr"</span>,
      <span class="json-key">"lat"</span>:                      <span class="json-num">31.4530</span>,
      <span class="json-key">"lon"</span>:                      <span class="json-num">77.6324</span>,
      <span class="json-key">"estimated_duration_mins"</span>:  <span class="json-num">45</span>
    <span class="json-key">}</span>
  ]
<span class="json-key">}</span></pre>
            </div>
        </section>

    </div>

    <!-- FOOTER -->
    <div class="page">
        <footer>
            <span>LOGISTICS &amp; ROUTE AGGREGATOR API &nbsp;·&nbsp; v1.0.0</span>
            <span>
                <a href="/docs">Docs</a>
                &nbsp;·&nbsp;
                <a href="/redoc">ReDoc</a>
            </span>
        </footer>
    </div>

</body>
</html>
    """
    return HTMLResponse(content=html_content, status_code=200)


@app.post("/api/v1/routes/plan", response_model=RouteResponse, dependencies=[Depends(get_api_key)])
async def plan_route(request: RouteRequest, db: AsyncSession = Depends(get_db)):
    if not settings.owm_api_key:
        raise HTTPException(status_code=500, detail="API key not configured.")

    try:
        timeline = await build_itinerary(request)
        
        db_route = DBRoute(activity_name=request.activity_name)
        db.add(db_route)
        await db.flush()

        for node in timeline:
            db_waypoint = DBWaypoint(
                route_id=db_route.id,
                sequence_order=node.sequence_order,
                location_name=node.location,
                arrival_time=node.arrival_time,
                departure_time=node.departure_time,
                is_after_sunset=node.is_after_sunset,
                error_message=node.error,
                temperature_celsius=node.weather.temperature_celsius if node.weather else None,
                conditions=node.weather.conditions if node.weather else None,
                sunrise_utc=node.weather.sunrise_utc if node.weather else None,
                sunset_utc=node.weather.sunset_utc if node.weather else None,
            )
            db.add(db_waypoint)

        await db.commit()
        await db.refresh(db_route)

        return RouteResponse(
            id=db_route.id,
            activity_name=db_route.activity_name,
            total_waypoints=len(timeline),
            timeline=timeline
        )
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@app.get(
    "/api/v1/routes/{route_id}",
    response_model=RouteResponse,
    status_code=status.HTTP_200_OK
)
async def get_route(route_id: int, db: AsyncSession = Depends(get_db)):
    """Fetches a saved itinerary and all its waypoints from the database."""
    query = select(DBRoute).options(selectinload(DBRoute.waypoints)).where(DBRoute.id == route_id)
    result = await db.execute(query)
    db_route = result.scalar_one_or_none()

    if not db_route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route with ID {route_id} not found."
        )

    sorted_waypoints = sorted(db_route.waypoints, key=lambda w: w.sequence_order)
    
    timeline = []
    for wp in sorted_waypoints:
        weather_obj = None
        if wp.temperature_celsius is not None:
            weather_obj = WeatherData(
                temperature_celsius=wp.temperature_celsius,
                conditions=wp.conditions,
                sunrise_utc=wp.sunrise_utc,
                sunset_utc=wp.sunset_utc
            )
        timeline.append(
            WaypointTimeline(
                sequence_order=wp.sequence_order,
                location=wp.location_name,
                arrival_time=wp.arrival_time,
                departure_time=wp.departure_time,
                is_after_sunset=wp.is_after_sunset,
                weather=weather_obj,
                error=wp.error_message
            )
        )

    return RouteResponse(
        id=db_route.id,
        activity_name=db_route.activity_name,
        total_waypoints=len(timeline),
        timeline=timeline
    )