#!/usr/bin/env python3
"""
weather_reminder.py

Auto-remind feature: fetches current weather from the Hong Kong Observatory RSS feed,
then suggests what clothes to wear. Optionally uses the pollinations.ai API for
AI-powered clothing advice.

RSS source: https://rss.weather.gov.hk/rss/CurrentWeather_uc.xml
"""

import os
import re
import sys
import html
import logging
import urllib.request
import urllib.error
import urllib.parse
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

try:
    import schedule
    import time
    SCHEDULE_AVAILABLE = True
except ImportError:
    SCHEDULE_AVAILABLE = False

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
# Constants
# ---------------------------------------------------------------------------

HKO_RSS_URL = "https://rss.weather.gov.hk/rss/CurrentWeather_uc.xml"
POLLINATIONS_API_URL = "https://gen.pollinations.ai/v1/chat/completions"
REQUEST_TIMEOUT = 15  # seconds

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class WeatherData:
    """Parsed weather information from the HKO RSS feed."""

    report_time: str = ""
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    description: str = ""
    wind_direction: str = ""
    wind_speed_kmh: Optional[float] = None
    weather_icon: str = ""
    raw_description: str = ""


# ---------------------------------------------------------------------------
# Weather fetcher
# ---------------------------------------------------------------------------


class WeatherFetcher:
    """Fetches and parses the Hong Kong Observatory current weather RSS feed."""

    def __init__(self, url: str = HKO_RSS_URL, timeout: int = REQUEST_TIMEOUT):
        self.url = url
        self.timeout = timeout

    def fetch(self) -> WeatherData:
        """Fetch and return parsed WeatherData."""
        logger.info("Fetching weather from %s", self.url)
        try:
            req = urllib.request.Request(
                self.url,
                headers={"User-Agent": "your-reminder/1.0 (HK weather auto-remind; +https://github.com/HugoWong528/your-reminder)"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                raw_xml = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            logger.error("Failed to fetch weather data: %s", exc)
            raise RuntimeError(f"Cannot reach HKO RSS feed: {exc}") from exc

        return self._parse(raw_xml)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse(self, raw_xml: str) -> WeatherData:
        """Parse raw RSS XML and return a WeatherData object."""
        # Strip any leading BOM or processing instruction that may confuse the parser
        xml_body = re.sub(r"<\?xml-stylesheet[^?]*\?>", "", raw_xml).strip()

        try:
            root = ET.fromstring(xml_body)
        except ET.ParseError as exc:
            logger.error("Failed to parse XML: %s", exc)
            raise RuntimeError(f"Invalid XML from HKO RSS: {exc}") from exc

        # RSS structure: <rss><channel><item>...</item></channel></rss>
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        item = root.find(".//item")
        if item is None:
            raise RuntimeError("No <item> found in HKO RSS XML")

        data = WeatherData()

        title_el = item.find("title")
        if title_el is not None and title_el.text:
            data.report_time = title_el.text.strip()

        desc_el = item.find("description")
        if desc_el is not None:
            raw_desc = desc_el.text or ""
            data.raw_description = raw_desc
            self._parse_description(raw_desc, data)

        return data

    def _parse_description(self, raw_html: str, data: WeatherData) -> None:
        """Extract weather fields from the HTML description."""
        # Unescape HTML entities and strip tags for plain text matching
        text = html.unescape(raw_html)
        plain = re.sub(r"<[^>]+>", " ", text)
        plain = re.sub(r"\s+", " ", plain).strip()
        data.description = plain

        # Temperature: e.g. "氣溫 : 22 度" or "溫度 : 22°C" or "Temperature : 22 degrees"
        temp_match = re.search(
            r"(?:氣溫|溫度|Temperature)[^0-9]*([0-9]+(?:\.[0-9]+)?)\s*(?:度|°C|degrees?)",
            plain,
            re.IGNORECASE,
        )
        if temp_match:
            data.temperature_c = float(temp_match.group(1))

        # Humidity: e.g. "相對濕度 : 85 %" or "Relative Humidity : 85 per cent"
        humid_match = re.search(
            r"(?:相對濕度|Relative Humidity)[^0-9]*([0-9]+(?:\.[0-9]+)?)\s*(?:%|per cent)",
            plain,
            re.IGNORECASE,
        )
        if humid_match:
            data.humidity_pct = float(humid_match.group(1))

        # Wind: e.g. "風速每小時 15 公里" or "Wind speed 15 kilometres per hour"
        wind_speed_match = re.search(
            r"(?:風速|wind speed)[^0-9]*([0-9]+(?:\.[0-9]+)?)\s*(?:公里|km|kilometres?)",
            plain,
            re.IGNORECASE,
        )
        if wind_speed_match:
            data.wind_speed_kmh = float(wind_speed_match.group(1))

        # Wind direction: e.g. "東北" or "北" or "Northeast"
        wind_dir_match = re.search(
            r"(?:wind|吹|風向)[^\u0000-\u007F\s]{0,4}(東北|東南|西北|西南|東|西|南|北|"
            r"North|South|East|West|Northeast|Northwest|Southeast|Southwest)",
            plain,
            re.IGNORECASE,
        )
        if wind_dir_match:
            data.wind_direction = wind_dir_match.group(1)


# ---------------------------------------------------------------------------
# Clothing suggester
# ---------------------------------------------------------------------------


class ClothingSuggester:
    """
    Generates clothing suggestions based on weather data.
    Provides rule-based suggestions and optionally AI-powered suggestions
    via the pollinations.ai API.
    """

    def __init__(self, pollinations_api_key: Optional[str] = None):
        self.pollinations_api_key = pollinations_api_key or os.environ.get(
            "POLLINATIONS_API_KEY"
        )

    def suggest(self, weather: WeatherData) -> str:
        """Return a clothing suggestion string for the given weather."""
        # Try AI suggestion first if an API key is available
        if self.pollinations_api_key:
            try:
                return self._ai_suggest(weather)
            except (urllib.error.URLError, json.JSONDecodeError, KeyError, ValueError) as exc:
                logger.warning("AI suggestion failed (%s); falling back to rules", exc)

        return self._rule_suggest(weather)

    # ------------------------------------------------------------------
    # Rule-based suggestion
    # ------------------------------------------------------------------

    def _rule_suggest(self, weather: WeatherData) -> str:
        """Simple temperature + humidity based clothing rules."""
        temp = weather.temperature_c
        humid = weather.humidity_pct
        wind = weather.wind_speed_kmh

        lines: list[str] = []

        if temp is None:
            lines.append("⚠️  無法獲取溫度資訊，建議留意天文台最新公告。")
            return "\n".join(lines)

        # --- Base layer by temperature ---
        if temp < 10:
            lines.append("🧥 氣溫極低！建議穿厚羽絨外套或大褸，注意保暖。")
            lines.append("   內裡多層：保暖底衫 + 厚毛衣 + 厚褲。")
        elif temp < 15:
            lines.append("🧥 天氣寒冷，建議穿外套或厚毛衣，搭配長褲。")
        elif temp < 20:
            lines.append("🧣 天氣涼快，建議穿薄外套或針織衫，長褲為宜。")
        elif temp < 25:
            lines.append("👕 天氣舒適，薄身長袖或短袖 T 恤加薄外套即可。")
        elif temp < 30:
            lines.append("👕 天氣溫暖，穿短袖或輕薄衣物，保持涼爽。")
        else:
            lines.append("🌞 天氣炎熱！建議穿透氣短袖、薄料衣物，注意防曬。")

        # --- Humidity adjustment ---
        if humid is not None and humid >= 80:
            lines.append("💧 濕度高，選擇透氣排汗布料，避免悶熱不適。")
        elif humid is not None and humid <= 40:
            lines.append("💨 濕度低，皮膚容易乾燥，注意補濕。")

        # --- Wind adjustment ---
        if wind is not None and wind >= 40:
            lines.append("🌬️  風力強勁，出門帶備防風外套，小心大風。")
        elif wind is not None and wind >= 20:
            lines.append("🌬️  有微風，披件薄外套會更舒適。")

        # --- Rain hint from description ---
        desc_lower = weather.description.lower()
        if any(kw in desc_lower for kw in ["rain", "shower", "雨", "驟雨"]):
            lines.append("☂️  有雨，記得帶雨傘！")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # AI-powered suggestion via pollinations.ai
    # ------------------------------------------------------------------

    def _ai_suggest(self, weather: WeatherData) -> str:
        """Request a clothing suggestion from pollinations.ai."""
        prompt = self._build_prompt(weather)
        payload = {
            "model": "openai",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你係一個香港天氣助手，根據用戶提供嘅天氣資訊，"
                        "用廣東話建議今日應該著咩衫，語氣親切簡潔，150字以內。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 300,
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            POLLINATIONS_API_URL,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.pollinations_api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        return result["choices"][0]["message"]["content"].strip()

    def _build_prompt(self, weather: WeatherData) -> str:
        parts = []
        if weather.temperature_c is not None:
            parts.append(f"氣溫: {weather.temperature_c}°C")
        if weather.humidity_pct is not None:
            parts.append(f"相對濕度: {weather.humidity_pct}%")
        if weather.wind_speed_kmh is not None:
            parts.append(f"風速: {weather.wind_speed_kmh} km/h")
        if weather.wind_direction:
            parts.append(f"風向: {weather.wind_direction}")
        if weather.description:
            # Limit description length for the prompt
            parts.append(f"天氣情況: {weather.description[:200]}")
        return "，".join(parts) if parts else "天氣資料未能獲取"


# ---------------------------------------------------------------------------
# Weather reminder (orchestrator)
# ---------------------------------------------------------------------------


class WeatherReminder:
    """
    Orchestrates weather fetching and clothing suggestions.
    Can run once or be scheduled for recurring reminders.
    """

    def __init__(
        self,
        fetcher: Optional[WeatherFetcher] = None,
        suggester: Optional[ClothingSuggester] = None,
    ):
        self.fetcher = fetcher or WeatherFetcher()
        self.suggester = suggester or ClothingSuggester()

    def run_once(self) -> str:
        """Fetch weather, generate suggestion, print and return the reminder."""
        try:
            weather = self.fetcher.fetch()
        except RuntimeError as exc:
            msg = f"❌ 無法獲取天氣資訊：{exc}"
            logger.error(msg)
            print(msg)
            return msg

        suggestion = self.suggester.suggest(weather)
        reminder = self._format_reminder(weather, suggestion)
        print(reminder)
        return reminder

    def schedule_daily(self, times: list[str]) -> None:
        """
        Schedule the reminder to run at specified times each day.

        Args:
            times: List of time strings in "HH:MM" format, e.g. ["07:30", "08:00"]
        """
        if not SCHEDULE_AVAILABLE:
            logger.error(
                "'schedule' library not installed. Run: pip install schedule"
            )
            sys.exit(1)

        for t in times:
            schedule.every().day.at(t).do(self.run_once)
            logger.info("Scheduled daily reminder at %s", t)

        logger.info("Weather reminder scheduler started. Press Ctrl+C to stop.")
        try:
            while True:
                schedule.run_pending()
                time.sleep(max(1, schedule.idle_seconds() or 1))
        except KeyboardInterrupt:
            logger.info("Scheduler stopped.")

    # ------------------------------------------------------------------

    @staticmethod
    def _format_reminder(weather: WeatherData, suggestion: str) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        separator = "─" * 50
        lines = [
            separator,
            f"🌤  香港天氣提示  ({now})",
            separator,
        ]
        if weather.report_time:
            lines.append(f"📋 {weather.report_time}")
        if weather.temperature_c is not None:
            lines.append(f"🌡️  氣溫：{weather.temperature_c}°C")
        if weather.humidity_pct is not None:
            lines.append(f"💧 相對濕度：{weather.humidity_pct}%")
        if weather.wind_speed_kmh is not None:
            wind_info = f"🌬️  風速：{weather.wind_speed_kmh} km/h"
            if weather.wind_direction:
                wind_info += f"  ({weather.wind_direction})"
            lines.append(wind_info)
        lines.append(separator)
        lines.append("👗 今日著衫建議：")
        lines.append(suggestion)
        lines.append(separator)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="香港天氣自動提示 – 獲取天氣並建議著咩衫",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例子:
  python weather_reminder.py                      # 即時執行一次
  python weather_reminder.py --schedule 07:30     # 每日 07:30 提醒
  python weather_reminder.py --schedule 07:30 08:00 12:00
""",
    )
    parser.add_argument(
        "--schedule",
        metavar="HH:MM",
        nargs="+",
        help="每日提醒時間（可指定多個），例如 07:30 12:00",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="pollinations.ai API key（可用環境變數 POLLINATIONS_API_KEY 代替）",
    )
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("POLLINATIONS_API_KEY")
    reminder = WeatherReminder(suggester=ClothingSuggester(pollinations_api_key=api_key))

    if args.schedule:
        reminder.schedule_daily(args.schedule)
    else:
        reminder.run_once()


if __name__ == "__main__":
    main()
