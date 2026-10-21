/* Daily check-in form: create, edit, delete. */
(function () {
  const form = document.getElementById('symptom-form');
  if (!form) return;
  const banner = document.getElementById('form-error');
  const title = document.querySelector('[data-form-title]');
  const cancel = document.getElementById('cancel-edit');
  let editId = null;
  const today = document.body.dataset.today;
  const reset = () => {
    editId = null; form.reset(); form.elements.date.value = today;
    title.textContent = 'New check-in'; cancel.classList.add('hidden'); banner.classList.add('hidden');
  };
  cancel.addEventListener('click', reset);
  document.querySelectorAll('[data-edit-symptom]').forEach(b => b.addEventListener('click', () => {
    const e = JSON.parse(b.dataset.editSymptom);
    editId = e.id; title.textContent = 'Edit check-in for ' + e.date;
    form.elements.date.value = e.date; form.elements.mood.value = e.mood || '';
    form.elements.severity.value = e.severity || ''; form.elements.notes.value = e.notes || '';
    form.querySelectorAll('input[name="symptoms"]').forEach(c => { c.checked = e.symptoms.includes(c.value); });
    cancel.classList.remove('hidden'); form.scrollIntoView({ behavior: 'smooth', block: 'start' });
    form.elements.date.focus();
  }));
  form.addEventListener('submit', async ev => {
    ev.preventDefault();
    if (form.elements.date.value > today) {
      CC.showErrors(form, { status: 422, data: { errors: { date: "Date can't be in the future." } } }, banner); return;
    }
    const body = {
      date: form.elements.date.value, mood: form.elements.mood.value || null,
      symptoms: Array.from(form.querySelectorAll('input[name="symptoms"]:checked')).map(c => c.value),
      severity: form.elements.severity.value || null, notes: form.elements.notes.value,
    };
    const res = await CC.api(editId ? 'PUT' : 'POST', editId ? '/api/symptoms/' + editId : '/api/symptoms', body);
    if (res.ok) { window.location.href = '/symptoms?notice=symptom_saved'; return; }
    CC.showErrors(form, res, banner);
  });
  document.querySelectorAll('[data-delete-symptom]').forEach(b => b.addEventListener('click', async () => {
    if (!window.confirm('Delete this check-in? This cannot be undone.')) return;
    const res = await CC.api('DELETE', '/api/symptoms/' + b.dataset.deleteSymptom);
    if (res.ok) window.location.href = '/symptoms?notice=symptom_deleted';
    else CC.toast((res.data && res.data.error) || 'Could not delete.', 'error');
  }));
  if (new URLSearchParams(location.search).get('date')) form.elements.date.focus();
})();
