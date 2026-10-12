
const POLL_INTERVAL = 5000; // Refresh display every 5 seconds

let electricityChart = null;
let waterChart = null;
let refreshInProgress = false;

const $ = (id) => document.getElementById(id);

function formatNumber(value, decimals = 1) {
    return Number(value).toLocaleString("en-IN", {
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
    container.replaceChildren(makeElement("p", "muted", message));
}

function renderAlerts(alerts) {
    const container = $("alertsList");
    container.replaceChildren();

    $("alertTotal").textContent = alerts.length;
    $("alertBadge").textContent =
        `${alerts.length} alert${alerts.length === 1 ? "" : "s"}`;

    if (!alerts.length) {
        showEmpty(container, "No potential issues detected in the current records.");
        return;
    }

    alerts.slice(0, 50).forEach(alert => {
        const item = makeElement("div", "alert-item");
        const details = makeElement("div");
        const title = makeElement("strong", "", alert.classroom);
        const description = makeElement(
            "p",
            "",
            `${alert.resource} · ${alert.recorded_at}`
        );
        const warning = makeElement("span", "warning", alert.message);

        details.append(title, description);
        item.append(details, warning);
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
    body.replaceChildren();

    $("recordCount").textContent =
        `${records.length.toLocaleString("en-IN")} records`;

    records.slice(0, 100).forEach(record => {
        const row = document.createElement("tr");

        const status = makeElement("td");
        const statusWrapper = makeElement("div", "record-status");

        if (record.alerts.length) {
            record.alerts.forEach(message => {
                statusWrapper.append(
                    makeElement("span", "warning", message)
                );
            });
        } else {
            statusWrapper.append(
                makeElement("span", "good", "Within baseline")
            );
        }

        status.append(statusWrapper);

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

        row.append(status);
        row.append(makeElement("td", "", record.recorded_at));
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

function updateChart(existingChart, canvasId, labels, values, label, color) {
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

    renderAlerts(data.alerts || []);
    renderInsights(data.insights || []);
    renderRecords(data.records || []);

    $("connectionStatus").textContent =
        `Connected · ${data.records.length} records · ` +
        `Dashboard refreshes every ${POLL_INTERVAL / 1000} seconds`;
}

async function refreshDashboard() {
    if (refreshInProgress) {
        return;
    }

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
