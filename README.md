# Friendly Poker Bot

Telegram bot for managing friendly poker sessions: track games, debts, and stats with
clean admin workflows and private‑only commands.

## Features
- Start/abort/finish games with buy‑in/buy‑out tracking.
- Automatic debt calculation with private notifications.
- MVP + ROI stats, yearly and all‑time summaries.
- Admin tools: add players, add funds, ratio settings, player deletion with audit/reporting.
- Weekly poll + photo reminders.
- Commands work only in private chat; group chat is for announcements.

## Requirements
- Python 3.12+
- SQLite (`aiosqlite`) or PostgreSQL (`asyncpg`)
- `uv` recommended for dependency management

## Setup
1. Copy `example.env` to `.env`.
2. Fill required variables:
   - `BOT_TOKEN` — bot token from BotFather
   - `BOT_ADMIN` — Telegram user id of the main admin
   - `BOT_ADMIN_IBAN` — payment requisites shown in `/info`
   - `BOT_ADMIN_NAME` — name shown in `/info`
   - `BOT_GROUP_ID` — group chat id
   - `DB_URL` — preferred, full DB URL (for PostgreSQL use `postgresql+asyncpg://user:password@host:5432/dbname`)
   - `DB_FILE_NAME` — SQLite fallback, file name without `.db` (used only when `DB_URL` is empty)
   - `BOT_TIMEZONE` — optional, default `Asia/Tbilisi`

## Run
```bash
uv sync
uv run bot-run
```

## SQLite -> PostgreSQL migration
1. Create backup of SQLite file:
```bash
cp poker_bot.db poker_bot.db.backup
```

2. Set PostgreSQL URL in `.env`:
```bash
DB_URL=postgresql+asyncpg://user:password@host:5432/dbname
```

3. Run migration:
```bash
uv run migrate-sqlite-to-postgres --source poker_bot.db
```

If target tables already contain data and you intentionally want to overwrite them:
```bash
uv run migrate-sqlite-to-postgres --source poker_bot.db --truncate-target
```

## Commands
- `/start` — greeting
- `/settings` — payment requisites
- `/stats` — personal stats + debts
- `/admin` — admin panel (admins only)
- `/info` — bot info + support details

## Development
```bash
uv run ruff check src
uv run ty check src
uv run pytest
```
