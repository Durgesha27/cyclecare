/* Draw charts from /api/insights when Chart.js is available; tables remain as the fallback. */
(async function () {
  const c1 = document.getElementById('cycle-chart'), c2 = document.getElementById('duration-chart');
  if (!window.Chart || (!c1 && !c2)) return;
  const res = await CC.api('GET', '/api/insights');
  if (!res.ok) return;
  const opts = (label) => ({ responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: { y: { beginAtZero: true, title: { display: true, text: label } } } });
  if (c1) new Chart(c1, { type: 'bar', data: {
    labels: res.data.cycle_lengths.map(i => i.to_date),
    datasets: [{ data: res.data.cycle_lengths.map(i => i.days),
      backgroundColor: res.data.cycle_lengths.map(i => i.valid ? '#E8A8B8' : '#DCD6F7') }] }, options: opts('Days between starts') });
  if (c2) new Chart(c2, { type: 'bar', data: {
    labels: res.data.durations.map(d => d.start_date),
    datasets: [{ data: res.data.durations.map(d => d.days), backgroundColor: '#C9DCCB' }] }, options: opts('Days') });
})();
