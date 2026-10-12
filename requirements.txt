
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
app.secret_key = "change-this-before-deployment"

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "ecocampus.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                classroom TEXT NOT NULL,
                resource TEXT NOT NULL,
                amount REAL NOT NULL,
                baseline REAL NOT NULL,
                occupied INTEGER NOT NULL DEFAULT 1,
                recorded_at TEXT NOT NULL
            )
        """)

        count = db.execute(
            "SELECT COUNT(*) FROM resources"
        ).fetchone()[0]

        # Demonstration data for the first launch
        if count == 0:
            samples = [
                ("Room 101", "Electricity", 18, 12, 1,
                 "2026-10-10 09:00"),
                ("Room 102", "Electricity", 8, 12, 1,
                 "2026-10-10 10:00"),
                ("Room 103", "Electricity", 15, 10, 0,
                 "2026-10-10 11:00"),
                ("Room 101", "Water", 420, 500, 1,
                 "2026-10-10 12:00"),
                ("Room 102", "Water", 750, 500, 1,
                 "2026-10-11 10:00"),
                ("Room 103", "Water", 350, 500, 1,
                 "2026-10-11 12:00"),
                ("Room 101", "Electricity", 10, 12, 1,
                 "2026-10-12 09:00"),
            ]

            db.executemany("""
                INSERT INTO resources
                (classroom, resource, amount, baseline,
                 occupied, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, samples)


def analyze(row):
    alerts = []

    if row["amount"] > row["baseline"]:
        alerts.append("Above baseline")

    if (row["resource"] == "Electricity"
            and row["occupied"] == 0
            and row["amount"] > 0):
        alerts.append("Usage in empty classroom")

    return alerts


def get_insights(rows):
    insights = []

    for row in rows:
        if row["resource"] == "Electricity" and row["occupied"] == 0:
            insights.append(
                f"{row['classroom']}: verify lights, fans and AC "
                "when the classroom is empty."
            )
        elif row["amount"] > row["baseline"]:
            if row["resource"] == "Electricity":
                insights.append(
                    f"{row['classroom']}: inspect lighting, AC "
                    "settings and equipment."
                )
            else:
                insights.append(
                    f"{row['classroom']}: inspect taps, flushes "
                    "and possible leaks."
                )

    return list(dict.fromkeys(insights))[:5]


@app.route("/")
def index():
    with get_db() as db:
        rows = db.execute("""
            SELECT * FROM resources
            ORDER BY recorded_at DESC, id DESC
        """).fetchall()

    records = []
    alerts = []

    for row in rows:
        item = dict(row)
        item["alerts"] = analyze(item)
        records.append(item)

        for message in item["alerts"]:
            alerts.append({
                "classroom": item["classroom"],
                "resource": item["resource"],
                "message": message,
                "amount": item["amount"],
                "recorded_at": item["recorded_at"]
            })

    electricity = sum(
        r["amount"] for r in records
        if r["resource"] == "Electricity"
    )
    water = sum(
        r["amount"] for r in records
        if r["resource"] == "Water"
    )

    # Estimated savings versus recorded baselines.
    # Negative savings means consumption exceeded baseline.
    saved = sum(
        r["baseline"] - r["amount"] for r in records
    )

    electricity_saved = sum(
        r["baseline"] - r["amount"] for r in records
        if r["resource"] == "Electricity"
    )
    water_saved = sum(
        r["baseline"] - r["amount"] for r in records
        if r["resource"] == "Water"
    )

    # Group records by classroom for comparisons
    classroom_totals = {}
    for r in records:
        name = r["classroom"]
        if name not in classroom_totals:
            classroom_totals[name] = {
                "classroom": name,
                "electricity": 0,
                "water": 0
            }

        key = (
            "electricity"
            if r["resource"] == "Electricity"
            else "water"
        )
        classroom_totals[name][key] += r["amount"]

    insights = get_insights(records)

    return render_template(
        "index.html",
        records=records,
        alerts=alerts,
        electricity=electricity,
        water=water,
        saved=saved,
        electricity_saved=electricity_saved,
        water_saved=water_saved,
        classrooms=list(classroom_totals.values()),
        insights=insights
    )


@app.route("/add", methods=["POST"])
def add_record():
    classroom = request.form.get("classroom", "").strip()
    resource = request.form.get("resource", "")
    amount_text = request.form.get("amount", "")
    baseline_text = request.form.get("baseline", "")
    occupied_text = request.form.get("occupied", "yes")

    if not classroom or len(classroom) > 80:
        flash("Enter a valid classroom name.", "error")
        return redirect(url_for("index"))

    if resource not in ("Electricity", "Water"):
        flash("Choose a valid resource.", "error")
        return redirect(url_for("index"))

    try:
        amount = float(amount_text)
        baseline = float(baseline_text)

        if (not 0 <= amount <= 1_000_000
                or not 0 < baseline <= 1_000_000):
            raise ValueError

    except (ValueError, TypeError):
        flash("Enter valid positive consumption and baseline values.", "error")
        return redirect(url_for("index"))

    occupied = 1 if occupied_text == "yes" else 0

    with get_db() as db:
        db.execute("""
            INSERT INTO resources
            (classroom, resource, amount, baseline,
             occupied, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            classroom,
            resource,
            amount,
            baseline,
            occupied,
            datetime.now().strftime("%Y-%m-%d %H:%M")
        ))

    flash("Resource record added successfully!", "success")
    return redirect(url_for("index"))


@app.route("/api/analytics")
def analytics():
    with get_db() as db:
        rows = db.execute("""
            SELECT recorded_at, resource, SUM(amount) AS total
            FROM resources
            GROUP BY recorded_at, resource
            ORDER BY recorded_at
        """).fetchall()

    return jsonify([dict(row) for row in rows])


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
