function getVisibleFields() {
  const fields = document.querySelectorAll(
    'input:not([type=hidden]):not([type=submit]):not([type=button])' +
    ':not([type=reset]):not([type=file]):not([type=image]),' +
    'textarea'
  );
  const result = [];
  for (const f of fields) {
    const rect = f.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) continue;
    let label = '';
    if (f.id) {
      const lbl = document.querySelector(`label[for="${CSS.escape(f.id)}"]`);
      if (lbl) label = lbl.innerText.trim();
    }
    if (!label) {
      label = f.getAttribute('aria-label') ||
              f.getAttribute('aria-labelledby') &&
                document.getElementById(f.getAttribute('aria-labelledby'))?.innerText.trim() ||
              f.getAttribute('placeholder') ||
              f.getAttribute('name') || '';
    }
    const uid = f.id || f.name || `f${result.length}`;
    result.push({
      id: uid,
      name: f.name || '',
      type: f.type || f.tagName.toLowerCase(),
      label: label.replace(/\s+/g, ' ').trim(),
      value: f.value,
      tag: f.tagName.toLowerCase()
    });
  }
  return result;
}

function fillField(id, value) {
  const el = document.getElementById(id) ||
             document.querySelector(`[name="${CSS.escape(id)}"]`);
  if (!el) return `NOT_FOUND:${id}`;
  if (el.type === 'checkbox') {
    if (!el.checked) el.click();
    return `CHECKED:${id}`;
  }
  const proto = el.tagName === 'TEXTAREA'
    ? HTMLTextAreaElement.prototype
    : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
  setter.call(el, value);
  el.dispatchEvent(new Event('input',  { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
  el.dispatchEvent(new Event('blur',   { bubbles: true }));
  return `OK:${id}`;
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.action === 'getFields') {
    sendResponse({ fields: getVisibleFields() });
  } else if (message.action === 'fill') {
    const results = (message.fields || []).map(f => fillField(f.id, f.value));
    sendResponse({ results });
  }
  return true;
});
