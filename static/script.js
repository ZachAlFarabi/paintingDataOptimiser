const inputLine = document.getElementById('inputLine');
const recordsTable = document.getElementById('recordsTable');
const exportBtn = document.getElementById('exportBtn');

inputLine.addEventListener('keypress', e => {
    if (e.key === 'Enter') {
        e.preventDefault();
        fetch('/addLine', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
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

exportBtn.onclick = () => window.location = '/exportExcel';

function renderTable(data){
    if (!data.length) {
        recordsTable.innerHTML = '<i>No records</i>';
        return;
    }

    const cols = Object.keys(data[0]);
    let html = '<table><tr>' + cols.map(c=>`<th>${c}</th>`).join('') + '</tr>';

    data.forEach(r => {
        html += '<tr>' + cols.map(c=>`<td>${r[c] ?? ''}</td>`).join('') + '</tr>';
    });

    recordsTable.innerHTML = html + '</table>';
}

function renderFigures(data){
    const paint=[], lag=[], rec=[], ratios=[], start=[];

    data.forEach(r=>{
        if (r.paintTime && r.lagTime) {
            paint.push(r.paintTime);
            lag.push(r.lagTime);
            rec.push(r.recommendedLag);
            ratios.push(r.lagToPaintRatio);
        }
        if (r.timeStart) start.push(r.timeStart);
    });

    Plotly.newPlot('convexHullFig', [
        {x:paint,y:lag,mode:'markers',name:'Actual'},
        {x:paint,y:rec,mode:'lines',name:'Recommended'}
    ], {title:'Paint vs Lag Time'});

    Plotly.newPlot('lagRatioFig', [
        {x:ratios.filter(v=>v), type:'histogram'}
    ], {title:'Lag / Paint Ratio'});

    Plotly.newPlot('timeDistributionFig', [
        {x:start, type:'histogram'}
    ], {title:'Start Time Distribution'});
}
