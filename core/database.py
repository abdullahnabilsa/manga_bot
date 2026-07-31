# File: core/database.py
from __future__ import annotations

import aiosqlite
import asyncio
import logging

logger = logging.getLogger(__name__)

class Database:
    """Asynchronous SQLite database wrapper with Persistent Connection and WAL mode."""
    
    def __init__(self, db_path: str = "manga_bot.db"):
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None
        self._write_lock = asyncio.Lock()  # قفل عمليات الكتابة فقط لمنع التضارب

    async def connect(self) -> None:
        """Establish a persistent database connection and optimize settings."""
        self._conn = await aiosqlite.connect(self.db_path)
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute("PRAGMA synchronous=NORMAL;")
        await self.init_db()
        logger.info("Database connected successfully with WAL mode.")

    async def close(self) -> None:
        """Close the persistent database connection."""
        if self._conn:
            await self._conn.close()
            logger.info("Database connection closed.")

    async def init_db(self) -> None:
        """Initialize all required tables."""
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS users_access (
                user_id INTEGER PRIMARY KEY,
                role TEXT NOT NULL
            )
        """)
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                user_id INTEGER PRIMARY KEY,
                persona TEXT,
                mode TEXT,
                output_method TEXT,
                file_format TEXT
            )
        """)
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key_value TEXT PRIMARY KEY,
                user_id INTEGER
            )
        """)
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        # NEW: Concurrency Access Control Table
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS concurrency_access (
                user_id INTEGER PRIMARY KEY,
                access_type TEXT NOT NULL,
                expires_at REAL
            )
        """)
        await self._conn.commit()

    async def execute(self, query: str, params: tuple = ()) -> None:
        # قفل الكتابة لضمان سلامة البيانات (Thread Safety)
        async with self._write_lock:
            await self._conn.execute(query, params)
            await self._conn.commit()

    async def fetchone(self, query: str, params: tuple = ()):
        # لا حاجة للقفل في القراءة، وضع WAL يسمح بقراءات متزامنة لا نهائية
        async with self._conn.execute(query, params) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, query: str, params: tuple = ()):
        async with self._conn.execute(query, params) as cursor:
            return await cursor.fetchall()