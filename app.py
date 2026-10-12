
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
import random
import threading
import time
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
app.secret_key = "change-this-before-deployment"

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "ecocampus.db"

SIMULATION_INTERVAL = 30  # seconds
SIMULATED_CLASSROOMS = ["Room 101", "Room 102", "Room 103"]

# Protect against accidentally starting two generator threads.
simulation_lock = threading.Lock()
simulation_started = False


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
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


def generate_simulated_readings():
    """Generate one electricity and one water reading per classroom."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    readings = []

    for classroom in SIMULATED_CLASSROOMS:
        # Same simulated occupancy for both readings in a cycle.
        occupied = random.choices([1, 0], weights=[75, 25])[0]

        # Illustrative consumption baselines, not campus measurements.
        electricity_baseline = random.choice([10, 12, 15])
        water_baseline = random.choice([300, 400, 500])

        # Occasionally create an above-baseline reading for the demo.
        if random.random() < 0.25:
            electricity_amount = round(
                electricity_baseline * random.uniform(1.10, 1.45), 2
            )
        else:
            electricity_amount = round(
                electricity_baseline * random.uniform(0.60, 0.98), 2
            )

        # Nonzero electricity in an empty classroom triggers a demo alert.
        if not occupied:
            electricity_amount = round(
                electricity_baseline * random.uniform(0.30, 0.80), 2
            )

        if random.random() < 0.25:
            water_amount = round(
                water_baseline * random.uniform(1.10, 1.40), 2
            )
        else:
            water_amount = round(
                water_baseline * random.uniform(0.60, 0.98), 2
            )

        readings.extend([
            (
                classroom, "Electricity", electricity_amount,
                electricity_baseline, occupied, timestamp
            ),
            (
                classroom, "Water", water_amount,
                water_baseline, occupied, timestamp
            )
        ])

    with get_db() as db:
        db.executemany("""
            INSERT INTO resources
            (classroom, resource, amount, baseline,
             occupied, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, readings)

    print(
        f"[DEMO SIMULATION] Added {len(readings)} readings at {timestamp}"
    )


def simulation_worker():
    """Keep generating demo readings while this Flask process runs."""
    while True:
        time.sleep(SIMULATION_INTERVAL)

        try:
            generate_simulated_readings()
        except Exception as exc:
            # Keep the worker alive if one cycle encounters an error.
            app.logger.exception("Simulation cycle failed: %s", exc)


def start_simulation():
    global simulation_started

    with simulation_lock:
        if simulation_started:
            return

        simulation_started = True

    # Start after the initial page can load; first cycle is after 30 seconds.
    worker = threading.Thread(
        target=simulation_worker,
        name="ecocampus-demo-simulator",
        daemon=True
    )
    worker.start()
    app.logger.info(
        "Demo simulator started; interval=%s seconds",
        SIMULATION_INTERVAL
    )


def analyze(row):
    alerts = []

    if row["amount"] > row["baseline"]:
        alerts.append("Above baseline")

    if (
        row["resource"] == "Electricity"
        and row["occupied"] == 0
        and row["amount"] > 0
    ):
        alerts.append("Usage in empty classroom")

    return alerts


def get_insights(rows):
    insights = []

    for row in rows:
        if (
            row["resource"] == "Electricity"
            and row["occupied"] == 0
            and row["amount"] > 0
        ):
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


def build_dashboard():
    with get_db() as db:
        rows = db.execute("""
            SELECT * FROM resources
            ORDER BY recorded_at DESC, id DESC
        """).fetchall()

    records = []

    for row in rows:
        item = dict(row)
        item["alerts"] = analyze(item)
        records.append(item)

    electricity = sum(
        r["amount"] for r in records
        if r["resource"] == "Electricity"
    )
    water = sum(
        r["amount"] for r in records
        if r["resource"] == "Water"
    )

    electricity_saved = sum(
        r["baseline"] - r["amount"] for r in records
        if r["resource"] == "Electricity"
    )
    water_saved = sum(
        r["baseline"] - r["amount"] for r in records
        if r["resource"] == "Water"
    )

    classroom_map = {}

    for r in records:
        name = r["classroom"]

        if name not in classroom_map:
            classroom_map[name] = {
                "classroom": name,
                "electricity": 0,
                "water": 0
            }

        key = (
            "electricity"
            if r["resource"] == "Electricity"
            else "water"
        )
        classroom_map[name][key] += r["amount"]

    alerts = []

    for r in records:
        for message in r["alerts"]:
            alerts.append({
                "classroom": r["classroom"],
                "resource": r["resource"],
                "message": message,
                "amount": r["amount"],
                "recorded_at": r["recorded_at"]
            })

    return {
        "records": records,
        "alerts": alerts,
        "electricity": electricity,
        "water": water,
        "electricity_saved": electricity_saved,
        "water_saved": water_saved,
        "saved": electricity_saved + water_saved,
        "classrooms": list(classroom_map.values()),
        "insights": get_insights(records),
        "simulated": True,
        "interval_seconds": SIMULATION_INTERVAL,
        "last_updated": (
            records[0]["recorded_at"] if records else None
        )
    }


@app.route("/")
def index():
    return render_template("index.html", dashboard=build_dashboard())


@app.route("/api/dashboard")
def dashboard_api():
    response = jsonify(build_dashboard())
    response.headers["Cache-Control"] = "no-store"
    return response


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

    if occupied_text not in ("yes", "no"):
        flash("Choose a valid classroom status.", "error")
        return redirect(url_for("index"))

    try:
        amount = float(amount_text)
        baseline = float(baseline_text)

        if (
            not 0 <= amount <= 1_000_000
            or not 0 < baseline <= 1_000_000
        ):
            raise ValueError

    except (ValueError, TypeError):
        flash("Enter valid consumption and baseline values.", "error")
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
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

    flash("Resource record added successfully!", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    start_simulation()

    # Disable the reloader so it doesn't create duplicate worker threads.
    app.run(debug=True, use_reloader=False)
