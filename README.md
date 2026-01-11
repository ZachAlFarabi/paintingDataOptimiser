# Paint Process Analytics Dashboard

A Flask-based web application for logging paint booth records, computing lag/paint efficiency metrics, and visualising operational distributions and convex-hull–based recommendations.

---

## Features

- Parse semi-structured paint booth log lines
- Persist records to CSV (`data/records.csv`)
- Compute:
  - Paint time
  - Lag time
  - Recommended lag (buffered convex hull)
  - Avoidable lag
  - Lag-to-paint ratio
- Interactive dashboard (Flask + HTML/JS)
- Export full dataset to Excel
- Ready for deployment on Railway / Render / Heroku

---

## Project Structure

- app.py
- Procfile
- requirements.txt
- runtime.txt
- data/
  - records.csv
- static/
  - script.js
  - style.css
- templates/
  - dashboard.html
 

---

## Requirements

- Python 3.9+
- Libraries:
  - flask
  - pandas
  - numpy
  - scipy
  - openpyxl

Install locally:
```bash
pip install -r requirements.txt
```

Running locally:
```bash
python app.py
http://127.0.0.1:5000
```
---

## Input format

```bash
<paintRecord> <ts>;
<date> <operator> <timeInBooth> <timeStart> <timeEnd>;
```

- Time format: Military
- Use x for unknown field
- Use ~ to skip process
- Enter xxx to undo the last record

