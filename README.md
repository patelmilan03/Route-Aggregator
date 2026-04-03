# Logistics & Route Aggregator API 🌍⏱️

A high-performance, asynchronous REST API built with FastAPI that acts as a central logistics engine. It ingests a sequence of geographical waypoints, calculates dynamic driving times between them, and concurrently aggregates localized weather and daylight data to generate a precision travel itinerary.

## 🚀 Features

* **Dynamic OSRM Routing:** Replaces static travel buffers with real-world driving time calculations utilizing the Open Source Routing Machine (OSRM).
* **Concurrent Data Aggregation:** Uses `asyncio` and `httpx` to fetch OpenWeatherMap data for all waypoints simultaneously, preventing I/O blocking and drastically reducing API latency.
* **Temporal Daylight Engine:** Compares calculated arrival times against localized UTC sunset data to automatically flag nighttime safety/visibility conflicts.
* **Eager-Loaded Persistence:** Utilizes SQLAlchemy and `aiosqlite` to persist routes and waypoints, employing eager loading to prevent lazy-load crashes in asynchronous environments.
* **Header Authentication:** Secures infrastructure against unauthorized consumption via `X-API-KEY` header validation.
* **Containerized & CI/CD Ready:** Fully Dockerized for OS-agnostic deployment, currently running on Render via an automated GitHub pipeline.

## 🛠️ Tech Stack

* **Framework:** Python 3.11, FastAPI, Uvicorn
* **Database:** SQLite, SQLAlchemy (Async), Pydantic
* **External APIs:** OpenWeatherMap API, OSRM (OpenStreetMap)
* **DevOps:** Docker, Render (CI/CD)

## 💻 Local Installation & Setup

You can run this API locally using Docker (recommended) or a native Python virtual environment.

### Prerequisites
1. Get a free API Key from [OpenWeatherMap](https://openweathermap.org/api).
2. Create a `.env` file in the root directory:
   ```text
   OWM_API_KEY=your_openweathermap_key_here
   API_KEY=your_custom_secret_password
   ```

### Method 1: Docker (Recommended)
Ensure Docker Desktop is running on your machine.
```bash
# Build the image
docker build -t route-aggregator-api .

# Run the container (injecting the .env file)
docker run -p 8000:8000 --env-file .env route-aggregator-api
```

### Method 2: Native Python
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn app.main:app --reload
```

## 📡 API Usage

### Authentication
All endpoints require the `X-API-KEY` header.
* **Key:** `X-API-KEY`
* **Value:** *(The password you set in your `.env` file)*

### Generate an Itinerary
**POST** `/api/v1/routes/plan`

```json
{
  "activity_name": "Pune Nature & Sightseeing Loop",
  "start_time": "2026-04-05T02:30:00Z",
  "waypoints": [
    {
      "name": "Osho International Meditation Resort",
      "lat": 18.5362,
      "lon": 73.8939,
      "estimated_duration_mins": 120
    },
    {
      "name": "Vetal Hill Viewpoint",
      "lat": 18.5283,
      "lon": 73.8208,
      "estimated_duration_mins": 90
    }
  ]
}
```

### Fetch a Saved Itinerary
**GET** `/api/v1/routes/{id}`
Returns the fully generated timeline with calculated arrival times, dynamic driving gaps, and weather flags.

## 📜 Interactive Documentation
Once the server is running, navigate to `http://localhost:8000/docs` (or your live Render URL + `/docs`) to interact with the auto-generated Swagger UI.