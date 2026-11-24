(() => {
  const dataNode = document.getElementById('compute-chart-data');
  if (!dataNode || !window.Plotly) return;
  const data = JSON.parse(dataNode.textContent);
  const metric = document.getElementById('compute-metric');
  const escapeText = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const layout = () => ({...(window.dashboardTheme?.plotlyLayout() || {}), paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
    height: 585, margin: {l: 65, r: 20, t: 25, b: 75},
    legend: {orientation: 'v', x: 1.02, y: 1, maxheight: 0.8}, autosize: true});
  const displayName = item => `${item.name} · ${item.group}${item.key.startsWith('pod:') ? ` · ${item.key.slice(-8)}` : ''}`;
  const config = {responsive: true, displaylogo: false};
  const monthly = document.getElementById('compute-month-chart');
  if (monthly) {
    const grouping = document.getElementById('compute-grouping');
    let selected = null;
    const renderMonth = async () => {
      const rows = data.rows;
      document.getElementById('compute-month-empty').hidden = rows.length > 0;
      const groups = new Map();
      for (const row of rows) {
        const id = grouping.value === 'group' ? JSON.stringify([row.group]) : JSON.stringify([row.namespace, row.group, row.key]);
        const label = grouping.value === 'group' ? row.group : displayName(row);
        if (!groups.has(id)) groups.set(id, {name: escapeText(label), dates: new Map()});
        const values = groups.get(id).dates;
        const prev = values.get(row.day) || {value: 0, url: row.url};
        prev.value += row[metric.value] || 0;
        values.set(row.day, prev);
      }
      const traces = [...groups.values()].map((group, index) => {
        const entries = [...group.dates.entries()].sort((a, b) => a[0].localeCompare(b[0]));
        return {type: 'bar', name: group.name, visible: selected === null || selected === index ? true : 'legendonly', x: entries.map(e => e[0]), y: entries.map(e => e[1].value),
          customdata: entries.map(e => e[1].url), hovertemplate: '%{x}<br>%{y:.4f}<extra>%{fullData.name}</extra>'};
      });
      const label = {cpu: 'CPU core-hours', memory: 'RAM GiB-hours', cost: `Estimated cost (${data.currency})`}[metric.value];
      await Plotly.react(monthly, traces, {...layout(), barmode: 'stack', xaxis: {title: 'Day'}, yaxis: {title: label, rangemode: 'tozero'}}, config);
      monthly.removeAllListeners('plotly_click');
      monthly.on('plotly_click', event => {
        const url = event.points?.[0]?.customdata;
        if (typeof url === 'string' && /^\/compute\/day\/\d{4}-\d{2}-\d{2}\/$/.test(url)) window.location.assign(url);
      });
      monthly.removeAllListeners('plotly_legendclick');
      monthly.on('plotly_legendclick', event => {
        selected = selected === event.curveNumber ? null : event.curveNumber;
        renderMonth();
        return false;
      });
      monthly.removeAllListeners('plotly_legenddoubleclick');
      monthly.on('plotly_legenddoubleclick', () => false);
    };
    metric.addEventListener('change', renderMonth);
    grouping.addEventListener('change', () => { selected = null; renderMonth(); });
    renderMonth();
  }
  const daily = document.getElementById('compute-day-chart');
  if (daily) {
    const fmt = new Intl.DateTimeFormat('en-GB', {timeZone: data.timezone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23'});
    const hoverTimes = data.times.map(t => fmt.format(new Date(t)) + ' Stockholm');
    const tickvals = data.times.filter((_, i) => i % 180 === 0);
    let selected = null;
    const renderDay = async () => {
      document.getElementById('compute-day-empty').hidden = data.series.length > 0;
      const sums = data.times.map(() => 0);
      let visibleCount = 0;
      const traces = data.series.map((item, index) => {
        const values = item[metric.value];
        const visible = selected === null || selected === index;
        const fill = visible && visibleCount++ ? 'tonexty' : 'tozeroy';
        const cumulative = values.map((v, i) => {
          if (v === null) return null;
          if (visible) sums[i] += v;
          return sums[i];
        });
        return {type: 'scatter', mode: 'lines', name: escapeText(displayName(item)), visible: visible ? true : 'legendonly',
          x: data.times, y: cumulative, customdata: values.map((v, i) => [v, hoverTimes[i]]),
          fill, connectgaps: false,
          hovertemplate: '%{customdata[1]}<br>%{customdata[0]:.4f}<extra>%{fullData.name}</extra>'};
      });
      await Plotly.react(daily, traces, {...layout(), xaxis: {title: 'Time (Europe/Stockholm)', tickmode: 'array', tickvals,
        ticktext: tickvals.map(t => fmt.format(new Date(t)))}, yaxis: {title: metric.value === 'cpu' ? 'CPU cores' : 'RAM GiB', rangemode: 'tozero'}}, config);
      daily.removeAllListeners('plotly_legendclick');
      daily.on('plotly_legendclick', event => {
        selected = selected === event.curveNumber ? null : event.curveNumber;
        renderDay();
        return false;
      });
      daily.removeAllListeners('plotly_legenddoubleclick');
      daily.on('plotly_legenddoubleclick', () => false);
    };
    metric.addEventListener('change', renderDay);
    renderDay();
  }
})();
