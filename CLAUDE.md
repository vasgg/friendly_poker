# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Telegram bot for managing friendly poker sessions. Tracks games, players, statistics, debts, and generates reports. Built with Python 3.12+, aiogram 3.15+, SQLAlchemy 2.0+, and Pydantic 2.9+.

## Commands

```bash
# Install dependencies
uv sync

# Initialize database
uv run create-db

# Run the bot
uv run bot-run

# Run tests
uv run pytest

# Run a specific test
uv run pytest src/tests/test_debt.py -k "test_name"
```

## Environment Variables

Required in `.env` file (see `example.env`):
- `BOT_TOKEN` - Telegram bot token
- `BOT_ADMIN` - Admin user ID
- `BOT_GROUP_ID` - Target group ID
- `DB_FILE_NAME` - SQLite database filename

## Architecture

```
src/
├── bot/
│   ├── main.py              # Entry point, dispatcher setup
│   ├── config.py            # Pydantic config (BotConfig, DBConfig)
│   ├── middlewares/         # Auth, session, logging middlewares
│   ├── handlers/            # Message/callback routing (aiogram Router)
│   ├── controllers/         # Business logic (game, user, record, debt)
│   └── internal/            # Shared utilities, enums, keyboards, lexicon
└── database/
    ├── models.py            # ORM models (User, Game, Record, Debt)
    ├── database_connector.py # AsyncEngine & session factory
    └── tables_helper.py     # DB initialization script
```

### Request Flow

1. **Middleware pipeline**: UpdatesDumper → DBSession → Auth → Logging
2. **Router handlers**: Receive Message/CallbackQuery with injected `db_session`, `user`, `state`
3. **Controllers**: Business logic with async database operations
4. **Database**: Async SQLite via SQLAlchemy + aiosqlite

### Key Components

- **Models**: `User` (player stats), `Game` (session tracking), `Record` (buy-in/buy-out), `Debt` (settlements)
- **Context enums** (`internal/context.py`): `GameStatus`, `GameAction`, `SettingsForm` FSM states
- **Debt algorithm** (`controllers/debt.py`): DFS-based `equalizer()` function for minimal transaction calculation
- **UI strings** (`internal/lexicon.py`): All text in Russian, centralized

### Handler Pattern

```python
async def handler(message: Message, user: User, db_session: AsyncSession, state: FSMContext):
    # user and db_session injected via middleware
```

### Database Patterns

- All operations are async using `AsyncSession`
- Session context manager with `.begin()` for transactions
- Full type hints with `Mapped` generics
