# 🌱 EcoCampus — Smart Campus Sustainability Dashboard

**Monitor campus resource consumption, detect wastage, and promote sustainable resource usage.**

EcoCampus is a software-based sustainability dashboard designed to help colleges monitor electricity and water consumption across classrooms. It uses resource readings, automatic simulation, and smart alerts to identify unusual consumption and help campus administrators make more informed decisions.

## 🎯 Problem Statement

Resource wastage — whether water, electricity, or materials — often goes unnoticed simply because no one is tracking it

in a way people can act on. Build a software solution that helps an individual, a classroom, or a campus see, understand,

or reduce its environmental footprint in some measurable way. EcoCampus aims to make campus resource consumption more visible, understandable, and actionable.

## 💡 Our Solution

EcoCampus provides a centralized dashboard that displays classroom resource usage, compares readings against configured baselines, and generates alerts when unusual consumption is detected.

The MVP uses simulated readings to demonstrate the core functionality without requiring physical IoT hardware.

## ✨ Key Features

- 📊 **Live Dashboard:** View electricity and water consumption data.
- 🔄 **Automatic Simulation:** Generate updated sample readings automatically.
- 🚨 **Smart Alerts:** Detect unusual resource consumption.
- ✅ **Alert Management:** Acknowledge alerts and mark issues as resolved.
- 📈 **Charts and Insights:** Understand resource usage patterns.
- 🏫 **Classroom Monitoring:** View resource records for individual classrooms.
- 🌍 **Sustainability Focus:** Encourage responsible use of campus resources.

## 🛠️ Tech Stack

- **Frontend:** HTML, CSS, JavaScript
- **Backend:** Python, Flask
- **Database:** SQLite (Future Integration)
- **Charts and Visualization:** JavaScript-based dashboard charts

## ⚙️ How It Works

1. The application obtains classroom resource readings from its SQLite database.
2. The simulation generates updated sample readings automatically.
3. Flask processes the readings and provides dashboard data through an API.
4. The dashboard refreshes periodically to display updated information.
5. The alert system identifies readings that exceed configured limits.
6. Users can acknowledge alerts and mark them as resolved.

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or newer recommended
- pip
- Git (optional)

### Installation

**1. Clone the repository**

```bash
git clone https://github.com/yashparmar2680/kaushal-8.0-hackathon.git
cd kaushal-8.0-hackathon
```

**2. Create a virtual environment (recommended)**

```bash
python -m venv venv
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

**3. Install dependencies**

If a `requirements.txt` file exists:

```bash
pip install -r requirements.txt
```

Otherwise, install the dependencies used by the project, including Flask:

```bash
pip install Flask
```

**4. Run the application**

```bash
python app.py
```

**5. Open the dashboard**

Visit:

[http://127.0.0.1:5000](http://127.0.0.1:5000)

## 📸 Project Screenshots

### Dashboard
![EcoCampus Dashboard](screenshots/dashboard.png)

### Smart Alerts
![EcoCampus Smart Alerts](screenshots/smart-alerts.png)

## 🧪 Current MVP Scope

- Demonstrates classroom electricity and water monitoring.
- Uses simulated readings for testing and demonstration.
- Includes automated alert generation and alert management.
- Stores resource and alert information in SQLite.

**Note:** The current MVP uses simulated data and does not claim to read from physical IoT sensors.

## 🔮 Future Improvements

- Integrate real IoT sensors when hardware access is available.
- Add historical usage reports and downloadable analytics.
- Estimate carbon emissions using a documented, configurable emissions factor.
- Add role-based access for administrators.
- Introduce campus-wide sustainability goals and resource-saving recommendations.

## 🌿 Expected Impact

EcoCampus aims to help educational institutions identify potential resource wastage, improve awareness of electricity and water consumption, and support data-informed sustainability decisions.

## 👨‍💻 Built For

**Kaushal 8.0 Hackathon**

Created as a software-based MVP focused on campus sustainability and responsible resource management.

---

*EcoCampus — Small insights, smarter campuses, a greener future.*
