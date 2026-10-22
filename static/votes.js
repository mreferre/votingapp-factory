// The /votes page votes through the existing public APIs: GET /api/<restaurant>
// returns the new count after a vote and GET /api/getvotes returns every count,
// so the page can update in place without a full reload.
(() => {
  const grid = document.querySelector('[data-votes-grid]');
  const status = document.querySelector('[data-status]');
  const refreshButton = document.querySelector('[data-refresh]');
  if (!grid || !status) return;

  const showStatus = (message) => {
    status.textContent = message;
    status.hidden = !message;
  };

  const setCount = (restaurant, count) => {
    const target = grid.querySelector(`[data-count="${restaurant}"]`);
    if (target) target.textContent = count;
  };

  grid.addEventListener('click', async (event) => {
    const button = event.target.closest('button[data-restaurant]');
    if (!button) return;
    button.disabled = true;
    try {
      const response = await fetch(`/api/${button.dataset.restaurant}`);
      if (!response.ok) throw new Error(`vote failed with status ${response.status}`);
      setCount(button.dataset.restaurant, await response.text());
      showStatus('');
    } catch {
      showStatus('Your vote could not be recorded. Please try again.');
    } finally {
      button.disabled = false;
    }
  });

  if (refreshButton) {
    refreshButton.addEventListener('click', async () => {
      try {
        const response = await fetch('/api/getvotes');
        if (!response.ok) throw new Error(`refresh failed with status ${response.status}`);
        for (const { name, value } of await response.json()) {
          setCount(name, value);
        }
        showStatus('');
      } catch {
        showStatus('The counts could not be refreshed. Please try again.');
      }
    });
  }
})();
