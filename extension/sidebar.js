const BRIDGE = 'http://localhost:7823';

async function getTabId() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab ? tab.id : null;
}

async function sendToContent(tabId, message) {
  return new Promise(resolve =>
    chrome.tabs.sendMessage(tabId, message, resolve)
  );
}

async function postBridge(url, title, fields) {
  const res = await fetch(`${BRIDGE}/fill`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, title, fields })
  });
  if (!res.ok) throw new Error(`Bridge HTTP ${res.status}`);
  return res.json();
}

function renderFields(answered) {
  const container = document.getElementById('fields');
  container.innerHTML = '';

  for (const f of answered) {
    const row = document.createElement('div');
    row.className = 'field-row';
    row.dataset.id = f.id;
    row.dataset.action = f.action;

    const lbl = document.createElement('div');
    lbl.className = 'field-label';
    lbl.textContent = f.label || f.id;
    row.appendChild(lbl);

    if (f.action === 'fill') {
      const ta = document.createElement('textarea');
      ta.className = 'field-answer';
      ta.rows = (f.answer || '').length > 100 ? 4 : 1;
      ta.value = f.answer || '';
      row.appendChild(ta);

      const actions = document.createElement('div');
      actions.className = 'field-actions';
      const btn = document.createElement('button');
      btn.textContent = 'Fill';
      btn.onclick = async () => {
        const tabId = await getTabId();
        await sendToContent(tabId, { action: 'fill', fields: [{ id: f.id, value: ta.value }] });
        btn.textContent = '✓ Done';
        btn.disabled = true;
      };
      actions.appendChild(btn);
      row.appendChild(actions);
    } else {
      const note = document.createElement('div');
      note.className = 'field-note';
      note.textContent = `⚠ ${f.note || 'manual action needed'}`;
      row.appendChild(note);
      if (f.answer) {
        const hint = document.createElement('div');
        hint.className = 'field-hint';
        hint.textContent = f.answer;
        row.appendChild(hint);
      }
    }

    container.appendChild(row);
  }

  document.getElementById('fill-all-wrap').style.display = 'block';
}

document.getElementById('fill-all').addEventListener('click', async () => {
  const tabId = await getTabId();
  const toFill = [];
  document.querySelectorAll('.field-row[data-action="fill"]').forEach(row => {
    const ta = row.querySelector('textarea');
    if (ta) toFill.push({ id: row.dataset.id, value: ta.value });
  });
  await sendToContent(tabId, { action: 'fill', fields: toFill });
  document.querySelectorAll('.field-row[data-action="fill"] button').forEach(btn => {
    btn.textContent = '✓ Done';
    btn.disabled = true;
  });
});

async function init() {
  const status = document.getElementById('status');
  const errorEl = document.getElementById('error');

  const tabId = await getTabId();
  if (!tabId) { status.textContent = 'No active tab found.'; return; }

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  status.textContent = 'Reading form fields…';
  const { fields } = await sendToContent(tabId, { action: 'getFields' });
  if (!fields || fields.length === 0) {
    status.textContent = 'No form fields detected on this page.';
    return;
  }

  status.textContent = `Generating answers for ${fields.length} fields…`;
  try {
    const response = await postBridge(tab.url, tab.title, fields);
    if (response.error) throw new Error(response.error);
    const fillCount = response.fields.filter(f => f.action === 'fill').length;
    status.textContent = `Ready — ${fillCount} fields to fill, ${response.fields.length - fillCount} manual.`;
    renderFields(response.fields);
  } catch (err) {
    status.textContent = 'Connection error';
    errorEl.textContent = err.message.includes('fetch') || err.message.includes('NetworkError')
      ? 'Bridge server not reachable — run `/jobhunter apply` in Claude Code first.'
      : err.message;
  }
}

document.addEventListener('DOMContentLoaded', init);
