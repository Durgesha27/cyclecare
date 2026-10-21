/* Interactive monthly calendar backed by /api/calendar. */
(function () {
  const grid = document.getElementById('cal-grid'), title = document.getElementById('cal-title');
  const detail = document.getElementById('cal-detail'), errBox = document.getElementById('cal-error');
  const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  const pad = n => String(n).padStart(2, '0');
  const [ty, tm] = document.body.dataset.today.split('-').map(Number);
  let year = ty, month = tm, data = null, selected = null;

  const el = (tag, text, cls) => { const e = document.createElement(tag); if (text) e.textContent = text; if (cls) e.className = cls; return e; };
  const iso = d => year + '-' + pad(month) + '-' + pad(d);

  async function load() {
    errBox.classList.add('hidden');
    const res = await CC.api('GET', '/api/calendar?year=' + year + '&month=' + month);
    if (!res.ok) { errBox.textContent = (res.data && res.data.error) || 'Could not load the calendar.'; errBox.classList.remove('hidden'); return; }
    data = res.data; render();
  }

  function render() {
    title.textContent = MONTHS[month - 1] + ' ' + year;
    grid.replaceChildren();
    const firstDow = new Date(year, month - 1, 1).getDay();
    const days = new Date(year, month, 0).getDate();   // handles leap years
    const periodDays = new Set(), predicted = new Set(data.predicted), sym = new Set(data.symptom_dates);
    data.periods.forEach(p => p.days.forEach(d => periodDays.add(d)));
    for (let i = 0; i < firstDow; i++) grid.appendChild(el('span', '', 'cal-cell blank'));
    for (let d = 1; d <= days; d++) {
      const date = iso(d), b = el('button', String(d), 'cal-cell');
      b.type = 'button'; b.dataset.date = date;
      const labels = [new Date(year, month - 1, d).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })];
      if (periodDays.has(date)) { b.classList.add('period'); labels.push('recorded period'); }
      else if (predicted.has(date)) { b.classList.add('predicted'); labels.push('estimated period, not confirmed'); }
      if (sym.has(date)) { b.classList.add('symptom'); labels.push('check-in logged'); }
      if (date === data.today) { b.classList.add('today'); labels.push('today'); }
      b.setAttribute('aria-label', labels.join(', '));
      b.setAttribute('aria-pressed', String(date === selected));
      b.addEventListener('click', () => { selected = date; render(); showDetail(date); });
      grid.appendChild(b);
    }
  }

  function showDetail(date) {
    detail.replaceChildren(el('h2', new Date(date + 'T00:00:00').toLocaleDateString(undefined, { dateStyle: 'full' })));
    const recs = data.periods.filter(p => p.days.includes(date));
    recs.forEach(p => {
      const box = el('div', '', 'detail-item');
      box.appendChild(el('strong', 'Recorded period'));
      box.appendChild(el('p', p.start_date + (p.end_date ? ' → ' + p.end_date : ' → ongoing / end not recorded'), 'small'));
      if (p.notes) box.appendChild(el('p', p.notes, 'small'));
      const a = el('a', 'Edit', 'btn btn-secondary btn-sm'); a.href = '/log-period?id=' + p.id;
      const del = el('button', 'Delete', 'btn btn-danger btn-sm'); del.type = 'button';
      del.addEventListener('click', async () => {
        if (!window.confirm('Delete this period record? This cannot be undone.')) return;
        const r = await CC.api('DELETE', '/api/periods/' + p.id);
        if (r.ok) { CC.toast('Period deleted.'); await load(); showDetail(date); }
        else CC.toast((r.data && r.data.error) || 'Could not delete.', 'error');
      });
      const row = el('div', '', 'actions'); row.append(a, del); box.appendChild(row); detail.appendChild(box);
    });
    if (!recs.length && data.predicted.includes(date))
      detail.appendChild(el('p', 'Estimated period day. This is a prediction based on your history, not a confirmed record.', 'alert alert-warning'));
    if (!recs.length && !data.predicted.includes(date)) detail.appendChild(el('p', 'No period recorded on this date.', 'muted'));
    if (data.symptom_dates.includes(date)) detail.appendChild(el('p', 'A check-in is logged for this day.', 'small'));
    const row = el('div', '', 'actions');
    if (date <= data.today) {
      const add = el('a', 'Add period starting here', 'btn btn-primary btn-sm'); add.href = '/log-period?date=' + date; row.appendChild(add);
      const chk = el('a', 'Daily check-in', 'btn btn-secondary btn-sm'); chk.href = '/symptoms?date=' + date; row.appendChild(chk);
    } else row.appendChild(el('p', 'Future dates can only be estimated, not recorded.', 'muted small'));
    detail.appendChild(row);
  }

  const shift = n => { month += n; if (month < 1) { month = 12; year--; } if (month > 12) { month = 1; year++; } selected = null; load(); };
  document.getElementById('cal-prev').addEventListener('click', () => shift(-1));
  document.getElementById('cal-next').addEventListener('click', () => shift(1));
  document.getElementById('cal-today').addEventListener('click', () => { year = ty; month = tm; selected = null; load(); });
  load();
})();
