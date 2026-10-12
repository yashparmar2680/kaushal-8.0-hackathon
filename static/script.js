
const POLL_INTERVAL = 5000;

let electricityChart = null;
let waterChart = null;
let refreshInProgress = false;

const $ = (id) => document.getElementById(id);

function formatNumber(value, decimals = 1) {
    return Number(value ?? 0).toLocaleString("en-IN", {
        maximumFractionDigits: decimals,
        minimumFractionDigits: decimals
    });
}

function makeElement(tag, className, text) {
    const element = document.createElement(tag);

    if (className) {
        element.className = className;
    }

    if (text !== undefined && text !== null) {
        element.textContent = String(text);
    }

    return element;
}

function showEmpty(container, message) {
    container.replaceChildren(
        makeElement("p", "alert-empty", message)
    );
}

function renderAlerts(alerts, activeCount) {
    const container = $("alertsList");
    if (!container) return;

    container.replaceChildren();

    const activeStatuses = ["New", "Acknowledged"];

    const calculatedActiveCount = alerts.filter(alert =>
        activeStatuses.includes(alert.status)
    ).length;

    const totalActive = Number.isFinite(Number(activeCount))
        ? Number(activeCount)
        : calculatedActiveCount;

    $("alertTotal").textContent = totalActive;
    $("alertBadge").textContent =
        `${totalActive} active alert${totalActive === 1 ? "" : "s"}`;

    if (!alerts.length) {
        showEmpty(
            container,
            "No alerts recorded yet. EcoCampus is monitoring your resources."
        );
        return;
    }

    alerts.slice(0, 50).forEach(alert => {
        const status = String(alert.status || "New");
        const severity = String(alert.severity || "Medium");
        const normalizedStatus = status.toLowerCase();
        const normalizedSeverity = severity.toLowerCase();

        const item = makeElement(
            "article",
            `alert-item severity-${normalizedSeverity} status-${normalizedStatus}`
        );

        const details = makeElement("div");
        const title = makeElement(
            "strong",
            "",
            `${alert.classroom || "Unknown classroom"} · ${alert.resource || "Resource"}`
        );

        const badges = makeElement("div", "alert-badges");

        badges.append(
            makeElement(
                "span",
                `alert-badge severity-${normalizedSeverity}`,
                `${severity} severity`
            ),
            makeElement(
                "span",
                `alert-badge status-${normalizedStatus}`,
                status
            )
        );

        const message = makeElement(
            "p",
            "",
            alert.message || alert.alert_type || "Resource usage needs review."
        );

        const amountText =
            alert.amount !== undefined && alert.baseline !== undefined
                ? `Recorded: ${formatNumber(alert.amount)} · Baseline: ${formatNumber(alert.baseline)}`
                : "";

        const measurements = makeElement("p", "muted", amountText);

        const timestamp = makeElement(
            "p",
            "alert-timestamp",
            `Detected: ${alert.detected_at || "Time unavailable"}`
        );

        details.append(title, badges, message);

        if (amountText) {
            details.append(measurements);
        }

        details.append(timestamp);

        if (status === "Acknowledged" && alert.updated_at) {
            details.append(
                makeElement(
                    "p",
                    "alert-timestamp",
                    `Last updated: ${alert.updated_at}`
                )
            );
        }

        if (status === "Resolved") {
            details.append(
                makeElement(
                    "p",
                    "alert-timestamp",
                    `Resolved: ${alert.resolved_at || alert.updated_at || "Time unavailable"}`
                )
            );
        }

        item.append(details);

        // Actions are available only for alerts that have an ID
        // and have not already been resolved.
        if (alert.id && status !== "Resolved") {
            const actions = makeElement("div", "alert-actions");

            if (status === "New") {
                const acknowledgeForm = document.createElement("form");
                acknowledgeForm.method = "POST";
                acknowledgeForm.action =
                    `/alerts/${encodeURIComponent(alert.id)}/acknowledge`;

                const acknowledgeButton = makeElement(
                    "button",
                    "acknowledge-button",
                    "✓ Acknowledge"
                );

                acknowledgeButton.type = "submit";
                acknowledgeForm.append(acknowledgeButton);
                actions.append(acknowledgeForm);
            }

            const resolveForm = document.createElement("form");
            resolveForm.method = "POST";
            resolveForm.action =
                `/alerts/${encodeURIComponent(alert.id)}/resolve`;

            const resolveButton = makeElement(
                "button",
                "resolve-button",
                "✓ Resolve"
            );

            resolveButton.type = "submit";
            resolveForm.append(resolveButton);
            actions.append(resolveForm);

            item.append(actions);
        }

        container.append(item);
    });

    if (alerts.length > 50) {
        container.append(
            makeElement(
                "p",
                "muted",
                `Showing 50 of ${alerts.length} alerts.`
            )
        );
    }
}

function renderInsights(insights) {
    const container = $("insightsList");
    if (!container) return;

    container.replaceChildren();

    if (!insights.length) {
        showEmpty(container, "No recommendations available yet.");
        return;
    }

    insights.forEach(insight => {
        container.append(
            makeElement("div", "insight", `💡 ${insight}`)
        );
    });
}

function renderRecords(records) {
    const body = $("recordsBody");
    if (!body) return;

    body.replaceChildren();

    $("recordCount").textContent =
        `${records.length.toLocaleString("en-IN")} records`;

    records.slice(0, 100).forEach(record => {
        const row = document.createElement("tr");
        const statusCell = document.createElement("td");
        const statusWrapper = makeElement("div", "record-status");

        const recordAlerts = Array.isArray(record.alerts)
            ? record.alerts
            : [];

        if (recordAlerts.length) {
            recordAlerts.forEach(message => {
                statusWrapper.append(
                    makeElement("span", "warning", message)
                );
            });
        } else {
            statusWrapper.append(
                makeElement("span", "good", "Within baseline")
            );
        }

        statusCell.append(statusWrapper);

        const values = [
            record.classroom,
            record.resource,
            `${formatNumber(record.amount)} ${
                record.resource === "Electricity" ? "kWh" : "L"
            }`,
            formatNumber(record.baseline),
            record.occupied ? "Occupied" : "Empty"
        ];

        values.forEach(value => {
            row.append(makeElement("td", "", value));
        });

        row.append(statusCell);
        row.append(
            makeElement("td", "", record.recorded_at || "—")
        );

        body.append(row);
    });

    if (!records.length) {
        const row = document.createElement("tr");
        const cell = makeElement("td", "", "No records available.");
        cell.colSpan = 7;
        row.append(cell);
        body.append(row);
    }

    if (records.length > 100) {
        const row = document.createElement("tr");
        const cell = makeElement(
            "td",
            "muted",
            `Showing the latest 100 of ${records.length} records.`
        );
        cell.colSpan = 7;
        row.append(cell);
        body.append(row);
    }
}

function updateChart(
    existingChart,
    canvasId,
    labels,
    values,
    label,
    color
) {
    const canvas = $(canvasId);

    if (!canvas || typeof Chart === "undefined") {
        return existingChart;
    }

    if (existingChart) {
        existingChart.data.labels = labels;
        existingChart.data.datasets[0].data = values;
        existingChart.update("none");
        return existingChart;
    }

    return new Chart(canvas, {
        type: "bar",
        data: {
            labels,
            datasets: [{
                label,
                data: values,
                backgroundColor: color,
                borderRadius: 6,
                maxBarThickness: 48
            }]
        },
        options: {
            responsive: true,
            animation: false,
            plugins: {
                legend: {
                    display: true,
                    position: "bottom"
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

function renderDashboard(data) {
    $("electricityTotal").innerHTML =
        `${formatNumber(data.electricity)} <small>kWh</small>`;

    $("waterTotal").innerHTML =
        `${formatNumber(data.water, 0)} <small>litres</small>`;

    $("savingsTotal").textContent = formatNumber(data.saved);

    $("electricitySavings").textContent =
        `${formatNumber(data.electricity_saved)} kWh`;

    $("waterSavings").textContent =
        `${formatNumber(data.water_saved)} litres`;

    $("lastUpdated").textContent = data.last_updated
        ? `Latest record: ${data.last_updated}`
        : "Waiting for readings";

    const classrooms = data.classrooms || [];
    const labels = classrooms.map(room => room.classroom);

    electricityChart = updateChart(
        electricityChart,
        "electricityChart",
        labels,
        classrooms.map(room => room.electricity),
        "Electricity (kWh)",
        "#268657"
    );

    waterChart = updateChart(
        waterChart,
        "waterChart",
        labels,
        classrooms.map(room => room.water),
        "Water (litres)",
        "#68aee8"
    );

    renderAlerts(
        data.alerts || [],
        data.active_alerts
    );

    renderInsights(data.insights || []);
    renderRecords(data.records || []);

    const recordCount = (data.records || []).length;

    $("connectionStatus").textContent =
        `Connected · ${recordCount} displayed records · ` +
        `Dashboard refreshes every ${POLL_INTERVAL / 1000} seconds`;
}

async function refreshDashboard() {
    if (refreshInProgress) return;

    refreshInProgress = true;

    try {
        const response = await fetch("/api/dashboard", {
            cache: "no-store"
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        renderDashboard(data);
    } catch (error) {
        console.error("Dashboard update failed:", error);

        $("connectionStatus").textContent =
            "Connection problem. Retrying automatically...";
    } finally {
        refreshInProgress = false;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    refreshDashboard();
    setInterval(refreshDashboard, POLL_INTERVAL);
});

/* =========================================
   ECOPCAMPUS SUSTAINABILITY REPORTS
   ========================================= */

let reportElectricityChartInstance = null;
let reportWaterChartInstance = null;
let latestSustainabilityReport = null;

async function loadSustainabilityReport() {
    const periodElement = document.getElementById("reportPeriod");
    const statusElement = document.getElementById("reportStatus");

    if (!periodElement || !statusElement) {
        return;
    }

    const period = periodElement.value;

    statusElement.textContent = "Generating sustainability report...";

    const loadButton = document.getElementById("loadReportButton");
    if (loadButton) loadButton.disabled = true;

    try {
        const response = await fetch(
            `/api/report?period=${encodeURIComponent(period)}`,
            { cache: "no-store" }
        );

        if (!response.ok) {
            throw new Error(`Server returned ${response.status}`);
        }

        const data = await response.json();
        latestSustainabilityReport = data;

        renderSustainabilityReport(data);

        statusElement.textContent = data.data_available
            ? `Report generated for the selected period.`
            : "No readings found for this period. Try another period.";

    } catch (error) {
        console.error("Sustainability report error:", error);
        statusElement.textContent =
            "Could not load the report. Check that Flask is running and try again.";
    } finally {
        if (loadButton) loadButton.disabled = false;
    }
}

function formatReportNumber(value) {
    const number = Number(value);

    return Number.isFinite(number)
        ? number.toLocaleString("en-IN", {
            maximumFractionDigits: 2
        })
        : "0";
}

function renderSustainabilityReport(data) {
    const electricity = data.summaries?.Electricity || {};
    const water = data.summaries?.Water || {};

    const electricityAverage =
        document.getElementById("reportElectricityAverage");
    const waterAverage =
        document.getElementById("reportWaterAverage");
    const readingCount =
        document.getElementById("reportReadingCount");
    const aboveBaseline =
        document.getElementById("reportAboveBaseline");

    if (electricityAverage) {
        electricityAverage.textContent =
            formatReportNumber(electricity.average);
    }

    if (waterAverage) {
        waterAverage.textContent =
            formatReportNumber(water.average);
    }

    if (readingCount) {
        readingCount.textContent =
            formatReportNumber(data.reading_count);
    }

    if (aboveBaseline) {
        aboveBaseline.textContent = formatReportNumber(
            (electricity.above_baseline_count || 0) +
            (water.above_baseline_count || 0)
        );
    }

    renderReportClassrooms(data.classrooms || {});
    renderReportNotes(data);
    renderSustainabilityCharts(data);
}

function renderReportClassrooms(classrooms) {
    const tableBody =
        document.getElementById("reportClassroomBody");

    if (!tableBody) return;

    tableBody.replaceChildren();

    const roomNames = Object.keys(classrooms);

    if (roomNames.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");

        cell.colSpan = 5;
        cell.textContent = "No classroom readings available.";

        row.appendChild(cell);
        tableBody.appendChild(row);
        return;
    }

    roomNames.forEach((roomName) => {
        const room = classrooms[roomName] || {};
        const electricity = room.Electricity || {};
        const water = room.Water || {};

        const row = document.createElement("tr");

        const values = [
            roomName,
            formatReportNumber(electricity.average) + " kWh",
            formatReportNumber(electricity.peak) + " kWh",
            formatReportNumber(water.average) + " L",
            formatReportNumber(water.peak) + " L"
        ];

        values.forEach((value) => {
            const cell = document.createElement("td");
            cell.textContent = value;
            row.appendChild(cell);
        });

        tableBody.appendChild(row);
    });
}

function renderReportNotes(data) {
    const notesElement = document.getElementById("reportNotes");

    if (!notesElement) return;

    const notes = [];

    if (data.note) {
        notes.push(data.note);
    }

    notes.push(
        `Readings included: ${formatReportNumber(data.reading_count)}.`
    );

    const sources = data.source_counts || {};
    const simulated = sources.simulation || 0;
    const manual = sources.manual || 0;
    const existing = sources.existing || 0;

    notes.push(
        `Data sources — Simulated: ${simulated}, ` +
        `Manual: ${manual}, Existing: ${existing}.`
    );

    notesElement.textContent = notes.join(" ");
}

function renderSustainabilityCharts(data) {
    if (typeof Chart === "undefined") {
        console.error("Chart.js is not loaded.");
        return;
    }

    const period = data.period;
    const intervals = data.intervals || {};

    // Select the clearest time grouping for each report period.
    let selectedIntervals;

    if (period === "1d") {
        selectedIntervals = intervals.hourly || {};
    } else if (period === "7d") {
        selectedIntervals = intervals.daily || intervals.hourly || {};
    } else {
        selectedIntervals = intervals.weekly || intervals.daily || {};
    }

    const electricityPoints = selectedIntervals.Electricity || [];
    const waterPoints = selectedIntervals.Water || [];

    const electricityCanvas =
        document.getElementById("reportElectricityChart");
    const waterCanvas =
        document.getElementById("reportWaterChart");

    if (electricityCanvas) {
        if (reportElectricityChartInstance) {
            reportElectricityChartInstance.destroy();
        }

        reportElectricityChartInstance = createSustainabilityChart(
            electricityCanvas,
            electricityPoints,
            "Electricity (kWh)"
        );
    }

    if (waterCanvas) {
        if (reportWaterChartInstance) {
            reportWaterChartInstance.destroy();
        }

        reportWaterChartInstance = createSustainabilityChart(
            waterCanvas,
            waterPoints,
            "Water (litres)"
        );
    }
}

function createSustainabilityChart(canvas, points, label) {
    return new Chart(canvas, {
        type: "line",
        data: {
            labels: points.map((point) => point.label),
            datasets: [
                {
                    label: `Average ${label}`,
                    data: points.map((point) => point.average),
                    borderWidth: 2,
                    tension: 0.25
                },
                {
                    label: `Expected ${label}`,
                    data: points.map((point) => point.baseline),
                    borderWidth: 2,
                    borderDash: [6, 5],
                    tension: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: "index"
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: label
                    }
                },
                x: {
                    ticks: {
                        maxRotation: 45,
                        minRotation: 0
                    }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: "bottom"
                }
            }
        }
    });
}

function downloadSustainabilityReportCSV() {
    if (!latestSustainabilityReport) {
        const status = document.getElementById("reportStatus");

        if (status) {
            status.textContent =
                "Generate a report before downloading the CSV.";
        }

        return;
    }

    const data = latestSustainabilityReport;
    const rows = [
        ["EcoCampus Sustainability Report"],
        ["Period", data.period],
        ["From", data.from],
        ["To", data.to],
        [],
        [
            "Classroom",
            "Electricity Average (kWh)",
            "Electricity Peak (kWh)",
            "Water Average (litres)",
            "Water Peak (litres)"
        ]
    ];

    Object.entries(data.classrooms || {}).forEach(([roomName, room]) => {
        const electricity = room.Electricity || {};
        const water = room.Water || {};

        rows.push([
            roomName,
            electricity.average ?? 0,
            electricity.peak ?? 0,
            water.average ?? 0,
            water.peak ?? 0
        ]);
    });

    rows.push(
        [],
        ["Total readings", data.reading_count ?? 0],
        [
            "Electricity average (kWh)",
            data.summaries?.Electricity?.average ?? 0
        ],
        [
            "Water average (litres)",
            data.summaries?.Water?.average ?? 0
        ],
        [
            "Readings above baseline",
            (data.summaries?.Electricity?.above_baseline_count || 0) +
            (data.summaries?.Water?.above_baseline_count || 0)
        ],
        [],
        ["Report note", data.note || ""]
    );

    const csv = rows.map((row) =>
        row.map((value) => {
            const safeValue = String(value ?? "");
            return `"${safeValue.replace(/"/g, '""')}"`;
        }).join(",")
    ).join("\r\n");

    const blob = new Blob(["\uFEFF" + csv], {
        type: "text/csv;charset=utf-8;"
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = `ecocampus-report-${data.period}.csv`;

    document.body.appendChild(link);
    link.click();
    link.remove();

    URL.revokeObjectURL(url);
}

// Connect only the new report controls.
document.addEventListener("DOMContentLoaded", () => {
    const loadButton = document.getElementById("loadReportButton");
    const downloadButton =
        document.getElementById("downloadReportButton");
    const periodSelect = document.getElementById("reportPeriod");

    if (loadButton) {
        loadButton.addEventListener(
            "click",
            loadSustainabilityReport
        );
    }

    if (downloadButton) {
        downloadButton.addEventListener(
            "click",
            downloadSustainabilityReportCSV
        );
    }

    if (periodSelect) {
        periodSelect.addEventListener(
            "change",
            loadSustainabilityReport
        );
    }

    // Load the initial report when the page opens.
    if (periodSelect) {
        loadSustainabilityReport();
    }
});
