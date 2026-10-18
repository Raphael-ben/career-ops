const $ = (id) => document.getElementById(id);
const W = globalThis.CareerOpsWorkday;
let pkg = null; // { data, files }
let hasKey = false;

const warn = (msg) => { $('warn').textContent = msg || ''; };

const toBase64 = (file) => new Promise((resolve, reject) => {
  const r = new FileReader();
  r.onload = () => resolve(String(r.result).split(',')[1] || '');
  r.onerror = () => reject(r.error);
  r.readAsDataURL(file);
});

async function loadFolder(fileList) {
  const all = [...fileList];
  const apply = all.find((f) => f.name === 'apply.json');
  if (!apply) throw new Error('apply.json not found — run: node apply-data.mjs <folder>');
  const data = JSON.parse(await apply.text());
  if (data.schema !== 1) throw new Error(`Unsupported apply.json schema: ${data.schema}`);
  const files = [];
  for (const name of Object.values(data.files || {}).filter(Boolean)) {
    const f = all.find((x) => x.name === name);
    if (!f) throw new Error(`File named in apply.json is missing: ${name}`);
    files.push({ name: f.name, type: f.type || 'application/pdf', base64: await toBase64(f) });
  }
  return { data, files };
}

async function onPick(ev) {
  warn('');
  $('report').textContent = '';
  pkg = null;
  $('fill').disabled = true;
  $('pkg').textContent = '';
  try {
    pkg = await loadFolder(ev.target.files);
    const { job, generated } = pkg.data;
    $('pkg').textContent = `${job.company} — ${job.role} (generated ${generated})`;
    $('fill').disabled = false;
  } catch (e) {
    warn(e.message);
  }
}

async function fillStep() {
  warn('');
  $('report').textContent = '';
  const pkgLine = $('pkg').textContent;
  $('fill').disabled = true;
  $('pkg').textContent = 'Filling… (this can take a minute)';
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.url) throw new Error('No active tab');
    const host = new URL(tab.url).hostname;
    if (!W.companyMatchesHost(pkg.data.job.company, host)) {
      warn(`Warning: tab host ${host} does not look like ${pkg.data.job.company}. Continuing anyway.`);
    }
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ['ats/workday.js', 'fill/workday-fill.js'],
    });
    const [res] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: (data, files) => globalThis.CareerOpsFill.run(data, files),
      args: [pkg.data, pkg.files],
    });
    renderReport(res.result);
  } catch (e) {
    warn(`Fill failed: ${e.message}`);
  } finally {
    $('pkg').textContent = pkgLine;
    $('fill').disabled = false;
  }
}

function renderReport(report) {
  const root = $('report');
  root.textContent = '';
  const add = (text, hint) => {
    const d = document.createElement('div');
    d.className = 'item';
    d.textContent = text;
    if (hint) {
      const h = document.createElement('div');
      h.className = 'hint';
      h.textContent = hint;
      d.appendChild(h);
    }
    root.appendChild(d);
    return d;
  };
  if (report == null) { warn('Fill returned no report — check the page console'); return; }
  if (report.step === null) { add('Nothing to fill on this step.'); return; }
  add(`Filled ${report.filled.length} field(s) on ${report.step}.`);
  for (const s of report.skipped) add(`Skipped: ${s.field}`, `wanted: ${s.wanted} — ${s.reason}`);
  for (const u of report.unmatchedOptions) {
    const row = add(`No option match: ${u.label || u.field}`, `wanted: ${u.wanted}\noptions: ${u.options.join(' | ')}`);
    row.querySelector('.hint').style.whiteSpace = 'pre-wrap';
    if (!u.options.length) continue;
    const btn = document.createElement('button');
    btn.textContent = 'Ask Haiku';
    if (!hasKey) { btn.disabled = true; btn.title = 'Set an API key in Settings'; }
    btn.onclick = () => askHaiku(u, row);
    row.appendChild(btn);
  }
}

async function askHaiku(entry, row) {
  const btn = row.querySelector('button');
  btn.disabled = true;
  const note = (text) => {
    const d = document.createElement('div');
    d.className = 'hint';
    d.textContent = text;
    row.appendChild(d);
  };
  try {
    const res = await chrome.runtime.sendMessage({ type: 'askHaiku', entry });
    if (!res || res.error) { note(`Haiku error: ${res?.error || 'no response'}`); btn.disabled = false; return; }
    if (res.choice === null) { note(`Haiku: no fitting option — ${res.why}`); return; }
    if (W.pickOption(entry.options, res.choice) !== res.choice) {
      note(`Haiku answered "${res.choice}", not an exact option — ignored.`);
      return;
    }
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    btn.disabled = true; // keep disabled while applyOption runs
    const [out] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: (e, c) => globalThis.CareerOpsFill.applyOption(e, c),
      args: [entry, res.choice],
    });
    if (out.result?.ok) note(`chosen by Haiku: ${res.choice} — ${res.why}`);
    else { note(`Could not select "${res.choice}" on the page.`); btn.disabled = false; }
  } catch (e) {
    note(`Haiku failed: ${e.message}`);
    btn.disabled = false;
  }
}

async function refreshKey() {
  const { anthropicKey } = await chrome.storage.local.get('anthropicKey');
  hasKey = !!anthropicKey;
  $('apiKey').value = '';
  $('apiKey').placeholder = hasKey ? 'Key is set' : 'Not set';
}

$('folder').addEventListener('change', onPick);
$('pick').addEventListener('change', onPick);
$('fill').addEventListener('click', fillStep);
$('saveKey').addEventListener('click', async () => {
  const v = $('apiKey').value.trim();
  if (v) await chrome.storage.local.set({ anthropicKey: v });
  await refreshKey();
});
refreshKey();
