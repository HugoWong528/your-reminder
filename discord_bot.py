#!/usr/bin/env python3
"""
discord_bot.py

Discord bot that provides Hong Kong weather reports with clothing suggestions.
Default weather location: 元朗公園.

Commands
--------
!weather [地點]   – Weather report + school & going-out clothing suggestions.
!locations        – List all supported locations.
!help_weather     – Show usage instructions.

Environment variables (Railway dashboard or .env file)
-------------------------------------------------------
DISCORD_BOT_TOKEN    – Discord bot token (required).
POLLINATIONS_API_KEY – pollinations.ai API key (optional; improves AI quality).
"""

import asyncio
import logging
import os
from functools import partial

import discord
from discord.ext import commands

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from weather_reminder import (
    AVAILABLE_LOCATIONS,
    DEFAULT_LOCATION,
    SCHOOL_CLOTHING_LIST,
    ClothingSuggester,
    HKOLocationWeatherFetcher,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True  # Required for prefix commands

bot = commands.Bot(command_prefix="!", intents=intents)


# ---------------------------------------------------------------------------
# Async helper
# ---------------------------------------------------------------------------


async def _run_blocking(func, *args):
    """Run a blocking function in the default thread-pool executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(func, *args))


# ---------------------------------------------------------------------------
# Bot events
# ---------------------------------------------------------------------------


@bot.event
async def on_ready():
    logger.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="元朗公園天氣 ☁️",
        )
    )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@bot.command(name="weather", aliases=["天氣", "w"])
async def weather_command(ctx: commands.Context, *, location: str = None):
    """
    Get weather + clothing suggestions for a Hong Kong location.

    Usage:
      !weather            – Uses default location (元朗公園).
      !weather 沙田       – Uses the specified location.
    """
    # Resolve location string to an HKO station name.
    if location is None:
        station = DEFAULT_LOCATION
        display_name = DEFAULT_LOCATION
    else:
        query = location.strip()
        station = AVAILABLE_LOCATIONS.get(query)
        if station is None:
            # Try case-insensitive partial match.
            query_lower = query.lower()
            for key, val in AVAILABLE_LOCATIONS.items():
                if query_lower in key.lower() or key.lower() in query_lower:
                    station = val
                    query = key
                    break
        if station is None:
            await ctx.reply(
                f"❌ 未能找到「{query}」。請用 `!locations` 查看可用地點。"
            )
            return
        display_name = query

    # Acknowledge the request while we fetch data.
    status_msg = await ctx.reply(f"⏳ 正在獲取 **{display_name}** 天氣資訊…")

    # Fetch weather (blocking I/O → run in executor).
    fetcher = HKOLocationWeatherFetcher(station=station)
    try:
        weather = await _run_blocking(fetcher.fetch)
    except Exception as exc:
        logger.error("Weather fetch failed: %s", exc)
        await status_msg.edit(content=f"❌ 無法獲取天氣資訊：{exc}")
        return

    # Generate clothing suggestions (AI with rule-based fallback).
    api_key = os.environ.get("POLLINATIONS_API_KEY")
    suggester = ClothingSuggester(pollinations_api_key=api_key)

    try:
        school_tip = await _run_blocking(suggester.suggest_with_mode, weather, "school")
    except Exception as exc:
        logger.warning("School suggestion error: %s", exc)
        school_tip = suggester._rule_suggest_school(weather)

    try:
        street_tip = await _run_blocking(suggester.suggest_with_mode, weather, "street")
    except Exception as exc:
        logger.warning("Street suggestion error: %s", exc)
        street_tip = suggester._rule_suggest(weather)

    # Build a Discord embed.
    embed = discord.Embed(
        title=f"🌤 {display_name} 天氣報告",
        color=discord.Color.blue(),
    )

    # Weather stats field.
    stats: list[str] = []
    if weather.temperature_c is not None:
        stats.append(f"🌡️ 氣溫：**{weather.temperature_c}°C**")
    if weather.humidity_pct is not None:
        stats.append(f"💧 相對濕度：**{weather.humidity_pct}%**")
    if weather.wind_speed_kmh is not None:
        wind_str = f"🌬️ 風速：**{weather.wind_speed_kmh} km/h**"
        if weather.wind_direction:
            wind_str += f"（{weather.wind_direction}）"
        stats.append(wind_str)
    if stats:
        embed.add_field(name="📊 天氣狀況", value="\n".join(stats), inline=False)

    # Clothing suggestions.
    embed.add_field(
        name="🏫 返學著衫建議",
        value=school_tip or "（無資料）",
        inline=False,
    )
    embed.add_field(
        name="🛍️ 出街著衫建議",
        value=street_tip or "（無資料）",
        inline=False,
    )

    if weather.report_time:
        embed.set_footer(text=weather.report_time)

    await status_msg.edit(content=None, embed=embed)


@bot.command(name="locations", aliases=["地點", "loc"])
async def locations_command(ctx: commands.Context):
    """List all supported weather-query locations."""
    unique_keys = sorted(set(AVAILABLE_LOCATIONS.keys()))
    location_list = "、".join(unique_keys)
    embed = discord.Embed(
        title="📍 可用地點",
        description=(
            f"使用 `!weather [地點]` 查詢指定地點天氣。\n\n{location_list}"
        ),
        color=discord.Color.green(),
    )
    embed.set_footer(text=f"預設地點：{DEFAULT_LOCATION}")
    await ctx.reply(embed=embed)


@bot.command(name="help_weather", aliases=["幫助", "help_w"])
async def help_command(ctx: commands.Context):
    """Show bot usage instructions."""
    embed = discord.Embed(
        title="🤖 天氣提示機器人",
        description="香港天氣提示 + 著衫建議（學校 / 出街）",
        color=discord.Color.purple(),
    )
    embed.add_field(
        name="指令",
        value=(
            "`!weather` — 查詢元朗公園天氣（預設）\n"
            "`!weather [地點]` — 查詢指定地點天氣\n"
            "`!locations` — 列出所有可用地點\n"
            "`!help_weather` — 顯示此說明\n"
        ),
        inline=False,
    )
    embed.add_field(
        name="例子",
        value=("`!weather`\n`!weather 沙田`\n`!weather 觀塘`"),
        inline=False,
    )
    await ctx.reply(embed=embed)


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        return  # Silently ignore unrecognised commands.
    logger.error("Command error in '%s': %s", ctx.command, error)
    await ctx.reply(f"❌ 發生錯誤：{error}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        logger.error(
            "DISCORD_BOT_TOKEN is not set. "
            "Add it to Railway environment variables or your local .env file."
        )
        raise SystemExit(1)
    logger.info("Starting Discord weather-reminder bot…")
    bot.run(token)


if __name__ == "__main__":
    main()
