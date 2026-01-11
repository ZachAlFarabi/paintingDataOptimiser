const inputLine = document.getElementById('inputLine');
const recordsTable = document.getElementById('recordsTable');
const exportBtn = document.getElementById('exportBtn');

inputLine.addEventListener('keypress', function(e){
    if(e.key === 'Enter'){
        e.preventDefault();
        const line = inputLine.value;
        fetch('/addLine',{
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({line})
        })
        .then(r => r.json())
        .then(data => {
            if(data.status === 'ok'){
                renderTable(data.table);
                renderFigures(data.table);
            }
            inputLine.value = ''; // <-- clear input after submit
        });
    }
});

exportBtn.addEventListener('click', function(){
    window.location = '/exportExcel';
});

function renderTable(tableData){
    if(!tableData || tableData.length === 0) {
        recordsTable.innerHTML = '<i>No records</i>';
        return;
    }
    let columns = ['paintRecord','ts','process','date','operator','timeInBooth','timeStart','timeEnd','paintTime','lagTime'];
    let html = '<table border="1"><tr>';
    columns.forEach(c => html += `<th>${c}</th>`);
    html += '</tr>';
    tableData.forEach(row => {
        html += '<tr>';
        columns.forEach(c => html += `<td>${row[c] !== null ? row[c] : ''}</td>`);
        html += '</tr>';
    });
    html += '</table>';
    recordsTable.innerHTML = html;
}

function renderFigures(tableData){
    let paint=[], lag=[], recommended=[], avoidable=[];
    tableData.forEach(r=>{
        if(r.paintTime && r.lagTime){
            paint.push(r.paintTime);
            lag.push(r.lagTime);
            recommended.push(r.recommendedLag || null);
            avoidable.push(r.avoidableLag || null);
        }
    });

    let traceActual = {x: paint, y: lag, mode:'markers', type:'scatter', name:'Actual'};
    let traceRec = {x: paint, y: recommended, mode:'lines', name:'Recommended'};
    Plotly.newPlot('convexHullFig', [traceActual, traceRec], {title:'Paint vs Lag Time', xaxis:{title:'Paint Time (h)'}, yaxis:{title:'Lag Time (h)'}});

    let ratios = tableData.map(r=>r.lagToPaintRatio).filter(v=>v!==null && !isNaN(v));
    Plotly.newPlot('lagRatioFig', [{x:ratios, type:'histogram'}], {title:'Lag / Paint Ratios', xaxis:{title:'Lag/Paint Ratio'}});

    let startTimes = tableData.map(r=>r.timeStart).filter(v=>v!==null && !isNaN(v));
    Plotly.newPlot('timeDistributionFig', [{x:startTimes, type:'histogram'}], {title:'Start Time Distribution', xaxis:{title:'Start Time (h)'}});
}
