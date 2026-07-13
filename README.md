# The Badge Badger

Web app to manage attendees in SQLite and generate conference badge PNGs from SVG templates.

## Features

- Password-only login (no username)
- Add, edit, delete attendees
- Paste/import CSV rows as `name,position,company`
- Generate one badge (`.png`) per attendee
- Download an empty badge (no name, company, or position)
- Download the badge back side (`cracha-back.svg`)
- Export all badges as a `.zip`
- `|` in Name/Company/Position forces a line break at that spot; an explicit
  `|` always beats an automatic length-based split when they compete
- Supports deployment under a subpath via `BASE_PATH`
- Docker Compose ready

## Required SVG templates

Keep these files in the project root:

- `cracha.svg`
- `cracha_big_many.svg`
- `cracha_big_many_position.svg`
- `cracha_big_company.svg`
- `cracha_big_name_company.svg` (two-line name + two-line company)
- `cracha_big_name_position.svg` (two-line name + two-line position)

## Local run with Poetry

Badge PNGs are rendered with [Inkscape](https://inkscape.org), so the `inkscape`
command must be available (the Docker image installs it automatically). The badge
fonts (Keania One, Alumni Sans SC, Major Mono Display) must also be installed.

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
# optionally set EXTERNAL_PORT (host port, defaults to 8000)
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
