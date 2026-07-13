import csv
import io
import os
import sqlite3
import subprocess
import tempfile
import zipfile
from functools import wraps
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, send_file, session, url_for


BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "data"
DB_PATH = DB_DIR / "app.db"
TEMPLATES_DIR = BASE_DIR

DEFAULT_TEMPLATE = "cracha.svg"
BIG_NAME_TEMPLATE = "cracha_big_many.svg"
BIG_COMPANY_TEMPLATE = "cracha_big_company.svg"
BIG_POSITION_TEMPLATE = "cracha_big_many_position.svg"

NAME_LENGTH_THRESHOLD = 18
OTHER_LENGTH_THRESHOLD = 23


def normalize_base_path(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return ""
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    return cleaned.rstrip("/")


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
    app.config["ADMIN_PASSWORD"] = os.getenv("ADMIN_PASSWORD", "change-me")
    app.config["APPLICATION_ROOT"] = normalize_base_path(os.getenv("BASE_PATH", ""))

    DB_DIR.mkdir(exist_ok=True)
    init_db()

    @app.context_processor
    def inject_base_path():
        return {"base_path": app.config["APPLICATION_ROOT"]}

    @app.before_request
    def enforce_base_path():
        base_path = app.config["APPLICATION_ROOT"]
        if not base_path:
            return None
        path = request.path
        if path == base_path:
            return redirect(f"{base_path}/")
        if path.startswith(base_path + "/"):
            request.environ["SCRIPT_NAME"] = base_path
            request.environ["PATH_INFO"] = path[len(base_path) :] or "/"
            return None
        return redirect(f"{base_path}/")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            password = request.form.get("password", "")
            if password == app.config["ADMIN_PASSWORD"]:
                session["logged_in"] = True
                return redirect(url_for("index"))
            flash("Invalid password.", "error")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    def login_required(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not session.get("logged_in"):
                return redirect(url_for("login"))
            return func(*args, **kwargs)

        return wrapper

    @app.route("/")
    @login_required
    def index():
        attendees = list_attendees()
        return render_template("index.html", attendees=attendees)

    @app.route("/attendees", methods=["POST"])
    @login_required
    def create_attendee():
        name = request.form.get("name", "").strip()
        company = request.form.get("company", "").strip()
        position = request.form.get("position", "").strip()

        if not name or not company:
            flash("Name and company are required.", "error")
            return redirect(url_for("index"))

        with get_db() as conn:
            conn.execute(
                "INSERT INTO attendees(name, company, position) VALUES(?, ?, ?)",
                (name, company, position),
            )
        flash("Attendee created.", "success")
        return redirect(url_for("index"))

    @app.route("/attendees/<int:attendee_id>/update", methods=["POST"])
    @login_required
    def update_attendee(attendee_id: int):
        name = request.form.get("name", "").strip()
        company = request.form.get("company", "").strip()
        position = request.form.get("position", "").strip()

        if not name or not company:
            flash("Name and company are required.", "error")
            return redirect(url_for("index"))

        with get_db() as conn:
            conn.execute(
                "UPDATE attendees SET name = ?, company = ?, position = ? WHERE id = ?",
                (name, company, position, attendee_id),
            )
        flash("Attendee updated.", "success")
        return redirect(url_for("index"))

    @app.route("/attendees/<int:attendee_id>/delete", methods=["POST"])
    @login_required
    def delete_attendee(attendee_id: int):
        with get_db() as conn:
            conn.execute("DELETE FROM attendees WHERE id = ?", (attendee_id,))
        flash("Attendee deleted.", "success")
        return redirect(url_for("index"))

    @app.route("/attendees/import", methods=["POST"])
    @login_required
    def import_attendees():
        raw = request.form.get("csv_data", "").strip()
        uploaded = request.files.get("csv_file")

        if uploaded and uploaded.filename:
            raw = uploaded.read().decode("utf-8", errors="ignore")

        if not raw:
            flash("Provide CSV text or upload a CSV file.", "error")
            return redirect(url_for("index"))

        inserted = 0
        reader = csv.reader(io.StringIO(raw))
        with get_db() as conn:
            for row in reader:
                row = [item.strip() for item in row]
                if not row:
                    continue
                if len(row) < 2:
                    continue

                if row[0].lower() == "name" and row[1].lower() == "company":
                    continue

                name = row[0]
                company = row[1]
                position = row[2] if len(row) > 2 else ""
                if not name or not company:
                    continue
                conn.execute(
                    "INSERT INTO attendees(name, company, position) VALUES(?, ?, ?)",
                    (name, company, position),
                )
                inserted += 1

        flash(f"Imported {inserted} attendees.", "success")
        return redirect(url_for("index"))

    @app.route("/badges/<int:attendee_id>.png")
    @login_required
    def badge_png(attendee_id: int):
        attendee = get_attendee(attendee_id)
        if attendee is None:
            flash("Attendee not found.", "error")
            return redirect(url_for("index"))

        image = generate_badge_png(attendee)
        safe_name = sanitize_filename(attendee["name"])
        return send_file(
            io.BytesIO(image),
            mimetype="image/png",
            as_attachment=True,
            download_name=f"{attendee_id}_{safe_name}.png",
        )

    @app.route("/badges/empty.png")
    @login_required
    def empty_badge_png():
        attendee = {"id": "", "name": "", "company": "", "position": ""}
        image = generate_badge_png(attendee)
        return send_file(
            io.BytesIO(image),
            mimetype="image/png",
            as_attachment=True,
            download_name="empty_badge.png",
        )

    @app.route("/badges/all.zip")
    @login_required
    def all_badges_zip():
        attendees = list_attendees()
        if not attendees:
            flash("No attendees to export.", "error")
            return redirect(url_for("index"))

        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as archive:
            for attendee in attendees:
                image = generate_badge_png(attendee)
                safe_name = sanitize_filename(attendee["name"])
                archive.writestr(f"{attendee['id']}_{safe_name}.png", image)

        memory_file.seek(0)
        return send_file(
            memory_file,
            mimetype="application/zip",
            as_attachment=True,
            download_name="badges.zip",
        )

    return app


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS attendees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                company TEXT NOT NULL,
                position TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def list_attendees() -> list[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(
            "SELECT id, name, company, position FROM attendees ORDER BY id"
        ).fetchall()


def get_attendee(attendee_id: int) -> sqlite3.Row | None:
    with get_db() as conn:
        return conn.execute(
            "SELECT id, name, company, position FROM attendees WHERE id = ?",
            (attendee_id,),
        ).fetchone()


def sanitize_filename(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in text).strip("_") or "badge"


def replace_placeholders(svg_content: str, replacements: dict[str, str]) -> str:
    for key, value in replacements.items():
        svg_content = svg_content.replace(key, value)
    return svg_content


def split_text(text: str, threshold: int) -> tuple[str, str, bool]:
    value = (text or "").strip()
    if not value:
        return "", "", False

    if "|" in value:
        part1, part2 = value.split("|", 1)
        return part1.strip(), part2.strip(), True

    if len(value) <= threshold:
        return value, "", False

    parts = value.split()
    if len(parts) <= 1:
        return value, "", False

    midpoint = len(parts) // 2
    return " ".join(parts[:midpoint]), " ".join(parts[midpoint:]), True


def choose_template(name_split: bool, company_split: bool, position_split: bool) -> str:
    if company_split:
        return BIG_COMPANY_TEMPLATE
    if position_split:
        return BIG_POSITION_TEMPLATE
    if name_split:
        return BIG_NAME_TEMPLATE
    return DEFAULT_TEMPLATE


def build_replacements(attendee: sqlite3.Row | dict) -> dict[str, str]:
    number = str(attendee["id"])
    name = attendee["name"]
    company = attendee["company"]
    position = attendee["position"]

    name1, name2, name_split = split_text(name, NAME_LENGTH_THRESHOLD)
    company1, company2, company_split = split_text(company, OTHER_LENGTH_THRESHOLD)
    position1, position2, position_split = split_text(position, OTHER_LENGTH_THRESHOLD)

    template = choose_template(name_split, company_split, position_split)

    if template == BIG_COMPANY_TEMPLATE:
        return {
            "TEMPLATE_FILE": template,
            "NUMBER": number,
            "NAME": name,
            "POSITION": position,
            "COMPANY1": company1,
            "COMPANY2": company2,
        }

    if template == BIG_POSITION_TEMPLATE:
        return {
            "TEMPLATE_FILE": template,
            "NUMBER": number,
            "NAME": name,
            "POSITION1": position1,
            "POSITION2": position2,
            "COMPANY": company,
        }

    if template == BIG_NAME_TEMPLATE:
        return {
            "TEMPLATE_FILE": template,
            "NUMBER": number,
            "NAME1": name1,
            "NAME2": name2,
            "POSITION": position,
            "COMPANY": company,
        }

    return {
        "TEMPLATE_FILE": template,
        "NUMBER": number,
        "NAME": name,
        "POSITION": position,
        "COMPANY": company,
    }


def generate_badge_png(attendee: sqlite3.Row | dict) -> bytes:
    replacements = build_replacements(attendee)
    template_file = replacements.pop("TEMPLATE_FILE")
    template_path = TEMPLATES_DIR / template_file

    if not template_path.exists():
        raise FileNotFoundError(f"Missing template file: {template_file}")

    svg_content = template_path.read_text(encoding="utf-8")
    filled_svg = replace_placeholders(svg_content, replacements)

    with tempfile.TemporaryDirectory() as tmp:
        svg_path = Path(tmp) / "badge.svg"
        png_path = Path(tmp) / "badge.png"
        svg_path.write_text(filled_svg, encoding="utf-8")
        subprocess.run(
            ["inkscape", str(svg_path), "--export-type=png", "--export-filename", str(png_path)],
            check=True,
            capture_output=True,
            timeout=120,
        )
        return png_path.read_bytes()


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
