# your-reminder

A personal reminder app for Hong Kong residents. Automatically fetches the latest
weather from the **Hong Kong Observatory** and suggests what to wear today.

## Features

- 🌤 Fetches live weather from the [HKO RSS feed](https://rss.weather.gov.hk/rss/CurrentWeather_uc.xml)
- 🌡️ Reads temperature, humidity, and wind conditions
- 👗 Gives rule-based clothing suggestions in Cantonese
- 🤖 Optional AI-powered suggestions via [pollinations.ai](https://pollinations.ai)
- ⏰ Built-in daily scheduler — set it and forget it

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run once (immediate weather + clothing tip)

```bash
python weather_reminder.py
```

### 3. Schedule daily reminders

```bash
# Remind at 07:30 every morning
python weather_reminder.py --schedule 07:30

# Multiple reminders per day
python weather_reminder.py --schedule 07:30 12:00 18:00
```

### 4. AI-powered suggestions (optional)

Get a free API key at <https://enter.pollinations.ai>, then:

```bash
# Via environment variable
POLLINATIONS_API_KEY=your_key python weather_reminder.py

# Or via flag
python weather_reminder.py --api-key your_key
```

You can also copy `.env.example` to `.env` and fill in your key — the script
reads `POLLINATIONS_API_KEY` from the environment automatically.

## Sample Output

```
──────────────────────────────────────────────────
🌤  香港天氣提示  (2026-03-23 08:02)
──────────────────────────────────────────────────
📋 香港天文台於2026年03月23日08時02分發出之天氣報告
🌡️  氣溫：22°C
💧 相對濕度：85%
🌬️  風速：15 km/h  (東北)
──────────────────────────────────────────────────
👗 今日著衫建議：
👕 天氣舒適，薄身長袖或短袖 T 恤加薄外套即可。
💧 濕度高，選擇透氣排汗布料，避免悶熱不適。
──────────────────────────────────────────────────
```

## Weather Source

Data comes from the **Hong Kong Observatory** official RSS feed:

> <https://rss.weather.gov.hk/rss/CurrentWeather_uc.xml>
