from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

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
            titles = [
                re.sub(r"\s+", " ", "".join(item.itertext())).strip()
                for item in root.findall(".//item/title")[:5]
            ]
            titles = [title[:180] for title in titles if title]
            if titles:
                sources.append("Google News RSS leads: " + "; ".join(titles))
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
        if isinstance(summary, str) and summary.strip():
            sources.append("DuckDuckGo context: " + re.sub(r"\s+", " ", summary)[:700])
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
    detailed = len(prompt.split()) >= 25
    documentary = bool(
        _DOCUMENTARY_TERMS.search(prompt)
        or detailed
        or format_hint == "landscape"
        or (explicit_duration is not None and explicit_duration >= 120)
    )
    if documentary:
        duration = documentary_duration_seconds(prompt, explicit_duration or 120)
        route_format = "landscape"
        flags = f"--movie --duration={duration}s"
        research = fetch_live_research(prompt) if research_enabled else ""
    else:
        duration = max(35, min(48, explicit_duration if explicit_duration is not None else 36))
        route_format = "vertical"
        flags = f"--vertical --duration={duration}s"
        research = ""

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
    )
