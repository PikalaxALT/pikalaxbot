import sqlite3
import asyncio
import concurrent.futures as cf
from .cursor import Cursor
from typing import *
import functools
import logging
from os import PathLike
from .context import contextmanager


__all__ = ('Cursor', 'Connection', 'connect')

LOG = logging.getLogger('asqlite3')
LOG.setLevel(logging.DEBUG)


class Connection:
    def __init__(self, db_path, **kwargs):
        self._db_path = db_path
        self._init_kwargs = kwargs
        self._connection: Optional[sqlite3.Connection] = None
        self._loop = None
        self._executor = cf.ThreadPoolExecutor(max_workers=1)

    @property
    def _conn(self) -> sqlite3.Connection:
        if self._connection is None:
            raise ValueError('No active connection')

        return self._connection

    async def _execute(self, fn: Callable, *args, **kwargs):
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        real_fn = functools.partial(fn, *args, **kwargs)
        return await self._loop.run_in_executor(self._executor, real_fn)

    def _execute_insert(self, sql: str, parameters: Iterable):
        cursor = self._conn.execute(sql, parameters)
        cursor.execute('SELECT last_insert_rowid()')
        return cursor.fetchone()

    def _execute_fetchall(self, sql: str, parameters: Iterable) -> Iterable:
        cursor = self._conn.execute(sql, parameters)
        return cursor.fetchall()

    async def _connect(self) -> 'Connection':
        if self._connection is None:
            try:
                self._connection = await self._execute(sqlite3.connect, self._db_path, **self._init_kwargs)
            except Exception:
                self._connection = None
                raise

        return self

    def __await__(self) -> Generator[Any, None, 'Connection']:
        return self._connect().__await__()

    async def __aenter__(self) -> 'Connection':
        return await self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    @contextmanager
    async def cursor(self, cursorClass: Optional[type] = sqlite3.Cursor) -> Cursor:
        return Cursor(self, await self._execute(self._conn.cursor, cursorClass))

    async def commit(self) -> None:
        await self._execute(self._conn.commit)

    async def rollback(self) -> None:
        await self._execute(self._conn.rollback)

    async def close(self) -> None:
        try:
            await self._execute(self._conn.close)
        except Exception:
            LOG.info('exception occurred while closing the connection')
        finally:
            self._connection = None

    @contextmanager
    async def execute(self, sql: str, parameters: Optional[Iterable] = None) -> Cursor:
        if parameters is None:
            parameters = []
        return Cursor(self, await self._execute(self._conn.execute, sql, parameters))

    @contextmanager
    async def execute_insert(self, sql: str, parameters: Optional[Iterable] = None) -> Optional:
        if parameters is None:
            parameters = []
        return await self._execute(self._execute_insert, sql, parameters)

    @contextmanager
    async def execute_fetchall(self, sql: str, parameters: Optional[Iterable] = None) -> Iterable:
        if parameters is None:
            parameters = []
        return await self._execute(self._execute_fetchall, sql, parameters)

    @contextmanager
    async def executemany(self, sql: str, parameters: Iterable[Iterable] = None) -> Cursor:
        return Cursor(self, await self._execute(self._conn.executemany, sql, parameters))

    @contextmanager
    async def executescript(self, script: str) -> Cursor:
        return Cursor(self, await self._execute(self._conn.executescript, script))

    async def interrupt(self):
        return self._conn.interrupt()

    async def create_function(self, name: str, num_params: int, callback: Callable, *, deterministic=False):
        return await self._execute(self._conn.create_function, name, num_params, callback, deterministic=deterministic)

    async def create_aggregate(self, name: str, num_params: int, aggregate_class: type):
        return await self._execute(self._conn.create_aggregate, name, num_params, aggregate_class)

    async def create_collation(self, name: str, callback: Optional[Callable]):
        return await self._execute(self._conn.create_collation, name, callback)

    @property
    def in_transaction(self):
        return self._conn.in_transaction

    @property
    def isolation_level(self) -> str:
        return self._conn.isolation_level

    @isolation_level.setter
    def isolation_level(self, value: str) -> None:
        self._conn.isolation_level = value

    @property
    def row_factory(self) -> "Optional[Type]":  # py3.5.2 compat (#24)
        return self._conn.row_factory

    @row_factory.setter
    def row_factory(self, factory: "Optional[Type]") -> None:  # py3.5.2 compat (#24)
        self._conn.row_factory = factory

    @property
    def text_factory(self) -> Type:
        return self._conn.text_factory

    @text_factory.setter
    def text_factory(self, factory: Type) -> None:
        self._conn.text_factory = factory

    @property
    def total_changes(self) -> int:
        return self._conn.total_changes

    async def enable_load_extension(self, value: bool) -> None:
        await self._execute(self._conn.enable_load_extension, value)  # type: ignore

    async def load_extension(self, path: str):
        await self._execute(self._conn.load_extension, path)  # type: ignore

    async def set_progress_handler(
        self, handler: Callable[[], Optional[int]], n: int
    ) -> None:
        await self._execute(self._conn.set_progress_handler, handler, n)

    async def set_trace_callback(self, handler: Callable) -> None:
        await self._execute(self._conn.set_trace_callback, handler)

    async def iterdump(self) -> AsyncIterator[str]:
        iterator = self._conn.iterdump()
        while True:
            try:
                line = await self._execute(next, iterator)
            except StopIteration:
                raise StopAsyncIteration
            else:
                yield line

    async def backup(self, target: Union['Connection', sqlite3.Connection], *, pages: int = 0, progress: Optional[Callable[[int, int, int], None]] = None, name: str = 'main', sleep: float = 0.250):
        if isinstance(target, Connection):
            target = target._conn
        await self._execute(self._conn.backup, target, pages=pages, progress=progress, name=name, sleep=sleep)


def connect(database: Union[str, PathLike], **kwargs):
    return Connection(database, **kwargs)
