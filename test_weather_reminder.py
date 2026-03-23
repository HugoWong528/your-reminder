"""
Tests for weather_reminder.py

Run with: python -m pytest test_weather_reminder.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
from weather_reminder import (
    WeatherData,
    WeatherFetcher,
    ClothingSuggester,
    WeatherReminder,
    HKOLocationWeatherFetcher,
    DEFAULT_LOCATION,
    AVAILABLE_LOCATIONS,
    SCHOOL_CLOTHING_LIST,
)

# ---------------------------------------------------------------------------
# Sample RSS XML (mimics the HKO RSS feed format)
# ---------------------------------------------------------------------------

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>香港天文台天氣報告</title>
    <item>
      <title>香港天文台於2026年03月23日08時02分發出之天氣報告</title>
      <category>R</category>
      <link>https://www.weather.gov.hk/tc/wxinfo/currwx/current.htm</link>
      <description><![CDATA[
        <p>氣溫 : 22 度</p>
        <p>相對濕度 : 85 %</p>
        <p>吹東北風，風速每小時 15 公里</p>
        <p>天色多雲，間中有驟雨。</p>
      ]]></description>
    </item>
  </channel>
</rss>"""

SAMPLE_RSS_HOT = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>香港天文台報告</title>
      <description><![CDATA[<p>氣溫 : 34 度</p><p>相對濕度 : 70 %</p>]]></description>
    </item>
  </channel>
</rss>"""

SAMPLE_RSS_COLD = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>香港天文台報告</title>
      <description><![CDATA[<p>氣溫 : 8 度</p><p>相對濕度 : 60 %</p>]]></description>
    </item>
  </channel>
</rss>"""

SAMPLE_RSS_WINDY = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>香港天文台報告</title>
      <description><![CDATA[<p>氣溫 : 18 度</p><p>相對濕度 : 75 %</p><p>吹東北風，風速每小時 50 公里</p>]]></description>
    </item>
  </channel>
</rss>"""

SAMPLE_RSS_NO_TEMP = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>香港天文台報告</title>
      <description><![CDATA[<p>天氣情況未能確定。</p>]]></description>
    </item>
  </channel>
</rss>"""

# ---------------------------------------------------------------------------
# WeatherFetcher tests
# ---------------------------------------------------------------------------


class TestWeatherFetcher:
    def setup_method(self):
        self.fetcher = WeatherFetcher()

    def test_parse_standard_sample(self):
        data = self.fetcher._parse(SAMPLE_RSS)
        assert data.temperature_c == 22.0
        assert data.humidity_pct == 85.0
        assert data.wind_speed_kmh == 15.0
        assert "2026" in data.report_time

    def test_parse_hot_weather(self):
        data = self.fetcher._parse(SAMPLE_RSS_HOT)
        assert data.temperature_c == 34.0
        assert data.humidity_pct == 70.0

    def test_parse_cold_weather(self):
        data = self.fetcher._parse(SAMPLE_RSS_COLD)
        assert data.temperature_c == 8.0

    def test_parse_missing_temperature(self):
        data = self.fetcher._parse(SAMPLE_RSS_NO_TEMP)
        assert data.temperature_c is None

    def test_parse_windy(self):
        data = self.fetcher._parse(SAMPLE_RSS_WINDY)
        assert data.wind_speed_kmh == 50.0

    def test_rain_in_description(self):
        data = self.fetcher._parse(SAMPLE_RSS)
        assert "驟雨" in data.description or "rain" in data.description.lower()

    def test_fetch_calls_urlopen(self):
        mock_response = MagicMock()
        mock_response.read.return_value = SAMPLE_RSS.encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            data = self.fetcher.fetch()

        assert data.temperature_c == 22.0

    def test_fetch_raises_on_network_error(self):
        import urllib.error

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            with pytest.raises(RuntimeError, match="Cannot reach HKO RSS feed"):
                self.fetcher.fetch()

    def test_parse_invalid_xml_raises(self):
        with pytest.raises(RuntimeError, match="Invalid XML"):
            self.fetcher._parse("<<not valid xml>>")


# ---------------------------------------------------------------------------
# ClothingSuggester tests
# ---------------------------------------------------------------------------


class TestClothingSuggester:
    def setup_method(self):
        self.suggester = ClothingSuggester()

    def _make_weather(self, temp=None, humid=None, wind=None, desc=""):
        return WeatherData(
            temperature_c=temp,
            humidity_pct=humid,
            wind_speed_kmh=wind,
            description=desc,
        )

    def test_very_cold_suggests_heavy_coat(self):
        suggestion = self.suggester.suggest(self._make_weather(temp=5))
        assert "厚" in suggestion or "羽絨" in suggestion or "大褸" in suggestion

    def test_cold_suggests_jacket(self):
        suggestion = self.suggester.suggest(self._make_weather(temp=13))
        assert "外套" in suggestion or "毛衣" in suggestion

    def test_mild_suggests_light_layer(self):
        suggestion = self.suggester.suggest(self._make_weather(temp=18))
        assert "外套" in suggestion or "針織" in suggestion

    def test_comfortable_suggests_tshirt(self):
        suggestion = self.suggester.suggest(self._make_weather(temp=22))
        assert "T 恤" in suggestion or "長袖" in suggestion or "短袖" in suggestion

    def test_warm_suggests_light_clothes(self):
        suggestion = self.suggester.suggest(self._make_weather(temp=28))
        assert "短袖" in suggestion or "輕薄" in suggestion

    def test_hot_suggests_breathable(self):
        suggestion = self.suggester.suggest(self._make_weather(temp=34))
        assert "透氣" in suggestion or "炎熱" in suggestion or "防曬" in suggestion

    def test_high_humidity_note(self):
        suggestion = self.suggester.suggest(self._make_weather(temp=25, humid=90))
        assert "濕度" in suggestion or "透氣" in suggestion

    def test_low_humidity_note(self):
        suggestion = self.suggester.suggest(self._make_weather(temp=22, humid=35))
        assert "濕度" in suggestion or "補濕" in suggestion

    def test_strong_wind_note(self):
        suggestion = self.suggester.suggest(self._make_weather(temp=20, wind=45))
        assert "風" in suggestion

    def test_rain_in_description_umbrella_hint(self):
        suggestion = self.suggester.suggest(
            self._make_weather(temp=22, desc="間中有驟雨")
        )
        assert "雨傘" in suggestion or "☂" in suggestion

    def test_no_temperature_returns_warning(self):
        suggestion = self.suggester.suggest(self._make_weather(temp=None))
        assert "無法" in suggestion or "⚠" in suggestion

    def test_ai_suggestion_fallback_on_error(self):
        """If AI call fails with a network error, rule-based suggestion is returned."""
        import urllib.error

        suggester = ClothingSuggester(pollinations_api_key="fake-key")
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("network error"),
        ):
            suggestion = suggester.suggest(self._make_weather(temp=22))
        # Should not raise; falls back to rules
        assert len(suggestion) > 0

    def test_ai_suggestion_called_when_key_present(self):
        """AI endpoint is called when API key is set."""
        mock_response = MagicMock()
        mock_response.read.return_value = json_response(
            "建議穿短袖，帶備雨傘。"
        )
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        suggester = ClothingSuggester(pollinations_api_key="sk_test_key")
        with patch("urllib.request.urlopen", return_value=mock_response) as mock_open:
            suggestion = suggester.suggest(self._make_weather(temp=22, humid=85))

        mock_open.assert_called_once()
        assert "建議穿短袖" in suggestion


# ---------------------------------------------------------------------------
# WeatherReminder tests
# ---------------------------------------------------------------------------


class TestWeatherReminder:
    def test_run_once_returns_formatted_reminder(self):
        fetcher = WeatherFetcher()
        fetcher.fetch = MagicMock(
            return_value=WeatherData(
                report_time="香港天文台報告",
                temperature_c=22.0,
                humidity_pct=85.0,
                wind_speed_kmh=15.0,
                wind_direction="東北",
            )
        )
        reminder = WeatherReminder(fetcher=fetcher)
        output = reminder.run_once()

        assert "22" in output
        assert "85" in output
        assert "東北" in output
        assert "著衫建議" in output

    def test_run_once_handles_fetch_error(self, capsys):
        fetcher = WeatherFetcher()
        fetcher.fetch = MagicMock(side_effect=RuntimeError("no network"))
        reminder = WeatherReminder(fetcher=fetcher)
        output = reminder.run_once()

        assert "無法獲取" in output


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

import json


def json_response(content: str) -> bytes:
    return json.dumps(
        {"choices": [{"message": {"content": content, "role": "assistant"}}]}
    ).encode("utf-8")


# ---------------------------------------------------------------------------
# HKOLocationWeatherFetcher tests
# ---------------------------------------------------------------------------

SAMPLE_RHRREAD = {
    "temperature": {
        "data": [
            {"place": "元朗公園", "value": 27, "unit": "C"},
            {"place": "沙田", "value": 25, "unit": "C"},
            {"place": "香港天文台", "value": 24, "unit": "C"},
        ],
        "recordTime": "2026-03-23T08:00:00+08:00",
    },
    "humidity": {
        "data": [{"place": "香港天文台", "value": 82, "unit": "percent"}],
        "recordTime": "2026-03-23T08:00:00+08:00",
    },
}


class TestHKOLocationWeatherFetcher:
    def _mock_rhrread(self, fetcher):
        fetcher._fetch_rhrread = MagicMock(return_value=SAMPLE_RHRREAD)

    def _mock_rss(self, fetcher):
        fetcher._rss_fetcher = MagicMock()
        fetcher._rss_fetcher.fetch.return_value = WeatherData(
            temperature_c=22.0,
            humidity_pct=85.0,
            wind_speed_kmh=15.0,
            wind_direction="東北",
            description="間中有驟雨",
        )

    def test_default_location_is_yuenlong_park(self):
        fetcher = HKOLocationWeatherFetcher()
        assert fetcher.station == "元朗公園"

    def test_alias_resolution(self):
        assert HKOLocationWeatherFetcher(station="元朗").station == "元朗公園"
        assert HKOLocationWeatherFetcher(station="荃灣").station == "荃灣城門谷"
        assert HKOLocationWeatherFetcher(station="中環").station == "香港天文台"

    def test_station_temperature_overrides_rss(self):
        fetcher = HKOLocationWeatherFetcher(station="元朗公園")
        self._mock_rss(fetcher)
        self._mock_rhrread(fetcher)
        weather = fetcher.fetch()
        # rhrread says 27°C for 元朗公園; RSS said 22°C → should be 27°C
        assert weather.temperature_c == 27.0

    def test_missing_station_keeps_rss_temperature(self):
        fetcher = HKOLocationWeatherFetcher(station="塔門")
        self._mock_rss(fetcher)
        fetcher._fetch_rhrread = MagicMock(return_value=SAMPLE_RHRREAD)
        weather = fetcher.fetch()
        # 塔門 is not in the mock rhrread, so RSS temperature (22°C) is kept
        assert weather.temperature_c == 22.0

    def test_humidity_filled_from_rhrread_when_rss_absent(self):
        fetcher = HKOLocationWeatherFetcher(station="元朗公園")
        # RSS returns no humidity
        fetcher._rss_fetcher = MagicMock()
        fetcher._rss_fetcher.fetch.return_value = WeatherData(temperature_c=22.0)
        self._mock_rhrread(fetcher)
        weather = fetcher.fetch()
        assert weather.humidity_pct == 82.0

    def test_rhrread_failure_falls_back_to_rss(self):
        fetcher = HKOLocationWeatherFetcher(station="元朗公園")
        self._mock_rss(fetcher)
        fetcher._fetch_rhrread = MagicMock(side_effect=RuntimeError("network error"))
        weather = fetcher.fetch()
        # RSS temperature kept when rhrread fails
        assert weather.temperature_c == 22.0

    def test_available_locations_constant(self):
        assert "元朗公園" in AVAILABLE_LOCATIONS
        assert "元朗" in AVAILABLE_LOCATIONS
        assert DEFAULT_LOCATION == "元朗公園"


# ---------------------------------------------------------------------------
# ClothingSuggester – school / street mode tests
# ---------------------------------------------------------------------------


class TestClothingSuggesterModes:
    def _make_weather(self, temp=None, humid=None, wind=None, desc=""):
        return WeatherData(
            temperature_c=temp,
            humidity_pct=humid,
            wind_speed_kmh=wind,
            description=desc,
        )

    # --- Rule-based school suggestions ---

    def test_school_very_cold_includes_校褸(self):
        s = ClothingSuggester()
        tip = s._rule_suggest_school(self._make_weather(temp=8))
        assert "校褸" in tip

    def test_school_cold_includes_long_sleeve(self):
        s = ClothingSuggester()
        tip = s._rule_suggest_school(self._make_weather(temp=13))
        assert "長袖恤衫" in tip

    def test_school_cool_includes_vest_or_long_sweater(self):
        s = ClothingSuggester()
        tip = s._rule_suggest_school(self._make_weather(temp=18))
        assert "毛衣" in tip

    def test_school_comfortable_short_sleeve(self):
        s = ClothingSuggester()
        tip = s._rule_suggest_school(self._make_weather(temp=22))
        assert "短袖恤衫" in tip

    def test_school_hot_short_sleeve(self):
        s = ClothingSuggester()
        tip = s._rule_suggest_school(self._make_weather(temp=30))
        assert "短袖恤衫" in tip

    def test_school_windy_includes_pe_jacket(self):
        s = ClothingSuggester()
        tip = s._rule_suggest_school(self._make_weather(temp=22, wind=30))
        assert "PE 外套" in tip or "風褸" in tip

    def test_school_rainy_includes_umbrella(self):
        s = ClothingSuggester()
        tip = s._rule_suggest_school(self._make_weather(temp=22, desc="有驟雨"))
        assert "雨傘" in tip

    def test_school_no_temperature_warning(self):
        s = ClothingSuggester()
        tip = s._rule_suggest_school(self._make_weather(temp=None))
        assert "⚠️" in tip

    # --- suggest_with_mode falls back to rules when AI fails ---

    def test_suggest_with_mode_school_fallback(self):
        import urllib.error

        s = ClothingSuggester(pollinations_api_key="fake")
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("network error"),
        ):
            tip = s.suggest_with_mode(self._make_weather(temp=22), mode="school")
        assert len(tip) > 0  # rule-based fallback produced output

    def test_suggest_with_mode_street_fallback(self):
        import urllib.error

        s = ClothingSuggester(pollinations_api_key="fake")
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("network error"),
        ):
            tip = s.suggest_with_mode(self._make_weather(temp=22), mode="street")
        assert len(tip) > 0

    def test_suggest_with_mode_school_ai_success(self):
        """AI is called and its response is returned for school mode."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json_response("建議穿長袖恤衫加校褸。")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        s = ClothingSuggester(pollinations_api_key="sk_test")
        with patch("urllib.request.urlopen", return_value=mock_resp):
            tip = s.suggest_with_mode(
                self._make_weather(temp=15, humid=70), mode="school"
            )
        assert "長袖恤衫" in tip or "校褸" in tip

    def test_suggest_with_mode_street_ai_success(self):
        """AI is called and its response is returned for street mode."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json_response("今日涼快，著件薄外套出街啦。")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        s = ClothingSuggester()
        with patch("urllib.request.urlopen", return_value=mock_resp):
            tip = s.suggest_with_mode(
                self._make_weather(temp=18, humid=75), mode="street"
            )
        assert "外套" in tip

    def test_school_clothing_list_constant_exists(self):
        assert "恤衫" in SCHOOL_CLOTHING_LIST
        assert "校褸" in SCHOOL_CLOTHING_LIST
        assert "PE 外套" in SCHOOL_CLOTHING_LIST

