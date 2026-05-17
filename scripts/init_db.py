"""Initialize LangGraph checkpoint tables in PostgreSQL.

Run once after the database container is up:
    make init-db
    # or directly:
    uv run python scripts/init_db.py
"""

import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

# Load environment variables from .env (local dev) or .env.prod
load_dotenv(Path(__file__).parent.parent / ".env")
load_dotenv(Path(__file__).parent.parent / ".env.prod", override=False)


async def main():
    try:
        import psycopg
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    except ImportError as e:
        print(f"Import error: {e}", file=sys.stderr)
        print("Make sure 'uv sync' has been run.", file=sys.stderr)
        sys.exit(1)

    user = os.getenv("PG_USER", "rag_chatbot")
    password = quote_plus(os.getenv("PG_PASSWORD", ""))
    host = os.getenv("PG_HOST", "127.0.0.1")
    port = os.getenv("PG_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "rag_chatbot_db")
    sslmode = os.getenv("PG_SSLMODE", "disable")

    connstr = f"postgresql://{user}:{password}@{host}:{port}/{db}?sslmode={sslmode}"
    print(f"Connecting to Postgres: {host}:{port}/{db} (user={user})")

    try:
        async with await psycopg.AsyncConnection.connect(connstr, autocommit=True) as conn:
            saver = AsyncPostgresSaver(conn)
            await saver.setup()
            print("✓ LangGraph checkpoint tables created (or already exist).")
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
