from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

THREADS_MAX = 500


def threads_length(text: str) -> int:
    """Byte-aware length: UTF-8 bytes, so emoji/multibyte chars never slip past the 500 limit."""
    return len(text.encode("utf-8"))


def fit_threads(body: str, suffix: str = "", limit: int = THREADS_MAX) -> str:
    """Trim `body` at a word boundary so that body + suffix fits the byte-aware limit."""
    room = limit - threads_length(suffix)
    if threads_length(body) <= room:
        return body + suffix
    out = ""
    for word in body.split(" "):
        candidate = (out + " " + word).strip()
        if threads_length(candidate + "…") > room:
            break
        out = candidate
    return out.rstrip(" ,.;:") + "…" + suffix


@dataclass
class OutgoingPost:
    id: str
    text: str
    topic_tag: str


@dataclass
class PublishResult:
    external_id: str
    dummy: bool = False


@dataclass
class Quota:
    used: int
    total: int

    @property
    def remaining(self) -> int:
        return self.total - self.used


class QuotaExceeded(Exception):
    pass


class SocialChannel(Protocol):
    key: str

    async def publish(self, post: OutgoingPost) -> PublishResult: ...
    async def quota(self) -> Quota: ...
    async def refresh_credentials(self) -> None: ...
