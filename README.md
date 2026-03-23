# your-reminder

A personal reminder app for Hong Kong residents. Automatically fetches the latest
weather from the **Hong Kong Observatory** and suggests what to wear today.

Includes a **Discord bot** that replies with school-uniform and going-out clothing
advice, defaulting to **元朗公園** weather readings.

## Features

- 🌤 Fetches live weather from the [HKO RSS feed](https://rss.weather.gov.hk/rss/CurrentWeather_uc.xml)
- 📍 Location-specific temperature from the HKO `rhrread` API (default: 元朗公園)
- 🌡️ Reads temperature, humidity, and wind conditions
- 🏫 School-uniform suggestions (male student; 恤衫 / 毛衣 / 校褸 / etc.)
- 🛍️ Going-out clothing suggestions
- 🤖 AI-powered suggestions via [pollinations.ai](https://pollinations.ai) (free, no key required)
- ⏰ Built-in daily scheduler — set it and forget it
- 🤖 Discord bot (`discord_bot.py`) for chat-based reminders

---

## Discord Bot

### 1. Create a Discord Application & Bot

1. Go to <https://discord.com/developers/applications> and click **New Application**.
2. Open the **Bot** tab → click **Add Bot**.
3. Under **Privileged Gateway Intents** enable **MESSAGE CONTENT INTENT**.
4. Copy the bot token — you will need it as `DISCORD_BOT_TOKEN`.
5. Under **OAuth2 → URL Generator** select scope `bot` and permission `Send Messages`,
   then open the generated URL to invite the bot to your server.

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

`.env`:

```
DISCORD_BOT_TOKEN=your_discord_bot_token_here
POLLINATIONS_API_KEY=           # optional
```

### 3. Run locally

```bash
pip install -r requirements.txt
python discord_bot.py
```

### 4. Bot commands

| Command | Description |
|---|---|
| `!weather` | Weather + clothing suggestions for **元朗公園** (default) |
| `!weather 沙田` | Weather + suggestions for 沙田 |
| `!locations` | List all supported locations |
| `!help_weather` | Show command help |

---

## Deploy on Railway

1. Push this repository to GitHub (or fork it).
2. Open <https://railway.app> → **New Project → Deploy from GitHub repo**.
3. Select your repository.
4. In **Settings → Variables** add the following:

   | Variable | Value |
   |---|---|
   | `DISCORD_BOT_TOKEN` | Your Discord bot token |
   | `POLLINATIONS_API_KEY` | *(optional)* Your pollinations.ai key |

5. Railway will detect the `Procfile` and run:
   ```
   worker: python discord_bot.py
   ```
6. Click **Deploy**. The bot will come online automatically.

> **Note**: Railway's free tier may sleep idle workers. Use a paid plan or a keep-alive
> service if you need 24/7 uptime.

---

## CLI Quick Start

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run once (immediate weather + clothing tip)

```bash
python weather_reminder.py
```

### Schedule daily reminders

```bash
# Remind at 07:30 every morning
python weather_reminder.py --schedule 07:30

# Multiple reminders per day
python weather_reminder.py --schedule 07:30 12:00 18:00
```

### AI-powered suggestions (optional)

```bash
POLLINATIONS_API_KEY=your_key python weather_reminder.py
# or
python weather_reminder.py --api-key your_key
```

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

## Weather Sources

| Data | Source |
|---|---|
| General conditions (humidity, wind, description) | [HKO RSS feed](https://rss.weather.gov.hk/rss/CurrentWeather_uc.xml) |
| Location-specific temperature | [HKO `rhrread` API](https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=tc) |

