document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.js-complete');
  if (btn) {
    const id = btn.dataset.id;
    const res = await fetch(`/lesson/${id}/complete`, {method:'POST'});
    if (res.ok) { btn.textContent = 'Пройдено ✓'; btn.disabled = true; }
  }
});
