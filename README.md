# Badge Manager

Web app to manage attendees in SQLite and generate conference badge PNGs from SVG templates.

## Features

- Password-only login (no username)
- Add, edit, delete attendees
- Paste/import CSV rows
- Generate one badge (`.png`) per attendee
- Export all badges as a `.zip`
- `|` in Name/Company/Position forces line break
- Supports deployment under a subpath via `BASE_PATH`
- Docker Compose ready

## Required SVG templates

Keep these files in the project root:

- `cracha.svg`
- `cracha_big_many.svg`
- `cracha_big_many_position.svg`
- `cracha_big_company.svg`

## Local run with Poetry

1. Install dependencies:

```bash
poetry install
```

2. Configure environment:

```bash
cp .env.example .env
# edit ADMIN_PASSWORD and SECRET_KEY
```

3. Start app:

```bash
poetry run flask --app app run --host 0.0.0.0 --port 8000 --debug
```

Open `http://localhost:8000`.

## Run with Docker Compose

1. Configure env file:

```bash
cp .env.example .env
# edit ADMIN_PASSWORD and SECRET_KEY
```

2. Build and run:

```bash
docker compose up --build
```

Open `http://localhost:8000`.

## Subpath deployment

Set in `.env`:

```env
BASE_PATH=/badges
```

Then app will be served under `/badges`.
