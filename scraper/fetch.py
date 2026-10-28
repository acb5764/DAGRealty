"""Polite HTTP client for scraping the USAMLS office-listings pages.

Identifies itself with a descriptive User-Agent, checks robots.txt once per
process, and rate-limits sequential requests. This is the client's own
publicly-displayed listing data (not a third party's), but we still avoid
hammering the source.
"""

import random
import time
import urllib.robotparser
from urllib.parse import urljoin

import requests

BASE = "https://www.usamls.net"
OFFICE_LISTINGS_PATH = "/dgrealestate/default.asp"
USER_AGENT = "DAGRealtyBot/1.0 (+contact: mackenziergardner@gmail.com)"
MIN_DELAY_SECONDS = 1.0
MAX_JITTER_SECONDS = 0.5


class ScraperBlockedError(RuntimeError):
    """Raised when robots.txt disallows the path we need to fetch."""


class RateLimitedSession:
    """A requests.Session that checks robots.txt once and sleeps between
    every request, so a full scrape run never fires concurrent or
    back-to-back requests at the source."""

    def __init__(self, base: str = BASE, user_agent: str = USER_AGENT):
        self.base = base
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self._last_request_at = 0.0
        self._robots = urllib.robotparser.RobotFileParser()
        self._robots.set_url(urljoin(base, "/robots.txt"))
        self._read_robots()

    def _read_robots(self) -> None:
        # Deliberately not self._robots.read() -- it always fetches via
        # urllib.request.urlopen() with Python's bare default User-Agent,
        # ignoring the descriptive one set above. usamls.net's WAF 403s
        # that generic UA string specifically, and RobotFileParser treats
        # ANY 401/403 on robots.txt itself as "disallow everything" (see
        # its source) -- even though the site's actual published robots.txt
        # is wide open (`Allow: /`) once fetched with a real UA, same as
        # every other page this session fetches. Fetching the text
        # ourselves and handing it to .parse() avoids that false block.
        try:
            resp = self.session.get(self._robots.url, timeout=20)
            resp.raise_for_status()
        except requests.RequestException:
            # A genuine failure to reach robots.txt (not the UA-sniffing
            # false-403 above, which raise_for_status would also catch) --
            # fall back to the same conservative default RobotFileParser
            # itself uses on a real error.
            self._robots.disallow_all = True
            return
        self._robots.parse(resp.text.splitlines())

    def _check_allowed(self, url: str) -> None:
        if not self._robots.can_fetch(self.session.headers["User-Agent"], url):
            raise ScraperBlockedError(f"robots.txt disallows fetching {url}")

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait = MIN_DELAY_SECONDS - elapsed + random.uniform(0, MAX_JITTER_SECONDS)
        if wait > 0:
            time.sleep(wait)

    def get(self, path: str, params: dict | None = None, retries: int = 3) -> str:
        url = urljoin(self.base, path)
        self._check_allowed(url)
        last_exc: Exception | None = None
        for attempt in range(retries):
            self._throttle()
            try:
                resp = self.session.get(url, params=params, timeout=20)
                self._last_request_at = time.monotonic()
                resp.raise_for_status()
                return resp.text
            except requests.RequestException as exc:
                last_exc = exc
                backoff = (2**attempt) + random.uniform(0, 1)
                time.sleep(backoff)
        raise RuntimeError(f"failed to fetch {url} after {retries} attempts") from last_exc

    def get_bytes(self, url: str, retries: int = 3) -> bytes:
        self._check_allowed(url)
        last_exc: Exception | None = None
        for attempt in range(retries):
            self._throttle()
            try:
                resp = self.session.get(url, timeout=30)
                self._last_request_at = time.monotonic()
                resp.raise_for_status()
                return resp.content
            except requests.RequestException as exc:
                last_exc = exc
                backoff = (2**attempt) + random.uniform(0, 1)
                time.sleep(backoff)
        raise RuntimeError(f"failed to fetch {url} after {retries} attempts") from last_exc
