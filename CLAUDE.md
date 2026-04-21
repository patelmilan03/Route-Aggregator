# Project Context & AI Instructions

## 📌 Overview
This repository contains the **Logistics & Route Aggregator API**. It is a backend service designed to take a sequence of geographical coordinates, calculate real-world driving times between them using OSRM, and concurrently fetch localized weather and daylight data using OpenWeatherMap.

## 🏗️ Architecture & Tech Stack
* **Language:** Python 3.11
* **Framework:** FastAPI
* **Server:** Uvicorn
* **Database:** SQLite (local/dev)
* **ORM:** SQLAlchemy 2.0 with `aiosqlite` (Async operations)
* **Validation:** Pydantic (`BaseSettings` for env management)
* **Containerization:** Docker (`Dockerfile` must remain lowercase 'f' for Linux CI/CD)
* **PaaS:** Render (Connected via GitHub Actions/Webhooks)

## 📐 Core Engineering Rules
When generating code or suggesting features for this project, adhere strictly to these architectural decisions:

1. **Strict Asynchronous I/O:** Never use synchronous network libraries like `requests`. Always use `httpx` with `asyncio.gather()` to fetch data from third-party APIs concurrently.
2. **Database Eager Loading:** When querying relational data via SQLAlchemy in async routes (e.g., getting a Route and its Waypoints), always use `selectinload`. Do not rely on lazy-loading, as it will crash the async event loop.
3. **Pydantic Validation First:** All incoming data must be strictly validated through Pydantic schemas before any business logic is executed.
4. **Security Check:** All endpoints must be protected using FastAPI's `Security` dependency checking for the `X-API-KEY` header.
5. **No Hardcoded Secrets:** Environment variables must always be managed via the `.env` file locally and injected via the PaaS dashboard in production. Never commit `.env`.

## 🚀 Key Features Implemented
* Dynamic duration matrix via OSRM Trip/Route endpoints.
* UTC timestamp comparison for localized sunset/daylight safety flags.
* Background Keep-Alive daemon utilizing `@app.on_event("startup")` to bypass 15-minute PaaS sleep cycles.
* Custom styled `HTMLResponse` dashboard at the root (`/`) endpoint detailing the project's origin.

## 💻 Common Commands
**Run Locally (Native):**
```bash
uvicorn app.main:app --reload
```
**Run via Docker:**
```bash
docker build -t route-aggregator-api .
docker run -p 8000:8000 --env-file .env route-aggregator-api
```