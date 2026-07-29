from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime


class ResilientWikipediaResearchBackend:
    """Wikipedia adapter with polite throttling and bounded retry handling."""

    api = "https://en.wikipedia.org/w/api.php"

    def __init__(self, max_attempts: int = 5, base_delay: float = 1.0):
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.max_attempts = max_attempts
        self.base_delay = base_delay
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
                "User-Agent": "youtube-no-face/0.1 (https://github.com/aNoobFrevr/youtube_no_face)",
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

    def search(self, query: str, limit: int = 3) -> list[dict[str, str]]:
        payload = self._get_json(
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
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
            }
            for item in payload["query"]["search"]
        ]

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
        return page.get("extract", "")
