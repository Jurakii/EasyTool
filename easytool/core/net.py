"""Small urllib wrapper. Kept behind a class so tests can swap in a fake."""
from __future__ import annotations

import json
import os
import shutil
import socket
import urllib.error
import urllib.parse
import urllib.request

from .. import __version__

TIMEOUT = 20


class NetError(RuntimeError):
    pass


class NotFound(NetError):
    pass


class Http:
    user_agent = f"EasyTool/{__version__}"

    def _request(self, url: str) -> urllib.request.Request:
        headers = {"User-Agent": self.user_agent}
        if "api.github.com" in url:
            headers["Accept"] = "application/vnd.github+json"
            token = os.environ.get("EASYTOOL_GITHUB_TOKEN")
            if token:
                headers["Authorization"] = f"Bearer {token}"
        return urllib.request.Request(url, headers=headers)

    def _open(self, url: str):
        try:
            return urllib.request.urlopen(self._request(url), timeout=TIMEOUT)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise NotFound(f"Not found: {url}") from exc
            if exc.code in (403, 429) and "api.github.com" in url:
                raise NetError(
                    "GitHub's hourly limit for anonymous requests was reached. "
                    "Try again later, or set EASYTOOL_GITHUB_TOKEN."
                ) from exc
            raise NetError(f"{url} returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            host = urllib.parse.urlparse(url).netloc or url
            if isinstance(reason, socket.gaierror):
                raise NetError(f"Couldn't find {host}. Check the address and your internet connection.") from exc
            if isinstance(reason, (socket.timeout, TimeoutError)):
                raise NetError(f"{host} took too long to answer.") from exc
            raise NetError(f"Couldn't reach {host} ({reason})") from exc

    def fetch_bytes(self, url: str) -> bytes:
        with self._open(url) as resp:
            return resp.read()

    def fetch_json(self, url: str):
        data = self.fetch_bytes(url)
        try:
            return json.loads(data.decode("utf-8-sig"))
        except ValueError as exc:
            raise NetError(f"{url} is not valid JSON") from exc

    def download(self, url: str, dest: str) -> None:
        part = dest + ".part"
        with self._open(url) as resp, open(part, "wb") as fh:
            shutil.copyfileobj(resp, fh)
        os.replace(part, dest)
