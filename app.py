from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import numpy as np
from scipy.spatial import ConvexHull, QhullError
import os
import io

app = Flask(__name__)

DATA_FILE = 'data/records.csv'
WINDOW_DAYS = 40
BUFFER_HOURS = 0.0833
MIN_HULL_SUPPORT = 2  # allow hull for 2+ points

# Ensure CSV exists
os.makedirs('data', exist_ok=True)
if not os.path.exists(DATA_FILE):
    pd.DataFrame(columns=[
        'paintRecord','ts','process','date','operator',
        'timeInBooth','timeStart','timeEnd','paintTime','lagTime'
    ]).to_csv(DATA_FILE,index=False)

# --- Utilities ---
def militaryTimeToHours(s):
    h = int(s[:2])
    m = int(s[2:])
    return h + m/60

def parseLine(line):
    parts = line.strip().split(';')
    paintRecord, ts = parts[0].split()
    processes = ['primer','topcoat','extra']
    records = []
    for i, part in enumerate(parts[1:]):
        if part.strip() == '~':
            records.append({
                'paintRecord': int(paintRecord),
                'ts': ts,  # keep as string
                'process': processes[i],
                'date': None,
                'operator': None,
                'timeInBooth': None,
                'timeStart': None,
                'timeEnd': None,
                'paintTime': None,
                'lagTime': None
            })
        else:
            tokens = part.strip().split()
            date = tokens[0]
            operator = tokens[1]
            timeInBooth = militaryTimeToHours(tokens[2])
            timeStart = militaryTimeToHours(tokens[3])
            timeEnd = militaryTimeToHours(tokens[4])
            paintTime = timeEnd - timeStart
            lagTime = timeStart - timeInBooth
            records.append({
                'paintRecord': int(paintRecord),
                'ts': ts,
                'process': processes[i],
                'date': date,
                'operator': operator,
                'timeInBooth': timeInBooth,
                'timeStart': timeStart,
                'timeEnd': timeEnd,
                'paintTime': paintTime,
                'lagTime': lagTime
            })
    return records

# --- Hull computation ---
def computeBufferedHull(df):
    hullPointsByTS = {}
    recommendedLagDict = {}
    avoidableLagList = []

    df['date_dt'] = pd.to_datetime(df['date'], format='%d/%m/%y', errors='coerce')
    currentDate = df['date_dt'].max() if not df['date_dt'].isna().all() else pd.Timestamp.now()
    cutoff = currentDate - pd.Timedelta(days=WINDOW_DAYS)
    recentDf = df[df['date_dt'] >= cutoff]

    for ts in recentDf['ts'].unique():
        hullPointsByTS[ts] = {}
        for process in ['primer','topcoat','extra']:
            procDf = recentDf[(recentDf['ts']==ts) & (recentDf['process']==process)]
            points = procDf[['paintTime','lagTime']].dropna().values

            # Remove duplicates
            unique_points = np.unique(points, axis=0)
            if len(unique_points) < MIN_HULL_SUPPORT:
                hullPointsByTS[ts][process] = []
                continue

            try:
                hull = ConvexHull(unique_points, qhull_options='QJ')
                vertices = unique_points[hull.vertices]
                vertices = vertices[np.argsort(vertices[:,0])]

                # Build lower hull
                lowerHull = [vertices[0]]
                for x, y in vertices[1:]:
                    if y <= lowerHull[-1][1]:
                        lowerHull.append([x,y])

                # Add buffer and ensure floats
                bufferedHull = [[float(x), float(y + BUFFER_HOURS)] for x, y in lowerHull]
                hullPointsByTS[ts][process] = bufferedHull
            except QhullError:
                hullPointsByTS[ts][process] = []

    # Compute recommended lag and avoidable lag
    for idx, row in df.iterrows():
        ts = row['ts']
        process = row['process']
        paintTime = row['paintTime']
        lagTime = row['lagTime']
        recLag = None
        hull = hullPointsByTS.get(ts, {}).get(process, [])
        if hull and pd.notna(paintTime):
            hullArr = np.array(hull, dtype=float)
            xVals, yVals = hullArr[:,0], hullArr[:,1]
            if paintTime <= xVals[0]:
                recLag = float(yVals[0])
            elif paintTime >= xVals[-1]:
                recLag = float(yVals[-1])
            else:
                recLag = float(np.interp(paintTime, xVals, yVals))
        recommendedLagDict[idx] = recLag
        avoidableLag = float(max(0, lagTime - recLag)) if recLag is not None and pd.notna(lagTime) else None
        avoidableLagList.append(avoidableLag)

    df['recommendedLag'] = df.index.map(recommendedLagDict)
    df['avoidableLag'] = avoidableLagList
    df['lagToPaintRatio'] = df.apply(
        lambda r: float(r['lagTime']/r['paintTime']) if pd.notna(r['lagTime']) and pd.notna(r['paintTime']) else None,
        axis=1
    )

    return df, hullPointsByTS

# --- Flask routes ---
@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/addLine', methods=['POST'])
def addLine():
    line = request.json.get('line')
    df = pd.read_csv(DATA_FILE)

    if line.strip() == 'xxx':
        if not df.empty:
            last = df.iloc[-1]
            mask = (df['paintRecord'] == last['paintRecord']) & (df['ts'] == last['ts'])
            df = df[~mask]
            df.to_csv(DATA_FILE, index=False)
        dfCalc,_ = computeBufferedHull(df)
        return jsonify({
            'status': 'ok',
            'table': dfCalc.drop(columns=['date_dt'], errors='ignore').fillna('').to_dict(orient='records'),
            'hulls': {}
        })

    records = parseLine(line)
    df = pd.concat([df, pd.DataFrame(records)], ignore_index=True)
    df.to_csv(DATA_FILE, index=False)
    dfCalc, hulls = computeBufferedHull(df)

    # --- SAFE hulls serialization (force ts as string) ---
    safeHulls = {}
    for ts, processes in hulls.items():
        ts_str = str(ts)  # <-- force string keys
        safeHulls[ts_str] = {}
        for proc, points in processes.items():
            safePoints = []
            for p in points:
                try:
                    x = float(p[0])
                    y = float(p[1])
                    safePoints.append([x, y])
                except (ValueError, TypeError, IndexError):
                    continue
            safeHulls[ts_str][proc] = safePoints

    table = dfCalc.drop(columns=['date_dt'], errors='ignore').fillna('').to_dict(orient='records')
    return jsonify({'status':'ok','table':table,'hulls':safeHulls})

@app.route('/exportExcel')
def exportExcel():
    df = pd.read_csv(DATA_FILE)
    dfCalc,_ = computeBufferedHull(df)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        dfCalc.to_excel(writer, index=False, sheet_name='PaintData')
    output.seek(0)
    return send_file(output, download_name='paint_records.xlsx', as_attachment=True)

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)