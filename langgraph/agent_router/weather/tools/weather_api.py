from langchain_core.tools import tool
from geopy.geocoders import Nominatim
import httpx
import time
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Allow importing the webapp package from the project root
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from webapp.database import Database

__all__ = ["get_coordinates", "get_weather", "get_rain_stop_estimate"]

# Shared database instance for caching
_db = Database()

# WMO weather code → human-readable description
WMO_DESCRIPTIONS = {
    0: "Clear",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Light rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Light snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Light rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Light snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with light hail",
    99: "Thunderstorm with heavy hail",
}


def _wmo_to_description(code) -> str:
    if code is None:
        return "Unknown"
    return WMO_DESCRIPTIONS.get(int(code), "Unknown")


@tool
def get_coordinates(city: str, state: str) -> dict:
    """Get latitude and longitude for a city and state in the USA."""
    # Check cache first
    cached = _db.get_cached_geocode(city, state)
    if cached:
        return {"latitude": cached["latitude"], "longitude": cached["longitude"]}

    geolocator = Nominatim(
        user_agent="astonhaycocks@gmail.com",
        timeout=10,
    )
    location_query = f"{city}, {state}, USA"

    try:
        location = geolocator.geocode(location_query)
        if location:
            lat, lon = location.latitude, location.longitude
            _db.cache_geocode(city, state, lat, lon)
            return {"latitude": lat, "longitude": lon}
        else:
            return {"error": f"Could not find location: {location_query}"}
    except Exception as e:
        return {"error": str(e)}


@tool
def get_weather(latitude: float, longitude: float) -> dict:
    """Get weather forecast for given latitude and longitude coordinates."""
    # Round lat/lon for cache key consistency
    lat = round(latitude, 2)
    lon = round(longitude, 2)

    # Build list of dates we want (today + 6 days)
    today = datetime.utcnow().date()
    dates = [(today + timedelta(days=i)).isoformat() for i in range(7)]

    # Check cache
    cached_rows = _db.get_cached_weather(lat, lon, dates)
    if len(cached_rows) == 7:
        # All days cached and fresh — build response from cache
        return _build_forecast(cached_rows)

    # Fetch from Open-Meteo with expanded fields
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,temperature_2m_min,"
        f"precipitation_sum,precipitation_probability_max,"
        f"weather_code,wind_speed_10m_max,wind_gusts_10m_max,"
        f"sunrise,sunset"
        f"&temperature_unit=fahrenheit"
        f"&wind_speed_unit=mph"
        f"&precipitation_unit=inch"
        f"&timezone=auto"
    )

    last_error = None
    for attempt in range(3):
        try:
            response = httpx.get(url, timeout=15.0)
            break
        except (httpx.ConnectError, httpx.ReadTimeout) as e:
            last_error = e
            if attempt < 2:
                time.sleep(1.0 * (attempt + 1))
    else:
        return {"error": f"Weather API unavailable: {last_error}"}

    if response.status_code != 200:
        return {"error": f"API request failed: {response.status_code}"}

    data = response.json()
    daily = data["daily"]

    # Build raw rows for caching
    raw_rows = []
    for i, date_str in enumerate(daily["time"]):
        raw_rows.append({
            "date": date_str,
            "high_f": daily["temperature_2m_max"][i],
            "low_f": daily["temperature_2m_min"][i],
            "precipitation_sum": daily["precipitation_sum"][i],
            "precipitation_probability_max": daily["precipitation_probability_max"][i],
            "weather_code": daily["weather_code"][i],
            "wind_speed_max": daily["wind_speed_10m_max"][i],
            "wind_gusts_max": daily["wind_gusts_10m_max"][i],
            "sunrise": daily["sunrise"][i],
            "sunset": daily["sunset"][i],
        })

    # Cache the results
    _db.cache_weather(lat, lon, raw_rows)

    return _build_forecast(raw_rows)


@tool
def get_rain_stop_estimate(latitude: float, longitude: float) -> dict:
    """Estimate how long rain will continue at a location using 15-minute forecast intervals.
    Use this when the user asks how long it will rain, when rain will stop, or if it is currently raining."""
    lat = round(latitude, 4)
    lon = round(longitude, 4)

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&minutely_15=rain,precipitation,weather_code"
        f"&forecast_minutely_15=96"
        f"&timezone=auto"
    )

    try:
        response = httpx.get(url, timeout=15.0)
    except Exception as e:
        return {"error": f"Weather API unavailable: {e}"}

    if response.status_code != 200:
        return {"error": f"API request failed: {response.status_code}"}

    data = response.json()
    minutely = data.get("minutely_15", {})
    times         = minutely.get("time", [])
    rain          = minutely.get("rain", [])
    precipitation = minutely.get("precipitation", [])

    now = datetime.now()

    # Is it raining right now? Check the most recent slot at or before now.
    raining_now = False
    for i, t in enumerate(times):
        slot = datetime.fromisoformat(t)
        if slot <= now:
            raining_now = (rain[i] or 0) > 0 or (precipitation[i] or 0) > 0

    if not raining_now:
        return {"raining_now": False, "message": "It is not currently raining at this location."}

    # Find the first future slot where rain stops.
    for i, t in enumerate(times):
        slot = datetime.fromisoformat(t)
        if slot <= now:
            continue
        is_raining = (rain[i] or 0) > 0 or (precipitation[i] or 0) > 0
        if not is_raining:
            minutes_until_stop = round((slot - now).total_seconds() / 60)
            return {
                "raining_now": True,
                "stops_at": t,
                "minutes_until_stop": minutes_until_stop,
                "message": f"Rain may stop in about {minutes_until_stop} minutes.",
            }

    return {
        "raining_now": True,
        "stops_at": None,
        "minutes_until_stop": None,
        "message": "Rain is forecasted to continue for the next 24 hours.",
    }


def _build_forecast(rows) -> dict:
    """Convert raw daily rows into the forecast response format."""
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    forecast = []
    for row in rows:
        high = row.get("high_f")
        low = row.get("low_f")
        if high is None or low is None:
            continue
        dt = datetime.strptime(row["date"], "%Y-%m-%d")
        forecast.append({
            "date": row["date"],
            "day": weekday_names[dt.weekday()],
            "high_f": round(float(high), 1),
            "low_f": round(float(low), 1),
            "precip_in": round(float(row.get("precipitation_sum") or 0), 2),
            "precip_chance_pct": int(row.get("precipitation_probability_max") or 0),
            "weather": _wmo_to_description(row.get("weather_code")),
            "wind_mph": round(float(row.get("wind_speed_max") or 0), 1),
            "gusts_mph": round(float(row.get("wind_gusts_max") or 0), 1),
            "sunrise": row.get("sunrise", ""),
            "sunset": row.get("sunset", ""),
        })
    return {"forecast": forecast}
