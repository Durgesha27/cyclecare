/* Shared helpers: CSRF-aware fetch, toasts, nav toggle, confirmations. */
(function () {
  const meta = document.querySelector('meta[name="csrf-token"]');
  window.CC = {
    token: () => (meta ? meta.content : ''),
    async api(method, url, body) {
      try {
        const res = await fetch(url, {
          method, credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': window.CC.token() },
          body: body === undefined ? undefined : JSON.stringify(body),
        });
        let data = {};
        try { data = await res.json(); } catch (e) { /* non-JSON */ }
        if (res.status === 401) { window.location.href = '/login'; }
        return { ok: res.ok, status: res.status, data };
      } catch (e) {
        return { ok: false, status: 0, data: { error: 'Network problem. Check your connection and try again.' } };
      }
    },
    toast(msg, kind) {
      const t = document.getElementById('toast');
      if (!t) return;
      t.textContent = msg;
      t.className = 'alert alert-' + (kind || 'success');
    },
    showErrors(form, result, banner) {
      form.querySelectorAll('.field-error[data-for]').forEach(p => { p.hidden = true; p.textContent = ''; });
      form.querySelectorAll('[aria-invalid]').forEach(i => i.removeAttribute('aria-invalid'));
      const errs = (result.data && result.data.errors) || {};
      let shown = false;
      Object.keys(errs).forEach(k => {
        const p = form.querySelector('.field-error[data-for="' + k + '"]');
        const input = form.querySelector('[name="' + k + '"]');
        if (p) { p.textContent = errs[k]; p.hidden = false; shown = true; }
        if (input) input.setAttribute('aria-invalid', 'true');
      });
      if (banner) {
        const msg = (result.data && result.data.error) || 'Something went wrong.';
        banner.textContent = msg; banner.classList.remove('hidden');
        if (shown && errs.form === undefined && result.status === 422) banner.classList.add('hidden');
      }
    },
  };
  const toggle = document.querySelector('.nav-toggle');
  if (toggle) toggle.addEventListener('click', () => {
    const nav = document.getElementById('main-nav');
    const open = nav.classList.toggle('open');
    toggle.setAttribute('aria-expanded', String(open));
  });
  document.querySelectorAll('form[data-confirm]').forEach(f =>
    f.addEventListener('submit', e => { if (!window.confirm(f.dataset.confirm)) e.preventDefault(); }));
  const signup = document.querySelector('[data-signup-form]');
  if (signup) signup.addEventListener('submit', e => {
    const a = signup.querySelector('#password'), b = signup.querySelector('#confirm_password');
    const err = document.getElementById('e-pw2');
    if (a.value !== b.value) { e.preventDefault(); err.textContent = 'Passwords do not match.'; err.hidden = false; b.focus(); }
  });
})();
