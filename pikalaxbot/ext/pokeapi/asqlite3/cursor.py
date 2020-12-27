import sqlite3
from typing import *

if TYPE_CHECKING:
    from .core import Connection


class Cursor:
    def __init__(self, connection: 'Connection', cursor: sqlite3.Cursor):
        self._connection = connection
        self._cursor = cursor

    async def _execute(self, fn, *args, **kwargs):
        return await self._connection._execute(fn, *args, **kwargs)

    async def __aiter__(self) -> AsyncIterator:
        while rows := await self.fetchmany():
            for row in rows:
                yield row

    async def execute(self, sql: str, parameters: Optional[Iterable] = None) -> 'Cursor':
        await self._execute(self._cursor.execute, sql, parameters)
        return self

    async def executemany(self, sql: str, parameters: Iterable[Iterable] = None) -> 'Cursor':
        await self._execute(self._cursor.executemany, sql, parameters)
        return self

    async def executescript(self, script: str) -> 'Cursor':
        await self._execute(self._cursor.executescript, script)
        return self

    async def fetchone(self) -> Any:
        return await self._execute(self._cursor.fetchone)

    async def fetchmany(self, size: int = None) -> Iterable[Any]:
        params = (size,) if size else ()
        return await self._execute(self._cursor.fetchmany, *params)

    async def fetchall(self) -> Iterable[Any]:
        return await self._execute(self._cursor.fetchall)

    async def close(self):
        await self._execute(self._cursor.close)

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def lastrowid(self) -> int:
        return self._cursor.lastrowid

    @property
    def arraysize(self) -> int:
        return self._cursor.arraysize

    @arraysize.setter
    def arraysize(self, value: int) -> None:
        self._cursor.arraysize = value

    @property
    def description(self) -> Tuple[Tuple]:
        return self._cursor.description

    @property
    def connection(self) -> sqlite3.Connection:
        return self._cursor.connection

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
