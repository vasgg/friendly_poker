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
- PostgreSQL (`asyncpg`)
- Alembic (schema migrations)
- `uv` recommended for dependency management

## Setup
1. Copy `example.env` to `.env`.
2. Fill required variables:
   - `BOT_TOKEN` — bot token from BotFather
   - `BOT_ADMIN` — Telegram user id of the main admin
   - `BOT_ADMIN_IBAN` — payment requisites shown in `/info`
   - `BOT_ADMIN_NAME` — name shown in `/info`
   - `BOT_GROUP_ID` — group chat id
   - `DB_URL` — full PostgreSQL URL (`postgresql+asyncpg://user:password@host:5432/dbname`)
   - `BOT_TIMEZONE` — optional, default `Asia/Tbilisi`

## Run
```bash
uv sync --group dev
uv run alembic upgrade head
uv run bot-run
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
# Set TEST_DB_URL to a dedicated PostgreSQL database before running tests
uv run pytest
```

## Existing Database Upgrade
If your PostgreSQL database already exists from pre-Alembic versions:
```bash
uv run alembic stamp 20260222_0001
uv run alembic upgrade head
```
