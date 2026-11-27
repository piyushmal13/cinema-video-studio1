from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

try:
    from .longform_director import documentary_duration_seconds
except ImportError:
    from longform_director import documentary_duration_seconds


_DOCUMENTARY_TERMS = re.compile(
    r"\bdocumentary\b|\blong\s+video\b|\b(?:2|3|4|5)\s*[- ]?\s*min(?:ute)?s?\b"
    r"|--minutes\s*=|--movie\b|--cinema\b",
    re.IGNORECASE,
)
_DURATION_FLAG = re.compile(
    r"--duration(?:=|\s+)(\d+(?:\.\d+)?)\s*(seconds?|secs?|s|minutes?|mins?|m)?\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ProductionRoute:
    prompt: str
    format_hint: str
    duration_sec: int
    documentary: bool
    research_context: str = ""
    market_update: bool = False


def _explicit_duration(prompt: str) -> int | None:
    minute_flag = re.search(r"--minutes\s*=\s*(\d+(?:\.\d+)?)", prompt, re.I)
    if minute_flag:
        return round(float(minute_flag.group(1)) * 60)
    flag = _DURATION_FLAG.search(prompt)
    if flag:
        value = float(flag.group(1))
        unit = (flag.group(2) or "seconds").lower()
        return round(value * 60 if unit.startswith("m") else value)
    natural = re.search(
        r"\b(\d+(?:\.\d+)?)\s*[- ]?\s*(seconds?|secs?|minutes?|mins?)\b",
        prompt,
        re.IGNORECASE,
    )
    if natural:
        value = float(natural.group(1))
        unit = natural.group(2).lower()
        return round(value * 60 if unit.startswith("m") else value)
    return None


def _query_text(prompt: str) -> str:
    cleaned = re.sub(r"/(?:video|movie|cinema|reel)(?:@\w+)?", " ", prompt, flags=re.I)
    cleaned = re.sub(r"--[\w=-]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()[:300]


def is_market_update_request(prompt: str) -> bool:
    market_term = bool(re.search(
        r"\b(?:market|markets|forex|fx|xauusd|gold|silver|dxy|nasdaq|nifty|sensex|"
        r"crypto|bitcoin|btc|eurusd|gbpusd|usdjpy|cpi|nfp|fomc|fed|bond yields?)\b",
        prompt, re.I,
    ))
    current_request = bool(re.search(
        r"\b(?:today|aaj|latest|current|update|overview|outlook|right now|this session|"
        r"what happened|what is moving|daily)\b",
        prompt, re.I,
    ))
    return market_term and current_request


def fetch_market_quotes(timeout: float = 3.0) -> str:
    """Fetch timestamped indicative public market quotes; never substitute futures for spot."""
    symbols = [
        ("GC=F", "Gold futures (not XAUUSD spot)"),
        ("DX-Y.NYB", "US Dollar Index"),
        ("^TNX", "US 10-year Treasury yield"),
        ("^NSEI", "NIFTY 50"),
        ("^IXIC", "NASDAQ Composite"),
    ]
    retrieved_at = datetime.now(timezone.utc).astimezone(
        ZoneInfo("Asia/Kolkata")
    ).isoformat(timespec="seconds")
    lines = [f"Market data retrieved at {retrieved_at} (Asia/Kolkata)."]
    for symbol, label in symbols:
        try:
            response = requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                params={"range": "1d", "interval": "5m"},
                headers={"User-Agent": "Mozilla/5.0 CinemaVideoStudio/1.0"},
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            result = payload.get("chart", {}).get("result") or []
            if not result:
                continue
            item = result[0]
            meta = item.get("meta", {})
            quote = (item.get("indicators", {}).get("quote") or [{}])[0]
            closes = quote.get("close") or []
            timestamps = item.get("timestamp") or []
            latest_pair = next(
                ((float(value), int(timestamps[index])) for index, value in reversed(list(enumerate(closes)))
                 if value is not None and index < len(timestamps)),
                None,
            )
            price = meta.get("regularMarketPrice")
            timestamp = meta.get("regularMarketTime")
            if price is None and latest_pair:
                price, timestamp = latest_pair
            if price is None:
                continue
            previous = meta.get("chartPreviousClose") or meta.get("previousClose")
            change = None
            if isinstance(previous, (int, float)) and previous:
                change = (float(price) - float(previous)) / float(previous) * 100
            quote_time = (
                datetime.fromtimestamp(int(timestamp), timezone.utc)
                .astimezone(ZoneInfo("Asia/Kolkata"))
                .isoformat(timespec="minutes")
                if timestamp else "timestamp unavailable"
            )
            currency = str(meta.get("currency") or "")
            price_text = f"{float(price):,.4f} {currency}".strip()
            change_text = f", {change:+.2f}% versus previous close" if change is not None else ""
            lines.append(
                f"{label}: {price_text}{change_text}; quote timestamp {quote_time}; "
                f"source https://finance.yahoo.com/quote/{symbol}"
            )
        except (requests.RequestException, ValueError, TypeError, KeyError, OverflowError) as error:
            print(f"Market quote unavailable for {symbol}: {error}")
    if len(lines) == 1:
        lines.append(
            "No market quote provider returned a usable timestamped value. "
            "Do not invent current prices or percentages."
        )
    lines.append(
        "Instrument caution: GC=F is a gold futures contract and must not be labelled "
        "as XAUUSD spot. Quote timestamps may be delayed or stale outside trading hours."
    )
    return "\n".join(lines)[:3200]


def fetch_market_research(prompt: str, timeout: float = 4.0) -> str:
    news_query = f"{_query_text(prompt)} market drivers today"
    news = fetch_live_research(news_query, timeout=timeout)
    quotes = fetch_market_quotes(timeout=min(timeout, 3.0))
    return "\n\n".join(part for part in (quotes, news) if part)[:5200]


def fetch_live_research(prompt: str, timeout: float = 6.0) -> str:
    """Fetch bounded public RSS/search hints; never treat them as verified facts."""
    query = _query_text(prompt)
    if not query:
        return ""
    sources: list[str] = []
    try:
        response = requests.get(
            "https://news.google.com/rss/search",
            params={"q": query, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"},
            headers={"User-Agent": "CinemaVideoStudio/1.0"},
            timeout=timeout,
        )
        response.raise_for_status()
        if len(response.content) <= 256_000 and not re.search(
            r"<!\s*(?:DOCTYPE|ENTITY)", response.text, re.I
        ):
            root = ET.fromstring(response.text)
            items = root.findall(".//item")[:5]
            for item in items:
                title = re.sub(r"\s+", " ", (item.findtext("title") or "")).strip()
                source = re.sub(r"\s+", " ", (item.findtext("source") or "Google News RSS")).strip()
                link = (item.findtext("link") or "").strip()
                published = re.sub(r"\s+", " ", (item.findtext("pubDate") or "")).strip()
                if title:
                    metadata = "; ".join(part for part in (source, published, link) if part)
                    sources.append(f"Research lead: {title[:180]} ({metadata[:240]})")
    except (requests.RequestException, ET.ParseError, ValueError) as error:
        print(f"Google News research unavailable: {error}")

    try:
        response = requests.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1",
            },
            headers={"User-Agent": "CinemaVideoStudio/1.0"},
            timeout=timeout,
        )
        response.raise_for_status()
        answer = response.json()
        summary = answer.get("AbstractText") or answer.get("Answer") or ""
        abstract_url = answer.get("AbstractURL") or ""
        if isinstance(summary, str) and summary.strip():
            sources.append("Search context: " + re.sub(r"\s+", " ", summary)[:650]
                           + (f" ({abstract_url})" if abstract_url else ""))
        for topic in answer.get("RelatedTopics", [])[:4]:
            if isinstance(topic, dict) and isinstance(topic.get("Text"), str):
                sources.append("Search lead: " + topic["Text"][:180])
    except (requests.RequestException, ValueError, TypeError) as error:
        print(f"DuckDuckGo research unavailable: {error}")

    return "\n".join(sources)[:2400]


def route_production_request(
    prompt: str,
    format_hint: str = "vertical",
    *,
    research_enabled: bool = True,
) -> ProductionRoute:
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("A non-empty prompt is required.")
    if format_hint not in {"vertical", "landscape"}:
        raise ValueError("Format must be 'vertical' or 'landscape'.")

    explicit_duration = _explicit_duration(prompt)
    market_update = is_market_update_request(prompt)
    documentary = bool(
        _DOCUMENTARY_TERMS.search(prompt)
        or format_hint == "landscape"
        or (explicit_duration is not None and explicit_duration >= 120)
    )
    if documentary:
        duration = documentary_duration_seconds(prompt, explicit_duration or 120)
        route_format = "landscape"
        flags = f"--movie --duration={duration}s"
        research = (
            fetch_market_research(prompt) if market_update and research_enabled
            else fetch_live_research(prompt) if research_enabled
            else ""
        )
    elif market_update:
        duration = max(35, min(75, explicit_duration if explicit_duration is not None else 50))
        route_format = "vertical"
        flags = f"--vertical --duration={duration}s"
        research = fetch_market_research(prompt) if research_enabled else ""
    else:
        duration = max(35, min(60, explicit_duration if explicit_duration is not None else 45))
        route_format = "vertical"
        flags = f"--vertical --duration={duration}s"
        research = (
            fetch_live_research(prompt)
            if research_enabled and os.environ.get("CINEMA_RESEARCH_ALL_IFX", "").casefold() in {"1", "true", "yes"}
            else ""
        )

    routed_prompt = re.sub(r"--minutes\s*=\s*\d+(?:\.\d+)?", " ", prompt, flags=re.I)
    routed_prompt = re.sub(
        r"--duration(?:=|\s+)\d+(?:\.\d+)?\s*(?:seconds?|secs?|s|minutes?|mins?|m)?\b",
        " ",
        routed_prompt,
        flags=re.I,
    )
    routed_prompt = re.sub(r"\s+", " ", routed_prompt).strip()
    routed_prompt = f"{routed_prompt} {flags}"
    return ProductionRoute(
        prompt=routed_prompt,
        format_hint=route_format,
        duration_sec=duration,
        documentary=documentary,
        research_context=research,
        market_update=market_update,
    )
