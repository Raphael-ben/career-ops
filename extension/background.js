importScripts('haiku.js');

chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch(console.error);

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type !== 'askHaiku') return false;
  (async () => {
    const { anthropicKey } = await chrome.storage.local.get('anthropicKey');
    if (!anthropicKey) return { error: 'No API key set' };
    const { url, init } = globalThis.CareerOpsHaiku.buildHaikuRequest(msg.entry, anthropicKey);
    const res = await fetch(url, init);
    const body = await res.json().catch(() => ({}));
    if (res.status === 401) return { error: 'API key rejected' };
    if (!res.ok) return { error: `HTTP ${res.status}: ${body.error?.message ?? res.statusText}` };
    return globalThis.CareerOpsHaiku.parseHaikuResponse(body, msg.entry.options);
  })().then(sendResponse, (e) => sendResponse({ error: String(e?.message ?? e) }));
  return true;
});
