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
MIN_HULL_SUPPORT = 2

# Ensure CSV exists
os.makedirs('data', exist_ok=True)
if not os.path.exists(DATA_FILE):
    pd.DataFrame(columns=[
        'paintRecord','ts','process','date','operator',
        'timeInBooth','timeStart','timeEnd','paintTime','lagTime'
    ]).to_csv(DATA_FILE, index=False)

# ---------- Utilities ----------
def militaryTimeToHours(s):
    if s is None or s.lower() == 'x':
        return None
    h = int(s[:2])
    m = int(s[2:])
    return h + m / 60

def parseLine(line):
    parts = line.strip().split(';')
    paintRecord, ts = parts[0].split()
    processes = ['primer','topcoat','extra']
    records = []

    for i, part in enumerate(parts[1:]):
        part = part.strip()
        if part == '~':
            continue

        tokens = part.split()
        date = tokens[0] if tokens[0].lower() != 'x' else None
        operator = tokens[1] if tokens[1].lower() != 'x' else None
        timeInBooth = militaryTimeToHours(tokens[2]) if len(tokens) > 2 else None
        timeStart   = militaryTimeToHours(tokens[3]) if len(tokens) > 3 else None
        timeEnd     = militaryTimeToHours(tokens[4]) if len(tokens) > 4 else None

        paintTime = timeEnd - timeStart if timeStart is not None and timeEnd is not None else None
        lagTime   = timeStart - timeInBooth if timeStart is not None and timeInBooth is not None else None

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

# ---------- Hull Computation ----------
def computeBufferedHull(df):
    hullPointsByTS = {}
    recommendedLagDict = {}
    avoidableLagList = []

    df['date_dt'] = pd.to_datetime(df['date'], format='%d/%m/%y', errors='coerce')
    cutoff = (df['date_dt'].max() if not df['date_dt'].isna().all() else pd.Timestamp.now()) - pd.Timedelta(days=WINDOW_DAYS)
    recentDf = df[df['date_dt'] >= cutoff]

    for ts in recentDf['ts'].unique():
        hullPointsByTS[ts] = {}
        for process in ['primer','topcoat','extra']:
            procDf = recentDf[(recentDf['ts'] == ts) & (recentDf['process'] == process)]
            points = procDf[['paintTime','lagTime']].dropna().values
            points = np.unique(points, axis=0)

            if len(points) < MIN_HULL_SUPPORT:
                hullPointsByTS[ts][process] = []
                continue

            try:
                hull = ConvexHull(points, qhull_options='QJ')
                vertices = points[hull.vertices]
                vertices = vertices[np.argsort(vertices[:,0])]

                lower = [vertices[0]]
                for x, y in vertices[1:]:
                    if y <= lower[-1][1]:
                        lower.append([x,y])

                hullPointsByTS[ts][process] = [[float(x), float(y + BUFFER_HOURS)] for x,y in lower]
            except QhullError:
                hullPointsByTS[ts][process] = []

    for idx, r in df.iterrows():
        hull = hullPointsByTS.get(r['ts'], {}).get(r['process'], [])
        recLag = None

        if hull and pd.notna(r['paintTime']):
            h = np.array(hull)
            recLag = float(np.interp(r['paintTime'], h[:,0], h[:,1]))

        recommendedLagDict[idx] = recLag
        avoidableLagList.append(
            max(0, r['lagTime'] - recLag) if recLag is not None and pd.notna(r['lagTime']) else None
        )

    df['recommendedLag'] = df.index.map(recommendedLagDict)
    df['avoidableLag'] = avoidableLagList
    df['lagToPaintRatio'] = df.apply(
        lambda r: r['lagTime']/r['paintTime'] if pd.notna(r['lagTime']) and pd.notna(r['paintTime']) else None,
        axis=1
    )

    return df, hullPointsByTS

# ---------- Utility to convert hours to hhmm ----------
def hoursToMilitary(h):
    if pd.isna(h):
        return ''
    h_int = int(h)
    m_int = int(round((h - h_int) * 60))
    return f"{h_int:02d}{m_int:02d}"

# ---------- Routes ----------
@app.route('/addLine', methods=['POST'])
def addLine():
    line = request.json.get('line')
    df = pd.read_csv(DATA_FILE)

    if line.strip() == 'xxx' and not df.empty:
        last = df.iloc[-1]
        df = df[~((df['paintRecord']==last['paintRecord']) & (df['ts']==last['ts']))]
        df.to_csv(DATA_FILE, index=False)
    elif line.strip() != 'xxx':
        records = parseLine(line)
        if records:
            df = pd.concat([df, pd.DataFrame(records)], ignore_index=True)
            df.to_csv(DATA_FILE, index=False)

    dfCalc, hulls = computeBufferedHull(df)

    # Convert time columns to military time for display
    for col in ['timeInBooth','timeStart','timeEnd']:
        dfCalc[col] = dfCalc[col].apply(hoursToMilitary)

    safeHulls = {str(ts): {p: v for p,v in procs.items()} for ts,procs in hulls.items()}
    table = dfCalc.drop(columns=['date_dt'], errors='ignore').fillna('').to_dict(orient='records')

    return jsonify({'status': 'ok', 'table': table, 'hulls': safeHulls})

@app.route('/exportExcel')
def exportExcel():
    df = pd.read_csv(DATA_FILE)
    dfCalc,_ = computeBufferedHull(df)
    for col in ['timeInBooth','timeStart','timeEnd']:
        dfCalc[col] = dfCalc[col].apply(hoursToMilitary)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        dfCalc.to_excel(writer, index=False)
    output.seek(0)
    return send_file(output, download_name='paint_records.xlsx', as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
