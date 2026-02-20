import streamlit as st
import requests
import json
from openai import OpenAI

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
WEATHER_KEY = st.secrets["OPENWEATHER_API_KEY"]

def get_current_weather(location, units="imperial"):
    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?q={location}&appid={WEATHER_KEY}&units={units}"
    )
    response = requests.get(url)
    if response.status_code == 401:
        raise Exception("Authentication failed: Invalid API key (401 Unauthorized)")
    if response.status_code == 404:
        msg = response.json().get("message", "City not found")
        raise Exception(f"404 error: {msg}")
    data = response.json()
    return {
        "location":    location,
        "temperature": round(data["main"]["temp"], 2),
        "feels_like":  round(data["main"]["feels_like"], 2),
        "temp_min":    round(data["main"]["temp_min"], 2),
        "temp_max":    round(data["main"]["temp_max"], 2),
        "humidity":    round(data["main"]["humidity"], 2),
        "description": data["weather"][0]["description"],
        "units":       "°F" if units == "imperial" else "°C",
    }

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": (
                "Get the current weather for a given city. "
                "Use this whenever weather information is needed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": (
                            "The city name, e.g. 'Syracuse, NY, US' or 'Lima, Peru'. "
                            "Default to 'Syracuse, NY, US' if no location is provided."
                        ),
                    },
                    "units": {
                        "type": "string",
                        "enum": ["imperial", "metric"],
                        "description": "Temperature units. Default is 'imperial' (Fahrenheit).",
                    },
                },
                "required": ["location"],
            },
        },
    }
]

def get_outfit_advice(city: str) -> str:
    """Run the two-step tool-call flow and return the LLM's advice."""
    system_msg = (
        "You are a helpful fashion and outdoor-activities assistant. "
        "When given a city, fetch the current weather and then recommend "
        "appropriate clothing and outdoor activities for the day. "
        "If no city is given, default to Syracuse, NY, US."
    )
    user_msg = f"What should I wear today in {city}?" if city else "What should I wear today?"

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user",   "content": user_msg},
    ]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )
    msg = response.choices[0].message

    if msg.tool_calls:
        messages.append(msg)

        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            loc   = args.get("location", "Syracuse, NY, US")
            units = args.get("units", "imperial")

            try:
                weather_data = get_current_weather(loc, units)
                result_str   = json.dumps(weather_data)
            except Exception as e:
                result_str = json.dumps({"error": str(e)})

            messages.append({
                "role":         "tool",
                "tool_call_id": tc.id,
                "name":         tc.function.name,
                "content":      result_str,
            })

        follow_up = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        return follow_up.choices[0].message.content
    else:
        return msg.content

st.set_page_config(page_title="What to Wear Bot", page_icon="🧥")
st.title("What to Wear Bot")
st.caption("Enter a city and get clothing suggestions + outdoor activity ideas based on today's weather.")

city_input = st.text_input(
    "City",
    placeholder="e.g. Syracuse, NY, US  or  Tokyo, Japan",
    help="Leave blank to default to Syracuse, NY, US",
)

if st.button("Get Advice", type="primary"):
    loc = city_input.strip() if city_input.strip() else "Syracuse, NY, US"
    with st.spinner(f"Fetching weather for **{loc}** and generating advice…"):
        try:
            advice = get_outfit_advice(loc)
            st.success("Here's your advice for today!")
            st.markdown(advice)
        except Exception as e:
            st.error(f"Something went wrong: {e}")