/* Log/edit period form and delete buttons (history + edit page). */
(function () {
  const form = document.getElementById('period-form');
  const banner = document.getElementById('form-error');
  if (form) {
    const today = document.body.dataset.today;
    const maxDays = parseInt(form.dataset.maxDays, 10) || 15;
    const start = form.elements.start_date, end = form.elements.end_date;
    const clientErrors = () => {
      const errors = {};
      if (!start.value) errors.start_date = 'Start date is required.';
      else if (start.value > today) errors.start_date = "Start date can't be in the future.";
      if (end.value) {
        if (start.value && end.value < start.value) errors.end_date = "End date can't be before the start date.";
        else if (end.value > today) errors.end_date = "End date can't be in the future. Leave it blank if ongoing.";
        else if (start.value && (new Date(end.value) - new Date(start.value)) / 864e5 + 1 > maxDays)
          errors.end_date = 'A period can be at most ' + maxDays + ' days. Please check the dates.';
      }
      return errors;
    };
    form.addEventListener('submit', async e => {
      e.preventDefault();
      const errors = clientErrors();
      if (Object.keys(errors).length) { CC.showErrors(form, { status: 422, data: { errors } }, banner); return; }
      const btn = document.getElementById('save-btn');
      btn.disabled = true; btn.textContent = 'Saving…';
      const id = form.dataset.id;
      const res = await CC.api(id ? 'PUT' : 'POST', id ? '/api/periods/' + id : '/api/periods', {
        start_date: start.value, end_date: end.value || null, notes: form.elements.notes.value,
      });
      if (res.ok) { window.location.href = '/dashboard?notice=period_saved'; return; }
      btn.disabled = false; btn.textContent = 'Save Period';
      CC.showErrors(form, res, banner);
    });
  }
  document.querySelectorAll('[data-delete-period]').forEach(btn => btn.addEventListener('click', async () => {
    if (!window.confirm('Delete this period record? This cannot be undone.')) return;
    const res = await CC.api('DELETE', '/api/periods/' + btn.dataset.deletePeriod);
    if (res.ok) window.location.href = (btn.dataset.redirect || window.location.pathname) + '?notice=period_deleted';
    else CC.toast((res.data && res.data.error) || 'Could not delete.', 'error');
  }));
})();
