const q = document.getElementById('q');
const go = document.getElementById('go');
const err = document.getElementById('error');
const meta = document.getElementById('meta');
const fact = document.getElementById('fact');
const results = document.getElementById('results');

function esc(s) {
  return (s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function hostOf(u) {
  try { return new URL(u).hostname.replace(/^www\./, ''); } catch { return ''; }
}

async function search() {
  const query = q.value.trim();
  err.textContent = '';
  fact.hidden = true;
  meta.hidden = true;
  results.innerHTML = '';
  if (!query) { err.textContent = 'Type something to search first.'; return; }
  go.disabled = true;
  go.textContent = 'Searching…';
  try {
    const r = await fetch('/api/search?q=' + encodeURIComponent(query));
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || 'Search failed.');
    const counts = Object.entries(data.sources).map(([k, v]) => `${k}: ${v}`).join(' · ');
    meta.innerHTML = `<span>${data.results.length} results — ${esc(counts)}</span><a class="gbtn" href="${esc(data.google_url)}" target="_blank" rel="noopener">Open this search in Google ↗</a>`;
    meta.hidden = false;
    if (data.fact) {
      fact.innerHTML = `<div class="src">Wikipedia — quick fact</div><h2>${esc(data.fact.title)}</h2><p>${esc(data.fact.text)}</p><a href="${esc(data.fact.url)}" target="_blank" rel="noopener">Read the full article ↗</a>`;
      fact.hidden = false;
    }
    if (!data.results.length) {
      results.innerHTML = '<p class="hint">No results came back from any source. Try different words.</p>';
    } else {
      results.innerHTML = data.results.map(item => `
        <div class="result">
          <div class="rhead"><span class="src">${esc(item.source)}</span><span class="host">${esc(hostOf(item.url))}</span></div>
          <a class="rtitle" href="${esc(item.url)}" target="_blank" rel="noopener">${esc(item.title)}</a>
          <p class="rsnip">${esc(item.snippet)}</p>
        </div>`).join('');
    }
  } catch (e) {
    err.textContent = e.message || 'Search failed.';
  } finally {
    go.disabled = false;
    go.textContent = 'Search';
  }
}

go.addEventListener('click', search);
q.addEventListener('keydown', e => { if (e.key === 'Enter') search(); });
q.focus();
