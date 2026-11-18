"""Wait until TEST_DATABASE_URL (or DATABASE_URL) accepts connections."""

import asyncio
import os
import sys

import asyncpg


async def main() -> int:
    url = os.environ.get("TEST_DATABASE_URL") or os.environ["DATABASE_URL"]
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    for _ in range(60):
        try:
            conn = await asyncpg.connect(url)
            await conn.close()
            return 0
        except (OSError, asyncpg.PostgresError):
            await asyncio.sleep(1)
    print("database not reachable", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
