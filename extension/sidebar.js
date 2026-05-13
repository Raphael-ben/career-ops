const BRIDGE = 'http://localhost:7823';
const processedIds = new Set();
let currentTab = null;
let isProcessing = false;
let bridgeError = false;

// --- Page interaction ---

async function detectPageElements(tabId) {
  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      const out = [];

      // Form inputs + textareas
      const inputs = document.querySelectorAll(
        'input:not([type=hidden]):not([type=submit]):not([type=button])' +
        ':not([type=reset]):not([type=file]):not([type=image]),textarea'
      );
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

      // "Add another" type action buttons
      const btns = document.querySelectorAll(
        'button:not([disabled]),[role="button"]:not([aria-disabled="true"])'
      );
      for (const btn of btns) {
        const rect = btn.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) continue;
        const text = (btn.innerText || btn.textContent || btn.getAttribute('aria-label') || '')
          .trim().replace(/\s+/g, ' ');
        if (!text || text.length > 80) continue;
        if (!/\badd\b|another|\+\s*$/i.test(text)) continue;
        out.push({
          id: 'btn::' + text,
          label: text,
          type: 'action_button',
          tag: 'button',
          name: '',
          value: ''
        });
      }

      return out;
    }
  });
  return results[0]?.result || [];
}

async function injectFill(tabId, fields) {
  if (!fields.length) return;
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

async function clickButtons(tabId, labels) {
  if (!labels.length) return;
  await chrome.scripting.executeScript({
    target: { tabId },
    func: (labelsToClick) => {
      for (const label of labelsToClick) {
        const all = document.querySelectorAll(
          'button:not([disabled]),[role="button"]:not([aria-disabled="true"])'
        );
        for (const btn of all) {
          const text = (btn.innerText || btn.textContent || btn.getAttribute('aria-label') || '')
            .trim().replace(/\s+/g, ' ');
          if (text === label) { btn.click(); break; }
        }
      }
    },
    args: [labels]
  });
}

// --- Bridge ---

async function postBridge(url, title, fields) {
  const res = await fetch(`${BRIDGE}/fill`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, title, fields })
  });
  if (!res.ok) throw new Error(`Bridge HTTP ${res.status}`);
  return res.json();
}

// --- UI ---

function setStatus(text) {
  document.getElementById('status').textContent = text;
}

function renderManualItems(items) {
  const container = document.getElementById('fields');
  container.innerHTML = '';
  for (const f of items) {
    const row = document.createElement('div');
    row.className = 'field-row';
    const lbl = document.createElement('div');
    lbl.className = 'field-label';
    lbl.textContent = f.label || f.id;
    row.appendChild(lbl);
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
    container.appendChild(row);
  }
}

// --- Core loop ---

async function processNewElements() {
  if (isProcessing || bridgeError) return;

  // Refresh tab each cycle — catches SPA navigation
  let tab;
  try {
    [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  } catch { return; }
  if (!tab) return;

  // URL changed → new page, reset state
  if (currentTab && tab.url !== currentTab.url) {
    processedIds.clear();
    document.getElementById('fields').innerHTML = '';
  }
  currentTab = tab;

  let all;
  try {
    all = await detectPageElements(tab.id);
  } catch { return; }

  const newFields = all.filter(f => !processedIds.has(f.id));
  if (!newFields.length) return;

  isProcessing = true;
  setStatus(`${newFields.length} new element${newFields.length > 1 ? 's' : ''} — generating…`);

  try {
    const response = await postBridge(tab.url, tab.title, newFields);
    if (response.error) throw new Error(response.error);

    const toFill  = response.fields.filter(f => f.action === 'fill');
    const toClick = response.fields.filter(f => f.action === 'click');
    const toSkip  = response.fields.filter(f => f.action === 'skip');

    // Fill and skip items are done — mark processed
    // Click items (buttons) stay un-processed so Claude re-evaluates each cycle
    toFill.forEach(f => processedIds.add(f.id));
    toSkip.forEach(f => processedIds.add(f.id));

    if (toFill.length) {
      await injectFill(tab.id, toFill.map(f => ({ id: f.id, value: f.answer })));
    }

    if (toClick.length) {
      await new Promise(r => setTimeout(r, 400));
      await clickButtons(tab.id, toClick.map(f => f.label));
    }

    renderManualItems(toSkip);

    const parts = [];
    if (toFill.length)  parts.push(`filled ${toFill.length}`);
    if (toClick.length) parts.push(`clicked ${toClick.length} btn`);
    if (toSkip.length)  parts.push(`${toSkip.length} manual`);
    setStatus(parts.length ? parts.join(' · ') : 'watching…');

  } catch (err) {
    const msg = err.message || '';
    if (msg.includes('fetch') || msg.includes('NetworkError') || msg.includes('Failed to fetch')) {
      bridgeError = true;
      setStatus('Bridge not reachable');
      document.getElementById('error').textContent =
        'Run `/jobhunter apply` in Claude Code first, then reopen this panel.';
    } else {
      setStatus('Error: ' + msg);
    }
  }

  isProcessing = false;
}

async function init() {
  document.getElementById('fill-all-wrap').style.display = 'none';
  setStatus('Scanning…');
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) { setStatus('No active tab.'); return; }
    currentTab = tab;
    await processNewElements();
    setInterval(processNewElements, 1500);
  } catch (err) {
    setStatus('Init error: ' + err.message);
  }
}

document.addEventListener('DOMContentLoaded', init);
