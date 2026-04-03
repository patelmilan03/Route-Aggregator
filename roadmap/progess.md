# PROJECT_ROADMAP.md
## Logistics & Route Aggregator API

### 1. Initial Setup & Core Aggregation
* **Action:** Bootstrapped the FastAPI application with Uvicorn.
* **Logic:** Implemented a POST endpoint to accept an activity name and a sequence of waypoints. Used `httpx` and `asyncio.gather` to fetch weather data from OpenWeatherMap concurrently, ensuring high I/O performance rather than blocking sequential calls.
* **Decision:** Used Pydantic for strict input validation to prevent malformed data from crashing the logic engine.

### 2. The Geocoding Architecture Shift
* **Action:** Refactored the payload and OWM API call to use precise `lat` and `lon` instead of city names.
* **Logic:** Third-party weather APIs fail when queried with local landmark strings (e.g., "Shaniwar Wada"). 
* **Decision:** Shifted the geocoding responsibility to the frontend (which would use a dedicated Places API) to guarantee the backend weather aggregator always receives deterministic GPS coordinates.

### 3. Business Logic & Timezone Handling
* **Action:** Added the `is_after_sunset` Boolean flag to the response schema.
* **Logic:** OpenWeatherMap returns UTC timestamps. If a user plans an itinerary in local time, raw aggregation causes severe contextual mismatches (e.g., scheduling a photowalk at 1 AM local time).
* **Decision:** Engineered the backend to calculate the temporal overlap between estimated arrival times and the localized sunset times, returning a warning flag to assist downstream frontend applications.

### 4. Database Persistence & Eager Loading
* **Action:** Integrated SQLAlchemy with the `aiosqlite` async driver. Built a one-to-many schema (`DBRoute` -> `DBWaypoint`).
* **Logic:** Ephemeral API responses are insufficient for a planning tool. Data must be persisted. 
* **Decision:** Opted for SQLite for frictionless local development, ensuring an easy migration path to PostgreSQL later. Implemented a `GET` endpoint using `selectinload` (Eager Loading) to fetch routes and their associated waypoints in a single async database trip, preventing lazy-loading crashes.

### 5. Dynamic Routing Integration (Current)
* **Action:** Replaced the static 45-minute travel buffer with dynamic driving estimations using the Open Source Routing Machine (OSRM) API.
* **Logic:** Static buffers break down in reality. Travel time between waypoints dictates the actual viability of the schedule.
* **Decision:** Utilized OSRM for real-time distance matrix calculations without requiring API keys, fetching routing durations concurrently to maintain API speed.

### 6. Containerization (Pending)
* **Action:** Write Dockerfile and manage `.dockerignore`.
* **Logic:** Ensure the application environment is isolated, reproducible, and OS-agnostic (bypassing Windows file-lock quirks).
---