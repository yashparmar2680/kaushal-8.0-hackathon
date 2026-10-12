
const chartCanvas = document.getElementById("classroomChart");

if (chartCanvas && typeof Chart !== "undefined") {
    const names = classrooms.map(room => room.classroom);
    const electricity = classrooms.map(room => room.electricity);
    const water = classrooms.map(room => room.water);

    new Chart(chartCanvas, {
        type: "bar",
        data: {
            labels: names,
            datasets: [
                {
                    label: "Electricity (kWh)",
                    data: electricity,
                    backgroundColor: "#268657",
                    borderRadius: 5
                },
                {
                    label: "Water (litres)",
                    data: water,
                    backgroundColor: "#68aee8",
                    borderRadius: 5
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
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
