"""Open-Meteo weather client.
Retrieves real weather data without requiring an API key.
"""
from typing import Optional, Dict, Any
import httpx


def get_weather_for_city(city: str) -> Dict[str, Any]:
    """Fetch current weather for a city using Open-Meteo geocoding and forecast API."""
    if not city or not city.strip():
        return {
            "success": False,
            "error": "No city provided.",
            "source": "Open-Meteo"
        }

    clean_city = city.strip()
    try:
        # Step 1: Geocoding
        geocode_url = "https://geocoding-api.open-meteo.com/v1/search"
        geo_resp = httpx.get(
            geocode_url,
            params={"name": clean_city, "count": 1, "language": "en", "format": "json"},
            timeout=5.0
        )
        geo_data = geo_resp.json()

        if not geo_data.get("results"):
            return {
                "success": False,
                "error": f"City '{clean_city}' could not be located on Open-Meteo.",
                "source": "Open-Meteo"
            }

        first_match = geo_data["results"][0]
        name = first_match.get("name", clean_city)
        country = first_match.get("country", "")
        lat = first_match["latitude"]
        lon = first_match["longitude"]

        # Step 2: Forecast
        forecast_url = "https://api.open-meteo.com/v1/forecast"
        weather_resp = httpx.get(
            forecast_url,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m",
            },
            timeout=5.0
        )
        w_data = weather_resp.json()
        current = w_data.get("current", {})

        temp = current.get("temperature_2m")
        humidity = current.get("relative_humidity_2m")
        wind = current.get("wind_speed_10m")

        return {
            "success": True,
            "city": name,
            "country": country,
            "temperature_celsius": temp,
            "humidity_percent": humidity,
            "wind_speed_kmh": wind,
            "source": "Open-Meteo (https://open-meteo.com)",
            "message": f"Currently in {name}{f', {country}' if country else ''}: {temp}°C, humidity {humidity}%, wind {wind} km/h (Source: Open-Meteo)."
        }
    except Exception as exc:
        return {
            "success": False,
            "error": f"Could not retrieve weather data for '{clean_city}': {str(exc)}",
            "source": "Open-Meteo"
        }
