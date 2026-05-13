const BRIDGE = 'http://localhost:7823';

async function detectFields(tabId) {
  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      const inputs = document.querySelectorAll(
        'input:not([type=hidden]):not([type=submit]):not([type=button])' +
        ':not([type=reset]):not([type=file]):not([type=image]),' +
        'textarea'
      );
      const out = [];
      for (const f of inputs) {
        const rect = f.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) continue;
        let label = '';
        if (f.id) {
          const lbl = document.querySelector('label[for="' + CSS.escape(f.id) + '"]');
          if (lbl) label = lbl.innerText.trim();
        }
        if (!label) {
          const aid = f.getAttribute('aria-labelledby');
          label = f.getAttribute('aria-label') ||
                  (aid && document.getElementById(aid)?.innerText.trim()) ||
                  f.getAttribute('placeholder') ||
                  f.getAttribute('name') || '';
        }
        const uid = f.id || f.name || ('f' + out.length);
        out.push({
          id: uid, name: f.name || '',
          type: f.type || f.tagName.toLowerCase(),
          label: label.replace(/\s+/g, ' ').trim(),
          value: f.value, tag: f.tagName.toLowerCase()
        });
      }
      return out;
    }
  });
  return results[0]?.result || [];
}

async function injectFill(tabId, fields) {
  await chrome.scripting.executeScript({
    target: { tabId },
    func: (toFill) => {
      for (const { id, value } of toFill) {
        const el = document.getElementById(id) ||
                   document.querySelector('[name="' + CSS.escape(id) + '"]');
        if (!el) continue;
        if (el.type === 'checkbox') { if (!el.checked) el.click(); continue; }
        const proto = el.tagName === 'TEXTAREA'
          ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
        setter.call(el, value);
        el.dispatchEvent(new Event('input',  { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.dispatchEvent(new Event('blur',   { bubbles: true }));
      }
    },
    args: [fields]
  });
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

function renderFields(answered, tabId) {
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
        await injectFill(tabId, [{ id: f.id, value: ta.value }]);
        btn.textContent = '✓ Done';
        btn.disabled = true;
      };
      actions.appendChild(btn);
      row.appendChild(actions);
    } else {
      const note = document.createElement('div');
      note.className = 'field-note';
      note.textContent = '⚠ ' + (f.note || 'manual action needed');
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

  document.getElementById('fill-all').onclick = async () => {
    const toFill = [];
    document.querySelectorAll('.field-row[data-action="fill"]').forEach(row => {
      const ta = row.querySelector('textarea');
      if (ta) toFill.push({ id: row.dataset.id, value: ta.value });
    });
    await injectFill(tabId, toFill);
    document.querySelectorAll('.field-row[data-action="fill"] button').forEach(btn => {
      btn.textContent = '✓ Done';
      btn.disabled = true;
    });
  };
}

async function init() {
  const status = document.getElementById('status');
  const errorEl = document.getElementById('error');

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) { status.textContent = 'No active tab found.'; return; }

    status.textContent = 'Reading form fields…';
    const fields = await detectFields(tab.id);
    if (!fields || fields.length === 0) {
      status.textContent = 'No form fields detected on this page.';
      return;
    }

    status.textContent = `Generating answers for ${fields.length} fields…`;
    const response = await postBridge(tab.url, tab.title, fields);
    if (response.error) throw new Error(response.error);
    const fillCount = response.fields.filter(f => f.action === 'fill').length;
    status.textContent = `Ready — ${fillCount} fields to fill, ${response.fields.length - fillCount} manual.`;
    renderFields(response.fields, tab.id);
  } catch (err) {
    status.textContent = 'Error';
    errorEl.textContent =
      (err.message.includes('fetch') || err.message.includes('NetworkError') || err.message.includes('Failed to fetch'))
        ? 'Bridge server not reachable — run `/jobhunter apply` in Claude Code first.'
        : err.message;
  }
}

document.addEventListener('DOMContentLoaded', init);
