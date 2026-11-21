# -*- coding: utf-8 -*-
"""天气服务：和风天气 QWeather 实时查询（带城市解析与缓存），provider=mock 时走内置演示数据。

用法：
    provider = mock    -> 查询内置 WEATHER_DATA，无需 Key（默认，保证无 Key 全链路可用）
    provider = qweather -> 调用和风天气 GeoAPI 解析城市 + Now API 查实况，需 WEATHER_API_KEY
"""
import logging
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------- mock 演示数据（provider=mock 时使用，验收数据可预期） ----------
WEATHER_DATA = {
    "北京": "晴，26 摄氏度，东南风 2 级",
    "上海": "多云，28 摄氏度，湿度 70%",
    "广州": "雷阵雨，30 摄氏度",
    "深圳": "多云转晴，29 摄氏度",
    "杭州": "小雨，24 摄氏度",
}

_GEO_API = "https://geoapi.qweather.com/v2/city/lookup"   # 城市名 -> LocationID
_NOW_API = "https://devapi.qweather.com/v7/weather/now"   # 实况天气

_ERROR_PREFIX = "天气服务暂不可用，请稍后再试"
_KEY_MISSING = "天气服务未配置 API Key（.env 的 WEATHER_API_KEY），当前无法查询实时天气。"


class WeatherService:
    """天气查询服务：mock / qweather 双模式，带 10 分钟内存缓存"""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, str]] = {}

    def get_weather(self, city: str) -> str:
        city = (city or "").strip()
        if not city:
            return "请输入要查询的城市名称。"
        if settings.weather_api_provider == "qweather":
            return self._query_qweather(city)
        return self._query_mock(city)

    # ---------- mock 模式 ----------
    def _query_mock(self, city: str) -> str:
        if city in WEATHER_DATA:
            return f"{city}：{WEATHER_DATA[city]}"
        return f"暂无 {city} 的天气数据，系统内置演示城市：{'、'.join(WEATHER_DATA.keys())}。"

    # ---------- 和风天气模式 ----------
    def _query_qweather(self, city: str) -> str:
        cached = self._cache.get(city)
        if cached and cached[0] > time.time():
            return cached[1]

        if not settings.weather_api_key:
            return _KEY_MISSING

        location_id, service_error = self._lookup_city(city)
        if service_error:
            return _ERROR_PREFIX + "，可稍后重试或稍后再问。"
        if not location_id:
            return f"未找到「{city}」的天气数据，请确认城市名称是否正确。"
        text = self._fetch_now(city, location_id)
        if text is None:
            return _ERROR_PREFIX + "，可稍后重试或稍后再问。"
        self._cache[city] = (time.time() + settings.weather_cache_ttl, text)
        return text

    def _lookup_city(self, city: str) -> tuple[str | None, bool]:
        """城市名 -> (LocationID, 是否服务异常)；城市不存在时返回 (None, False)"""
        try:
            resp = httpx.get(
                _GEO_API,
                params={"location": city, "key": settings.weather_api_key, "number": 1},
                timeout=settings.weather_timeout,
            )
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("城市解析异常 city=%s: %s", city, exc)
            return None, True
        code = str(data.get("code", ""))
        if code == "404" or (code == "200" and not data.get("location")):
            logger.warning("城市不存在 city=%s code=%s", city, code)
            return None, False
        if code != "200" or not data.get("location"):
            logger.warning("城市解析失败 city=%s code=%s", city, code)
            return None, True
        return data["location"][0]["id"], False

    def _fetch_now(self, city: str, location_id: str) -> str | None:
        """实况天气查询并组装中文回复"""
        try:
            resp = httpx.get(
                _NOW_API,
                params={"location": location_id, "key": settings.weather_api_key},
                timeout=settings.weather_timeout,
            )
            data = resp.json()
            if data.get("code") != "200":
                logger.warning("实况查询失败 city=%s code=%s", city, data.get("code"))
                return None
            now = data.get("now") or {}
            parts = [f"{city}：{now.get('text', '未知天气')}"]
            if now.get("temp") is not None:
                parts.append(f"{now['temp']} 摄氏度")
            if now.get("windDir"):
                parts.append(f"{now['windDir']} {now.get('windScale', '')} 级".strip())
            if now.get("humidity") is not None:
                parts.append(f"湿度 {now['humidity']}%")
            return "，".join(parts) + "（和风天气实时数据）"
        except Exception as exc:  # noqa: BLE001
            logger.warning("实况查询异常 city=%s: %s", city, exc)
            return None


weather_service = WeatherService()
