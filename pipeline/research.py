from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime


class ResilientWikipediaResearchBackend:
    """Wikipedia adapter with polite throttling and bounded retry handling."""

    api = "https://en.wikipedia.org/w/api.php"

    def __init__(
        self,
        max_attempts: int = 5,
        base_delay: float = 1.0,
        max_results_per_query: int = 3,
        max_document_chars: int = 2400,
    ):
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if max_results_per_query < 1:
            raise ValueError("max_results_per_query must be at least 1")
        if max_document_chars < 500:
            raise ValueError("max_document_chars must be at least 500")
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_results_per_query = max_results_per_query
        self.max_document_chars = max_document_chars
        self._last_request_at = 0.0

    def _wait_for_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        minimum_interval = 0.5
        if elapsed < minimum_interval:
            time.sleep(minimum_interval - elapsed)

    def _retry_delay(self, exc: urllib.error.HTTPError, attempt: int) -> float:
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        if retry_after:
            try:
                return max(float(retry_after), 0.0)
            except ValueError:
                try:
                    retry_at = parsedate_to_datetime(retry_after).timestamp()
                    return max(retry_at - time.time(), 0.0)
                except (TypeError, ValueError, OverflowError):
                    pass
        return self.base_delay * (2 ** (attempt - 1))

    def _get_json(self, params: dict[str, object]) -> dict:
        query = urllib.parse.urlencode(params)
        request = urllib.request.Request(
            f"{self.api}?{query}",
            headers={
                "User-Agent": "youtube-no-face/0.3 (https://github.com/aNoobFrevr/youtube_no_face)",
                "Accept": "application/json",
            },
        )

        for attempt in range(1, self.max_attempts + 1):
            self._wait_for_rate_limit()
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    self._last_request_at = time.monotonic()
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                self._last_request_at = time.monotonic()
                if exc.code not in {429, 500, 502, 503, 504} or attempt == self.max_attempts:
                    raise
                time.sleep(self._retry_delay(exc, attempt))

        raise RuntimeError("Wikipedia request retry loop exited unexpectedly")

    def _search_once(self, query: str, limit: int) -> list[dict[str, str]]:
        payload = self._get_json(
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
                "srprop": "snippet",
                "format": "json",
                "utf8": 1,
                "maxlag": 5,
            }
        )
        return [
            {
                "title": item["title"],
                "url": "https://en.wikipedia.org/wiki/"
                + urllib.parse.quote(item["title"].replace(" ", "_")),
                "snippet": re.sub(r"<[^>]+>", "", item.get("snippet", "")),
            }
            for item in payload["query"]["search"]
        ]

    def _search_variants(self, query: str) -> list[str]:
        lowered = query.casefold()
        variants = [query]

        # Natural-language example questions often search poorly on Wikipedia.
        # Add encyclopaedic phrases that describe the underlying phenomenon,
        # while still letting the later relevance gate reject weak matches.
        if "gravity" in lowered and any(word in lowered for word in ("example", "examples", "places", "locations")):
            variants.extend(
                [
                    "gravity of Earth latitude equator poles altitude",
                    "Earth gravity variation highest lowest locations",
                    "gravity anomaly Earth regional variation",
                ]
            )
        elif "gravity" in lowered and any(word in lowered for word in ("measure", "measurement", "instrument", "detect")):
            variants.extend(["gravimetry gravimeter", "gravity of Earth measurement"])
        elif "gravity" in lowered and any(word in lowered for word in ("cause", "causes", "variation", "different")):
            variants.extend(["gravity of Earth variation latitude altitude", "Earth gravity field"])

        deduplicated: list[str] = []
        seen: set[str] = set()
        for variant in variants:
            normalized = " ".join(variant.split()).casefold()
            if normalized not in seen:
                seen.add(normalized)
                deduplicated.append(variant)
        return deduplicated

    def search(self, query: str, limit: int = 3) -> list[dict[str, str]]:
        bounded_limit = min(limit, self.max_results_per_query)
        results: list[dict[str, str]] = []
        seen_urls: set[str] = set()

        for variant in self._search_variants(query):
            for item in self._search_once(variant, bounded_limit):
                if item["url"] in seen_urls:
                    continue
                seen_urls.add(item["url"])
                results.append(item)
                if len(results) >= bounded_limit:
                    return results

        return results

    def fetch(self, url: str) -> str:
        title = urllib.parse.unquote(url.rsplit("/", 1)[-1]).replace("_", " ")
        payload = self._get_json(
            {
                "action": "query",
                "prop": "extracts",
                "explaintext": 1,
                "redirects": 1,
                "titles": title,
                "format": "json",
                "maxlag": 5,
            }
        )
        page = next(iter(payload["query"]["pages"].values()))
        return page.get("extract", "")[: self.max_document_chars]
