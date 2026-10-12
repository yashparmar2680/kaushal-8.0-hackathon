# EcoCampus — Testing Documentation

## 1. Overview

EcoCampus is a smart campus sustainability dashboard developed for KAUSHAL 8.0, PS-04. This document describes how to run and test the application's main features.

## 2. Testing Environment

- **Language:** Python
- **Web Framework:** Flask
- **Database:** SQLite
- **Frontend:** HTML, CSS, JavaScript
- **Browser:** Any modern web browser

## 3. How to Run the Application

1. Open a terminal in the project directory.
2. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Start the application:

   ```bash
   python app.py
   ```

4. Open the local URL shown in the terminal, usually `http://127.0.0.1:5000`.

## 4. Test Cases

| Test Case | Expected Result |
|---|---|
| Open the dashboard | The dashboard loads successfully. |
| View resource readings | Electricity and water usage records are displayed. |
| Add a resource record | The record is saved and displayed, if manual entry is enabled. |
| Check baseline alerts | Readings exceeding configured baselines can trigger alerts. |
| Check empty-classroom alerts | Electricity usage in a classroom marked unoccupied can trigger an alert, when the required conditions are met. |
| View charts and insights | Usage trends and summaries are displayed, if implemented and configured. |
| Refresh the dashboard | The page updates without errors. |

## 5. Simulated Data Disclosure

This prototype uses simulated electricity and water readings for demonstration and testing. The readings are not collected from physical sensors, smart meters, or actual campus utility bills.

Any simulated occupancy information, baseline comparisons, alerts, and sustainability insights are intended to demonstrate the application's functionality. They should not be interpreted as verified measurements of actual campus consumption.

## 6. Current Scope and Limitations

- The prototype demonstrates software-based resource monitoring.
- Alert results depend on the recorded or simulated readings, configured baselines, and occupancy status.
- Real-world accuracy has not been established through physical sensor measurements.
- IoT integration and real campus data collection can be considered future improvements.

## 7. Test Results

Run the test cases above and record the actual results before submission. Mark a feature as passed only after verifying it in the running application.

**Project:** EcoCampus — Smart Campus Sustainability Platform  
**Event:** KAUSHAL 8.0  