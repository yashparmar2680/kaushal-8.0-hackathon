
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, jsonify, abort
)
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

SIMULATION_INTERVAL = 30
DISPLAY_LIMIT = 30

SIMULATED_CLASSROOMS = [
    "Room 101", "Room 102", "Room 103"
]

simulation_lock = threading.Lock()
simulation_started = False


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# --------------------------------------------------
# DATABASE INITIALIZATION
# --------------------------------------------------

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

        db.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                classroom TEXT NOT NULL,
                resource TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                amount REAL NOT NULL,
                baseline REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'New'
                    CHECK(status IN (
                        'New', 'Acknowledged', 'Resolved'
                    )),
                detected_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                resolved_at TEXT
            )
        """)

        # Extra protection against duplicate open alerts.
        db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            unique_open_alert
            ON alerts(classroom, resource, alert_type)
            WHERE status IN ('New', 'Acknowledged')
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


# --------------------------------------------------
# ALERT RULES
# --------------------------------------------------

def detect_issues(row):
    issues = []

    if row["amount"] > row["baseline"]:
        if row["resource"] == "Electricity":
            severity = (
                "High"
                if row["amount"] > row["baseline"] * 1.25
                else "Medium"
            )
            message = "Electricity consumption above baseline"
        else:
            severity = (
                "High"
                if row["amount"] > row["baseline"] * 1.25
                else "Medium"
            )
            message = "Water consumption above baseline"

        issues.append({
            "type": "Above baseline",
            "severity": severity,
            "message": message
        })

    if (
        row["resource"] == "Electricity"
        and row["occupied"] == 0
        and row["amount"] > 0
    ):
        issues.append({
            "type": "Usage in empty classroom",
            "severity": "High",
            "message": (
                "Check lights, fans, AC and equipment "
                "in the empty classroom"
            )
        })

    return issues


# --------------------------------------------------
# DUPLICATE-PROOF ALERT SYNCHRONIZATION
# --------------------------------------------------

def sync_alerts_for_readings(rows):
    """
    Create an alert if no open alert exists for the same
    classroom, resource and alert type.

    If an open alert already exists, update its latest
    reading instead of inserting another alert.

    Resolved alerts remain in history. A recurrence creates
    a new alert.
    """
    timestamp = now()

    with get_db() as db:
        for row in rows:
            issues = detect_issues(row)

            for issue in issues:
                existing = db.execute("""
                    SELECT id
                    FROM alerts
                    WHERE classroom = ?
                      AND resource = ?
                      AND alert_type = ?
                      AND status IN ('New', 'Acknowledged')
                    ORDER BY id DESC
                    LIMIT 1
                """, (
                    row["classroom"],
                    row["resource"],
                    issue["type"]
                )).fetchone()

                if existing:
                    db.execute("""
                        UPDATE alerts
                        SET severity = ?,
                            message = ?,
                            amount = ?,
                            baseline = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (
                        issue["severity"],
                        issue["message"],
                        row["amount"],
                        row["baseline"],
                        timestamp,
                        existing["id"]
                    ))

                else:
                    db.execute("""
                        INSERT INTO alerts (
                            classroom, resource, alert_type,
                            severity, message, amount, baseline,
                            status, detected_at, updated_at,
                            resolved_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?,
                                'New', ?, ?, NULL)
                    """, (
                        row["classroom"],
                        row["resource"],
                        issue["type"],
                        issue["severity"],
                        issue["message"],
                        row["amount"],
                        row["baseline"],
                        timestamp,
                        timestamp
                    ))


def sync_latest_resource_alerts():
    """Initialize alerts from the latest reading per room/resource."""
    with get_db() as db:
        rows = db.execute("""
            SELECT r.*
            FROM resources r
            INNER JOIN (
                SELECT classroom, resource, MAX(id) AS latest_id
                FROM resources
                GROUP BY classroom, resource
            ) latest ON r.id = latest.latest_id
        """).fetchall()

    sync_alerts_for_readings(rows)


# --------------------------------------------------
# AUTOMATIC SIMULATION
# Updates existing simulated rows
# --------------------------------------------------

def generate_simulated_readings():
    timestamp = now()
    readings = []

    with get_db() as db:
        for classroom in SIMULATED_CLASSROOMS:
            occupied = random.choices(
                [1, 0], weights=[75, 25]
            )[0]

            electricity_baseline = random.choice([10, 12, 15])
            water_baseline = random.choice([300, 400, 500])

            electricity_amount = round(
                electricity_baseline * random.uniform(0.60, 1.40),
                2
            )

            if not occupied:
                electricity_amount = round(
                    electricity_baseline * random.uniform(0.30, 0.80),
                    2
                )

            water_amount = round(
                water_baseline * random.uniform(0.60, 1.40),
                2
            )

            values = [
                ("Electricity", electricity_amount,
                 electricity_baseline),
                ("Water", water_amount, water_baseline)
            ]

            for resource, amount, baseline in values:
                existing = db.execute("""
                    SELECT id
                    FROM resources
                    WHERE classroom = ? AND resource = ?
                    ORDER BY id DESC LIMIT 1
                """, (classroom, resource)).fetchone()

                if existing:
                    db.execute("""
                        UPDATE resources
                        SET amount = ?, baseline = ?,
                            occupied = ?, recorded_at = ?
                        WHERE id = ?
                    """, (
                        amount, baseline, occupied,
                        timestamp, existing["id"]
                    ))
                    record_id = existing["id"]

                else:
                    cursor = db.execute("""
                        INSERT INTO resources (
                            classroom, resource, amount, baseline,
                            occupied, recorded_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        classroom, resource, amount, baseline,
                        occupied, timestamp
                    ))
                    record_id = cursor.lastrowid

                readings.append({
                    "id": record_id,
                    "classroom": classroom,
                    "resource": resource,
                    "amount": amount,
                    "baseline": baseline,
                    "occupied": occupied,
                    "recorded_at": timestamp
                })

    sync_alerts_for_readings(readings)

    print(f"[SIMULATION] Updated readings at {timestamp}")


def simulation_worker():
    while True:
        time.sleep(SIMULATION_INTERVAL)
        try:
            generate_simulated_readings()
        except Exception:
            app.logger.exception("Simulation cycle failed")


def start_simulation():
    global simulation_started

    with simulation_lock:
        if simulation_started:
            return
        simulation_started = True

    threading.Thread(
        target=simulation_worker,
        name="ecocampus-simulator",
        daemon=True
    ).start()


# --------------------------------------------------
# INSIGHTS
# --------------------------------------------------

def get_insights(rows):
    insights = []

    for row in rows:
        if (
            row["resource"] == "Electricity"
            and row["occupied"] == 0
            and row["amount"] > 0
        ):
            insights.append(
                f"{row['classroom']}: check lights, fans "
                "and AC when the classroom is empty."
            )
        elif row["amount"] > row["baseline"]:
            if row["resource"] == "Electricity":
                insights.append(
                    f"{row['classroom']}: inspect lighting, "
                    "AC settings and equipment."
                )
            else:
                insights.append(
                    f"{row['classroom']}: inspect taps, "
                    "flushes and possible leaks."
                )

    return list(dict.fromkeys(insights))[:5]


# --------------------------------------------------
# BUILD DASHBOARD
# --------------------------------------------------

def build_dashboard():
    with get_db() as db:
        all_rows = db.execute("""
            SELECT * FROM resources
        """).fetchall()

        display_rows = db.execute("""
            SELECT * FROM resources
            ORDER BY recorded_at DESC, id DESC
            LIMIT ?
        """, (DISPLAY_LIMIT,)).fetchall()

        alert_rows = db.execute("""
            SELECT * FROM alerts
            ORDER BY
                CASE status
                    WHEN 'New' THEN 0
                    WHEN 'Acknowledged' THEN 1
                    ELSE 2
                END,
                updated_at DESC, id DESC
            LIMIT 100
        """).fetchall()

        open_count = db.execute("""
            SELECT COUNT(*) FROM alerts
            WHERE status IN ('New', 'Acknowledged')
        """).fetchone()[0]

    all_records = [dict(row) for row in all_rows]
    records = [dict(row) for row in display_rows]
    alerts = [dict(row) for row in alert_rows]

    electricity = sum(
        r["amount"] for r in all_records
        if r["resource"] == "Electricity"
    )
    water = sum(
        r["amount"] for r in all_records
        if r["resource"] == "Water"
    )

    electricity_saved = sum(
        r["baseline"] - r["amount"] for r in all_records
        if r["resource"] == "Electricity"
    )
    water_saved = sum(
        r["baseline"] - r["amount"] for r in all_records
        if r["resource"] == "Water"
    )

    classroom_map = {}

    for r in all_records:
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

    # Preserve a compatible list of current alert dictionaries.
    for alert in alerts:
        alert["recorded_at"] = alert["updated_at"]

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
        "total_records": len(all_records),
        "displayed_records": len(records),
        "display_limit": DISPLAY_LIMIT,
        "active_alerts": open_count,
        "last_updated": (
            records[0]["recorded_at"] if records else None
        )
    }


# --------------------------------------------------
# PAGES AND API
# --------------------------------------------------

@app.route("/")
def index():
    return render_template(
        "index.html",
        dashboard=build_dashboard()
    )


@app.route("/api/dashboard")
def dashboard_api():
    response = jsonify(build_dashboard())
    response.headers["Cache-Control"] = "no-store"
    return response


# --------------------------------------------------
# ACKNOWLEDGE OR RESOLVE AN ALERT
# --------------------------------------------------

@app.post("/alerts/<int:alert_id>/acknowledge")
def acknowledge_alert(alert_id):
    with get_db() as db:
        alert = db.execute(
            "SELECT * FROM alerts WHERE id = ?",
            (alert_id,)
        ).fetchone()

        if alert is None:
            abort(404)

        if alert["status"] == "New":
            db.execute("""
                UPDATE alerts
                SET status = 'Acknowledged', updated_at = ?
                WHERE id = ? AND status = 'New'
            """, (now(), alert_id))

    flash("Alert acknowledged.", "success")
    return redirect(url_for("index") + "#alerts")


@app.post("/alerts/<int:alert_id>/resolve")
def resolve_alert(alert_id):
    with get_db() as db:
        alert = db.execute(
            "SELECT * FROM alerts WHERE id = ?",
            (alert_id,)
        ).fetchone()

        if alert is None:
            abort(404)

        if alert["status"] != "Resolved":
            timestamp = now()
            db.execute("""
                UPDATE alerts
                SET status = 'Resolved',
                    updated_at = ?,
                    resolved_at = ?
                WHERE id = ?
            """, (timestamp, timestamp, alert_id))

    flash("Alert marked as resolved.", "success")
    return redirect(url_for("index") + "#alerts")


# --------------------------------------------------
# MANUAL RESOURCE ENTRY
# --------------------------------------------------

@app.route("/add", methods=["POST"])
def add_record():
    classroom = request.form.get("classroom", "").strip()
    resource = request.form.get("resource", "")
    amount_text = request.form.get("amount", "")
    baseline_text = request.form.get("baseline", "")
    occupied_text = request.form.get("occupied", "yes")

    if not classroom or len(classroom) > 80:
        flash("Enter a valid classroom name.", "error")
        return redirect(url_for("index") + "#record")

    if resource not in ("Electricity", "Water"):
        flash("Choose a valid resource.", "error")
        return redirect(url_for("index") + "#record")

    if occupied_text not in ("yes", "no"):
        flash("Choose a valid classroom status.", "error")
        return redirect(url_for("index") + "#record")

    try:
        amount = float(amount_text)
        baseline = float(baseline_text)

        if (
            not 0 <= amount <= 1_000_000
            or not 0 < baseline <= 1_000_000
        ):
            raise ValueError
    except (ValueError, TypeError):
        flash(
            "Enter valid consumption and baseline values.",
            "error"
        )
        return redirect(url_for("index") + "#record")

    occupied = 1 if occupied_text == "yes" else 0
    timestamp = now()

    with get_db() as db:
        cursor = db.execute("""
            INSERT INTO resources (
                classroom, resource, amount, baseline,
                occupied, recorded_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            classroom, resource, amount, baseline,
            occupied, timestamp
        ))

        reading = {
            "id": cursor.lastrowid,
            "classroom": classroom,
            "resource": resource,
            "amount": amount,
            "baseline": baseline,
            "occupied": occupied,
            "recorded_at": timestamp
        }

    sync_alerts_for_readings([reading])

    flash("Resource record added successfully!", "success")
    return redirect(url_for("index") + "#record")


# --------------------------------------------------
# RUN
# --------------------------------------------------

if __name__ == "__main__":
    init_db()
    sync_latest_resource_alerts()
    start_simulation()

    app.run(debug=True, use_reloader=False)
