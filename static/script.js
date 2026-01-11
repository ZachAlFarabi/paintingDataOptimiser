const inputLine = document.getElementById('inputLine');
const recordsTable = document.getElementById('recordsTable');
const exportBtn = document.getElementById('exportBtn');

/* ---------------- Input handling ---------------- */
inputLine.addEventListener('keypress', e => {
    if (e.key === 'Enter') {
        e.preventDefault();

        fetch('/addLine', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ line: inputLine.value })
        })
        .then(r => r.json())
        .then(data => {
            renderTable(data.table);
            renderFigures(data.table);
            inputLine.value = '';
        });
    }
});

exportBtn.onclick = () => {
    window.location = '/exportExcel';
};

/* ---------------- Table rendering ---------------- */
function renderTable(data) {

    const columns = [
        'paintRecord','ts','process','date','operator',
        'timeInBooth','timeStart','timeEnd','paintTime','lagTime',
        'recommendedLag','avoidableLag','lagToPaintRatio'
    ];

    let html = '<table border="1" style="border-collapse:collapse;width:100%">';
    html += '<thead><tr>';

    columns.forEach(c => {
        html += `<th>${c}</th>`;
    });

    html += '</tr></thead><tbody>';

    if (data && data.length > 0) {
        data.forEach(row => {
            html += '<tr>';
            columns.forEach(c => {
                html += `<td>${row[c] ?? ''}</td>`;
            });
            html += '</tr>';
        });
    } else {
        html += `
            <tr>
                <td colspan="${columns.length}" 
                    style="text-align:center;font-style:italic;">
                    No records
                </td>
            </tr>
        `;
    }

    html += '</tbody></table>';
    recordsTable.innerHTML = html;
}

/* ---------------- Figures ---------------- */
function renderFigures(data) {

    const paint = [];
    const lag = [];
    const rec = [];
    const ratios = [];
    const startTimes = [];

    data.forEach(r => {
        if (r.paintTime != null && r.lagTime != null) {
            paint.push(r.paintTime);
            lag.push(r.lagTime);
            rec.push(r.recommendedLag ?? null);
            ratios.push(r.lagToPaintRatio ?? null);
        }
        if (r.timeStart != null) {
            startTimes.push(r.timeStart);
        }
    });

    Plotly.newPlot(
        'convexHullFig',
        [
            { x: paint, y: lag, mode: 'markers', name: 'Actual' },
            { x: paint, y: rec, mode: 'lines', name: 'Recommended' }
        ],
        {
            title: 'Paint vs Lag Time',
            xaxis: { title: 'Paint Time (h)' },
            yaxis: { title: 'Lag Time (h)' }
        }
    );

    Plotly.newPlot(
        'lagRatioFig',
        [
            { x: ratios.filter(v => v != null), type: 'histogram' }
        ],
        {
            title: 'Lag / Paint Ratio',
            xaxis: { title: 'Lag / Paint' }
        }
    );

    Plotly.newPlot(
        'timeDistributionFig',
        [
            { x: startTimes, type: 'histogram' }
        ],
        {
            title: 'Start Time Distribution',
            xaxis: { title: 'Time (hours since midnight)' }
        }
    );
}