import argparse
import asyncio
from pathlib import Path

from pydantic_settings import BaseSettings
from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from bot.internal.config_dicts import assign_config_dict
from database.models import Base, Debt, Game, Record, User

TABLES_ORDER: tuple[type[DeclarativeBase], ...] = (User, Game, Record, Debt)
SEQUENCE_TABLES: tuple[type[DeclarativeBase], ...] = (Game, Record, Debt)


class MigrationDBConfig(BaseSettings):
    URL: str | None = None
    echo: bool = False

    model_config = assign_config_dict(prefix="DB_")


def normalize_postgres_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    return url


def build_sqlite_url(source: str) -> tuple[str, Path]:
    sqlite_path = Path(source).expanduser()
    if sqlite_path.suffix != ".db":
        sqlite_path = sqlite_path.with_suffix(".db")
    sqlite_path = sqlite_path.resolve()

    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite file not found: {sqlite_path}")

    return f"sqlite+aiosqlite:///{sqlite_path}", sqlite_path


async def get_table_counts(session: AsyncSession) -> dict[str, int]:
    counts: dict[str, int] = {}
    for model in TABLES_ORDER:
        count = await session.scalar(select(func.count()).select_from(model))
        counts[model.__tablename__] = int(count or 0)
    return counts


def model_rows_to_dicts(rows: list[DeclarativeBase], model: type[DeclarativeBase]) -> list[dict]:
    return [
        {column.name: getattr(row, column.name) for column in model.__table__.columns}
        for row in rows
    ]


async def ensure_target_empty(session: AsyncSession) -> None:
    counts = await get_table_counts(session)
    non_empty = {table_name: count for table_name, count in counts.items() if count > 0}
    if non_empty:
        details = ", ".join(f"{table_name}={count}" for table_name, count in non_empty.items())
        raise RuntimeError(
            "Target database is not empty. Use --truncate-target to overwrite existing data. "
            f"Current rows: {details}"
        )


async def truncate_target(session: AsyncSession) -> None:
    for model in reversed(TABLES_ORDER):
        await session.execute(delete(model))


async def copy_table(
    source_session: AsyncSession, target_session: AsyncSession, model: type[DeclarativeBase]
) -> int:
    result = await source_session.execute(select(model).order_by(model.id))
    rows = list(result.scalars())
    if not rows:
        return 0

    await target_session.execute(insert(model), model_rows_to_dicts(rows, model))
    return len(rows)


async def reset_sequences(session: AsyncSession) -> None:
    for model in SEQUENCE_TABLES:
        max_id = await session.scalar(select(func.max(model.id)))
        next_value = int(max_id or 0) + 1
        table_name = model.__tablename__
        await session.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), :next_value, false)"
            ),
            {"next_value": next_value},
        )


async def migrate(
    source_url: str,
    target_url: str,
    *,
    truncate_existing: bool,
    echo: bool,
) -> dict[str, int]:
    source_engine = create_async_engine(source_url, echo=False)
    target_engine = create_async_engine(target_url, echo=echo)

    source_session_factory = async_sessionmaker(source_engine, expire_on_commit=False)
    target_session_factory = async_sessionmaker(target_engine, expire_on_commit=False)

    try:
        async with target_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, checkfirst=True)

        copied_counts: dict[str, int] = {}
        async with source_session_factory() as source_session, target_session_factory() as target_session:
            async with target_session.begin():
                if truncate_existing:
                    await truncate_target(target_session)
                await ensure_target_empty(target_session)

                for model in TABLES_ORDER:
                    copied_counts[model.__tablename__] = await copy_table(
                        source_session, target_session, model
                    )

                target_counts = await get_table_counts(target_session)
                if target_counts != copied_counts:
                    raise RuntimeError(
                        "Row count mismatch after migration. "
                        f"Source: {copied_counts}; Target: {target_counts}"
                    )

                await reset_sequences(target_session)

        return copied_counts
    finally:
        await source_engine.dispose()
        await target_engine.dispose()


def parse_args() -> argparse.Namespace:
    db_config = MigrationDBConfig()
    parser = argparse.ArgumentParser(
        description="Copy all data from SQLite .db file to PostgreSQL database."
    )
    parser.add_argument(
        "--source",
        default="poker_bot.db",
        help="Path to source SQLite .db file (default: poker_bot.db).",
    )
    parser.add_argument(
        "--target-url",
        default=db_config.URL,
        help=(
            "Target PostgreSQL URL. If omitted, uses DB_URL from .env "
            "(must be postgresql+asyncpg://...)"
        ),
    )
    parser.add_argument(
        "--echo",
        action="store_true",
        default=db_config.echo,
        help="Enable SQLAlchemy SQL logging output during migration.",
    )
    parser.add_argument(
        "--truncate-target",
        action="store_true",
        help="Delete all rows in target tables before import.",
    )
    return parser.parse_args()


def run_main() -> None:
    args = parse_args()

    source_url, sqlite_path = build_sqlite_url(args.source)
    if not args.target_url:
        raise ValueError("Provide --target-url or set DB_URL in .env")

    target_url = normalize_postgres_url(args.target_url)
    if not target_url.startswith("postgresql+asyncpg://"):
        raise ValueError(
            "Target URL must be PostgreSQL (postgresql+asyncpg://...). "
            "Set DB_URL in .env or pass --target-url explicitly."
        )

    safe_target_url = make_url(target_url).render_as_string(hide_password=True)
    print(f"Source SQLite: {sqlite_path}")
    print(f"Target Postgres: {safe_target_url}")

    copied_counts = asyncio.run(
        migrate(
            source_url=source_url,
            target_url=target_url,
            truncate_existing=args.truncate_target,
            echo=args.echo,
        )
    )

    print("Migration completed:")
    for table_name, count in copied_counts.items():
        print(f"  - {table_name}: {count} rows")


if __name__ == "__main__":
    run_main()
