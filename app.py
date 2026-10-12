
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, jsonify, abort
)
import sqlite3
import random
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta, date

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


# --------------------------------------------------
# TIME AND DATABASE HELPERS
# --------------------------------------------------

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

        # Current dashboard readings and manual entries.
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

        # Alert history.
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

        # Historical readings for reports and graphs.
        # Each simulation cycle adds a new snapshot here.
        db.execute("""
            CREATE TABLE IF NOT EXISTS resource_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                classroom TEXT NOT NULL,
                resource TEXT NOT NULL,
                amount REAL NOT NULL,
                baseline REAL NOT NULL,
                occupied INTEGER NOT NULL DEFAULT 1,
                recorded_at TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'simulation'
            )
        """)

        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_time
            ON resource_history(recorded_at)
        """)

        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_resource_time
            ON resource_history(resource, recorded_at)
        """)

        # Prevent duplicate open alerts for the same issue.
        db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS unique_open_alert
            ON alerts(classroom, resource, alert_type)
            WHERE status IN ('New', 'Acknowledged')
        """)

        # Add demonstration records only if resources is empty.
        count = db.execute(
            "SELECT COUNT(*) FROM resources"
        ).fetchone()[0]

        if count == 0:
            samples = [
                ("Room 101", "Electricity", 18, 12, 1,
                 "2026-10-10 09:00:00"),
                ("Room 102", "Electricity", 8, 12, 1,
                 "2026-10-10 10:00:00"),
                ("Room 103", "Electricity", 15, 10, 0,
                 "2026-10-10 11:00:00"),
                ("Room 101", "Water", 420, 500, 1,
                 "2026-10-10 12:00:00"),
                ("Room 102", "Water", 750, 500, 1,
                 "2026-10-11 10:00:00"),
                ("Room 103", "Water", 350, 500, 1,
                 "2026-10-11 12:00:00"),
                ("Room 101", "Electricity", 10, 12, 1,
                 "2026-10-12 09:00:00"),
            ]

            db.executemany("""
                INSERT INTO resources (
                    classroom, resource, amount, baseline,
                    occupied, recorded_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, samples)

        # One-time migration of existing records into history.
        # This does not delete or alter existing records.
        history_count = db.execute(
            "SELECT COUNT(*) FROM resource_history"
        ).fetchone()[0]

        if history_count == 0:
            existing_rows = db.execute("""
                SELECT classroom, resource, amount, baseline,
                       occupied, recorded_at
                FROM resources
            """).fetchall()

            for row in existing_rows:
                db.execute("""
                    INSERT INTO resource_history (
                        classroom, resource, amount, baseline,
                        occupied, recorded_at, source
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 'existing')
                """, (
                    row["classroom"],
                    row["resource"],
                    row["amount"],
                    row["baseline"],
                    row["occupied"],
                    row["recorded_at"]
                ))


# --------------------------------------------------
# ALERT RULES
# --------------------------------------------------

def detect_issues(row):
    issues = []

    if row["amount"] > row["baseline"]:
        severity = (
            "High"
            if row["amount"] > row["baseline"] * 1.25
            else "Medium"
        )

        if row["resource"] == "Electricity":
            message = "Electricity consumption above baseline"
        else:
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
# ALERT SYNCHRONIZATION
# --------------------------------------------------

def sync_alerts_for_readings(rows):
    timestamp = now()

    with get_db() as db:
        for row in rows:
            for issue in detect_issues(row):

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

                # Keep the latest reading in resources for the dashboard.
                existing = db.execute("""
                    SELECT id
                    FROM resources
                    WHERE classroom = ? AND resource = ?
                    ORDER BY id DESC
                    LIMIT 1
                """, (classroom, resource)).fetchone()

                if existing:
                    db.execute("""
                        UPDATE resources
                        SET amount = ?,
                            baseline = ?,
                            occupied = ?,
                            recorded_at = ?
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

                # Always append a separate historical snapshot.
                db.execute("""
                    INSERT INTO resource_history (
                        classroom, resource, amount, baseline,
                        occupied, recorded_at, source
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 'simulation')
                """, (
                    classroom, resource, amount, baseline,
                    occupied, timestamp
                ))

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

    print(f"[SIMULATION] Saved historical snapshots at {timestamp}")


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
# EXISTING SUSTAINABILITY INSIGHTS
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
# BUILD EXISTING DASHBOARD
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
# REPORTING HELPERS
# --------------------------------------------------

REPORT_PERIODS = {
    "1d": {
        "days": 1,
        "intervals": ["hourly"]
    },
    "7d": {
        "days": 7,
        "intervals": ["hourly", "daily"]
    },
    "30d": {
        "days": 30,
        "intervals": ["hourly", "daily", "weekly"]
    }
}


def parse_timestamp(value):
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def get_bucket(timestamp, interval):
    if interval == "hourly":
        bucket = timestamp.replace(
            minute=0, second=0, microsecond=0
        )
        label = bucket.strftime("%d %b %H:%M")

    elif interval == "daily":
        bucket = timestamp.date()
        label = bucket.strftime("%d %b %Y")

    else:
        # ISO weeks begin on Monday.
        bucket = (
            timestamp.date()
            - timedelta(days=timestamp.weekday())
        )
        label = f"Week of {bucket.strftime('%d %b %Y')}"

    return bucket, label


def aggregate_report_rows(rows, interval):
    """
    Aggregate readings as averages and peaks.

    The simulator records snapshots, not consumption per interval.
    Therefore, summing every snapshot would exaggerate consumption.
    """
    groups = {}

    for row in rows:
        timestamp = parse_timestamp(row["recorded_at"])

        if timestamp is None:
            continue

        bucket, label = get_bucket(timestamp, interval)
        key = (row["resource"], bucket)

        if key not in groups:
            groups[key] = {
                "label": label,
                "resource": row["resource"],
                "amounts": [],
                "baselines": [],
                "above_baseline": 0,
                "empty_electricity": 0
            }

        group = groups[key]

        amount = float(row["amount"])
        baseline = float(row["baseline"])

        group["amounts"].append(amount)
        group["baselines"].append(baseline)

        if amount > baseline:
            group["above_baseline"] += 1

        if (
            row["resource"] == "Electricity"
            and int(row["occupied"]) == 0
            and amount > 0
        ):
            group["empty_electricity"] += 1

    result = {
        "Electricity": [],
        "Water": []
    }

    for (resource, bucket), group in sorted(
        groups.items(),
        key=lambda item: item[0][1]
    ):
        amounts = group["amounts"]
        baselines = group["baselines"]

        result[resource].append({
            "label": group["label"],
            "average": round(sum(amounts) / len(amounts), 2),
            "baseline": round(
                sum(baselines) / len(baselines), 2
            ),
            "peak": round(max(amounts), 2),
            "readings": len(amounts),
            "above_baseline": group["above_baseline"],
            "empty_electricity": group["empty_electricity"]
        })

    return result


def build_report(period):
    settings = REPORT_PERIODS[period]
    end_time = datetime.now()
    start_time = end_time - timedelta(days=settings["days"])

    with get_db() as db:
        rows = db.execute("""
            SELECT *
            FROM resource_history
            WHERE recorded_at >= ?
              AND recorded_at <= ?
            ORDER BY recorded_at ASC, id ASC
        """, (
            start_time.strftime("%Y-%m-%d %H:%M:%S"),
            end_time.strftime("%Y-%m-%d %H:%M:%S")
        )).fetchall()

    history = [dict(row) for row in rows]

    summaries = {}
    classroom_summaries = {}

    for resource in ("Electricity", "Water"):
        resource_rows = [
            row for row in history
            if row["resource"] == resource
        ]

        amounts = [float(row["amount"]) for row in resource_rows]
        baselines = [
            float(row["baseline"]) for row in resource_rows
        ]

        summaries[resource] = {
            "reading_count": len(resource_rows),
            "average": (
                round(sum(amounts) / len(amounts), 2)
                if amounts else None
            ),
            "peak": round(max(amounts), 2) if amounts else None,
            "average_baseline": (
                round(sum(baselines) / len(baselines), 2)
                if baselines else None
            ),
            "above_baseline_count": sum(
                1 for row in resource_rows
                if row["amount"] > row["baseline"]
            ),
            "empty_classroom_readings": sum(
                1 for row in resource_rows
                if (
                    resource == "Electricity"
                    and int(row["occupied"]) == 0
                    and row["amount"] > 0
                )
            )
        }

        for classroom in sorted({
            row["classroom"] for row in resource_rows
        }):
            classroom_rows = [
                row for row in resource_rows
                if row["classroom"] == classroom
            ]

            values = [
                float(row["amount"]) for row in classroom_rows
            ]

            classroom_summaries.setdefault(classroom, {})

            classroom_summaries[classroom][resource] = {
                "reading_count": len(values),
                "average": round(sum(values) / len(values), 2),
                "peak": round(max(values), 2)
            }

    intervals = {}

    for interval in settings["intervals"]:
        intervals[interval] = aggregate_report_rows(
            history, interval
        )

    source_counts = {
        "simulation": sum(
            1 for row in history
            if row["source"] == "simulation"
        ),
        "manual": sum(
            1 for row in history
            if row["source"] == "manual"
        ),
        "existing": sum(
            1 for row in history
            if row["source"] == "existing"
        )
    }

    return {
        "period": period,
        "period_days": settings["days"],
        "from": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "to": end_time.strftime("%Y-%m-%d %H:%M:%S"),
        "reading_count": len(history),
        "data_available": bool(history),
        "intervals": intervals,
        "summaries": summaries,
        "classrooms": classroom_summaries,
        "source_counts": source_counts,
        "note": (
            "Simulated readings are demonstrations, not live sensor "
            "measurements. Values are snapshots; averages and peaks "
            "are reported instead of summing repeated snapshots."
        )
    }


# --------------------------------------------------
# DASHBOARD PAGE AND API
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
# REPORT API
# --------------------------------------------------

@app.route("/api/report")
def report_api():
    period = request.args.get("period", "1d").strip().lower()

    if period not in REPORT_PERIODS:
        return jsonify({
            "error": "Invalid report period.",
            "allowed_periods": list(REPORT_PERIODS.keys())
        }), 400

    report = build_report(period)

    response = jsonify(report)
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

        # Save manual readings to report history too.
        db.execute("""
            INSERT INTO resource_history (
                classroom, resource, amount, baseline,
                occupied, recorded_at, source
            )
            VALUES (?, ?, ?, ?, ?, ?, 'manual')
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
# RUN APPLICATION
# --------------------------------------------------

if __name__ == "__main__":
    init_db()
    sync_latest_resource_alerts()
    start_simulation()

    app.run(debug=True, use_reloader=False)
