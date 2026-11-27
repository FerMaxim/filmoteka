const target = document.querySelector('#external-results');
if (target) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(target.dataset.source, {credentials: 'same-origin', signal: controller.signal});
    if (!response.ok || response.redirected) throw new Error('Unavailable');
    target.innerHTML = await response.text();
  } catch {
    target.textContent = 'Внешний поиск временно недоступен. Локальные произведения доступны.';
  } finally { clearTimeout(timer); }
}
document.addEventListener('error', event => {
  if (event.target.matches?.('.catalog-poster img')) event.target.hidden = true;
}, true);
