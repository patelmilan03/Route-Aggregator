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

### 5. Dynamic Routing Integration 
* **Action:** Replaced the static 45-minute travel buffer with dynamic driving estimations using the Open Source Routing Machine (OSRM) API.
* **Logic:** Static buffers break down in reality. Travel time between waypoints dictates the actual viability of the schedule.
* **Decision:** Utilized OSRM for real-time distance matrix calculations without requiring API keys, fetching routing durations concurrently to maintain API speed.

### 6. Containerization (Complete)
* **Action:** Wrote Dockerfile and managed `.dockerignore`.
* **Logic:** Ensured the application environment is isolated, reproducible, and OS-agnostic (bypassing Windows file-lock quirks).

### 7. Fixed Temporal Logic Bug
* **Action:** Patched `services.py` to use `.time()` comparisons for daylight checking.
* **Logic:** Prevents "After Sunset" false positives caused by comparing current sunset dates against future arrival dates.

### 8. Local Docker Execution
* **Action:** Built Docker Image and ran container via `docker run`.
* **Logic:** Achieved OS-level abstraction. The API now runs in a consistent Linux environment regardless of the host OS.

### 9. API Security Layer
* **Action:** Implemented `APIKeyHeader` authentication.
* **Logic:** Protects infrastructure from unauthorized use by requiring a secret key in the request headers.
* **Decision:** Used FastAPI's `Security` dependencies for clean, reusable protection across all endpoints.

### 10. Production Environment Readiness
* **Action:** Updated Docker CMD to support dynamic port binding (`${PORT:-8000}`).
* **Logic:** Vital for compatibility with Cloud Platform-as-a-Service (PaaS) providers that assign ports dynamically at runtime.

### 11. Repository Sanitization & Security Remediation
* **Action:** Purged compromised `.env` files, `venv/`, `__pycache__/`, and `routes.db` from Git history using `git rm --cached`. Rotated external API keys.
* **Logic:** Prevented hardcoded secrets from leaking and removed OS-specific binaries/cache files that break cross-platform cloud deployments.
* **Decision:** Enforced strict `.gitignore` rules to maintain a lightweight, production-grade codebase.

### 12. Cloud Deployment & CI/CD Pipeline (Render)
* **Action:** Connected the GitHub repository to Render for automated Docker-based Continuous Deployment.
* **Logic:** Pushing code to the `main` branch now automatically triggers a cloud build, pulling the latest code and spinning up a new container with zero downtime.
* **Decision:** Transitioned from local hosting to a managed cloud environment, securely injecting environment variables via the provider's dashboard.
---