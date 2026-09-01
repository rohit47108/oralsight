"""Process-local account operation locks that complement database row locks."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass(slots=True)
class _LockEntry:
    lock: asyncio.Lock
    references: int = 0


class UserOperationLocks:
    """Serialize account lifecycle work within one API process.

    PostgreSQL row locks remain the cross-process guarantee. This small registry
    gives the SQLite test runtime the same ordering and avoids starting a second
    account lifecycle transaction while an upload owns the database user row.
    """

    def __init__(self) -> None:
        self._entries: dict[str, _LockEntry] = {}
        self._guard = asyncio.Lock()

    @asynccontextmanager
    async def hold(self, user_id: str) -> AsyncIterator[None]:
        async with self._guard:
            entry = self._entries.get(user_id)
            if entry is None:
                entry = _LockEntry(lock=asyncio.Lock())
                self._entries[user_id] = entry
            entry.references += 1
        await entry.lock.acquire()
        try:
            yield
        finally:
            entry.lock.release()
            async with self._guard:
                entry.references -= 1
                if entry.references == 0:
                    self._entries.pop(user_id, None)
