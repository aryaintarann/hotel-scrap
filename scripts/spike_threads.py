"""S-1 spike: verify a Threads test account. Reads THREADS_USER_ID / THREADS_ACCESS_TOKEN from .env.

    uv run python scripts/spike_threads.py            # profile + quota only (read-only)
    uv run python scripts/spike_threads.py --post     # also publishes ONE TEXT post to the account

Report goes to spike_out/threads.json (gitignored). The token is never printed.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from hotelpilot.core.config import get_settings
from hotelpilot.publishing.channels.base import OutgoingPost
from hotelpilot.publishing.channels.threads import ThreadsChannel


async def main() -> int:
    s = get_settings()
    if not s.threads_enabled:
        print("THREADS_USER_ID / THREADS_ACCESS_TOKEN empty in .env — nothing to test.")
        return 1
    ch = ThreadsChannel(s.threads_user_id, s.threads_access_token.get_secret_value())
    report: dict[str, object] = {"checked_at": datetime.now(UTC).isoformat()}
    report["profile"] = await ch._call("GET", f"{ch.base}/me", {"fields": "id,username"})
    q = await ch.quota()
    report["quota"] = {"used": q.used, "total": q.total}
    if "--post" in sys.argv:
        res = await ch.publish(
            OutgoingPost(
                id="spike", text="HotelPilot spike test post. #AIassisted", topic_tag="HotelPilotTest"
            )
        )
        report["published_id"] = res.external_id
    out = Path("spike_out")
    out.mkdir(exist_ok=True)
    (out / "threads.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
