
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
