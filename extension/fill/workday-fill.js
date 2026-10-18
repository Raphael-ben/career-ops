// SPIKE RESULTS: pending (engine built with per-primitive verify + fallback; see controller ledger)
//
// Workday in-page fill engine. Classic script, one IIFE, injected after ats/workday.js
// into the ISOLATED world by sidebar.js. Fills the current step only and returns a Report.
// It never clicks Next / Save and Continue / Submit and never deletes a block (safeClick guards).
//
// Add-button strategy: all Add / Add Another buttons share data-automation-id "add-button".
// A button belongs to a section when its aria-label + text matches map.<section>.addLabel,
// else when the nearest heading (h2-h4 / role=heading) BEFORE it in document order matches
// (section heading "Work Experience" / "Education", or block heading "Work Experience 3").
// clickAdd then proves it by the blockNumbers diff of that section's prefix.
(function () {
  const W = globalThis.CareerOpsWorkday;
  const M = W.map;
  const norm = (s) => String(s ?? '').trim().toLowerCase().replace(/\s+/g, ' ');
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const byId = (id) => document.getElementById(id);
  const visible = (el) => el.getClientRects().length > 0;
  const auto = (id) => `[data-automation-id="${id}"]`;
  const fire = (el, type) => el.dispatchEvent(new Event(type, { bubbles: true }));
  const key = (el, k, code = 0) => {
    for (const type of ['keydown', 'keyup']) {
      el.dispatchEvent(new KeyboardEvent(type, { key: k, code: k === 'Enter' ? 'Enter' : k === 'Escape' ? 'Escape' : '', keyCode: code, which: code, bubbles: true }));
    }
  };

  async function waitFor(pred, ms = 5000) {
    const end = Date.now() + ms;
    for (;;) {
      const v = pred();
      if (v) return v;
      if (Date.now() >= end) return null;
      await sleep(100);
    }
  }

  // Refuses anything that could leave the step or submit. Nothing here should ever hit it.
  const FORBIDDEN = /^(next|submit|save and continue|continue|apply|delete|remove)\b/i;
  function safeClick(el) {
    const a = el.getAttribute('data-automation-id') || '';
    const label = `${el.getAttribute('aria-label') || ''} ${el.textContent || ''}`.trim();
    if (M.never.includes(a) || a === M.upload.remove || (el.tagName === 'BUTTON' && FORBIDDEN.test(label))) {
      throw new Error(`refused to click "${label || a}"`);
    }
    el.click();
  }

  function nativeSet(el, v) {
    const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, v);
  }

  // Technique 1: native setter + input/change/blur. Technique 2: focus/select + execCommand.
  // Verified after a short settle so a React re-render that reverts the value is caught.
  // { blur: false } keeps focus (prompt inputs may clear unselected text on blur before Enter).
  async function setText(el, value, ok = (v) => norm(v) === norm(value), { blur = true } = {}) {
    const want = String(value);
    const leave = () => { if (blur) { el.dispatchEvent(new FocusEvent('blur', { bubbles: true })); el.blur(); } };
    el.focus();
    nativeSet(el, want);
    fire(el, 'input'); fire(el, 'change');
    leave();
    await sleep(150);
    if (ok(el.value)) return true;
    el.focus(); el.select();
    document.execCommand('insertText', false, want);
    leave();
    await sleep(150);
    return ok(el.value);
  }

  // Month typed as two digits; Workday reads "05" back as "5", hence Number() compare.
  async function setDate(monthEl, yearEl, month, year) {
    let ok = true;
    if (monthEl && month != null) ok = await setText(monthEl, String(month).padStart(2, '0'), (v) => Number(v) === month) && ok;
    if (yearEl && year != null) ok = await setText(yearEl, String(year), (v) => Number(v) === year) && ok;
    return ok;
  }

  async function setCheckbox(el, checked) {
    if (el.checked === checked) return true;
    safeClick(el);
    await sleep(150);
    if (el.checked !== checked) { el.checked = checked; fire(el, 'click'); fire(el, 'change'); await sleep(150); }
    return el.checked === checked;
  }

  const radioLabel = (r) => (r.labels?.[0]?.textContent || r.getAttribute('aria-label') || r.value || '').trim();
  const radios = (name) => [...document.querySelectorAll(`input[type="radio"][name="${name}"]`)];

  async function setRadio(name, labelText) {
    const r = radios(name).find((x) => norm(radioLabel(x)) === norm(labelText));
    if (!r) return false;
    if (r.checked) return true;
    safeClick(r);
    await sleep(150);
    if (!r.checked) { r.labels?.[0]?.click(); await sleep(150); }
    return r.checked;
  }

  // ---- listbox (button opening [role=option]s) ----
  const btnText = (b) => (b.textContent || '').trim();
  const isPlaceholder = (t) => t === '' || /^select\b/i.test(t); // ponytail: English placeholder only; other tenant languages report "page has"
  const listboxOf = (btn) => {
    const ctl = btn.getAttribute('aria-controls') && byId(btn.getAttribute('aria-controls'));
    return ctl || [...document.querySelectorAll('[role="listbox"]')].find(visible) || null;
  };
  function openOptions(btn) {
    const lb = btn.getAttribute('aria-controls') && byId(btn.getAttribute('aria-controls'));
    return [...(lb || document).querySelectorAll(M.listboxOption)].filter(visible);
  }
  const optText = (o) => (o.textContent || '').trim();
  async function closePopup(target = document.activeElement || document.body) {
    key(target, 'Escape', 27);
    await sleep(200);
  }

  async function selectListbox(buttonId, text) {
    const btn = byId(buttonId);
    if (!btn) return { ok: false, options: [] };
    if (norm(btnText(btn)) === norm(text)) return { ok: true, options: [] };
    // Keys go to the open listbox, else the button; never to an input (Enter there starts a search).
    const keyTarget = () => listboxOf(btn) || btn;
    const typeKeys = (s) => { for (const ch of s) key(keyTarget(), ch, ch.toUpperCase().charCodeAt(0)); };
    const open = async () => { btn.focus(); safeClick(btn); return (await waitFor(() => { const o = openOptions(btn); return o.length ? o : null; }, 3000)) || []; };
    let opts = await open();
    let hit = W.pickOption(opts.map(optText), text);
    if (!hit && opts.length) {
      // Virtualised list: type-ahead the first letters, then re-read.
      typeKeys(String(text).slice(0, 3));
      await sleep(400);
      opts = openOptions(btn);
      hit = W.pickOption(opts.map(optText), text);
    }
    const options = opts.map(optText);
    if (!hit) { await closePopup(keyTarget()); return { ok: false, options }; }
    safeClick(opts.find((o) => optText(o) === hit));
    if (await waitFor(() => norm(btnText(btn)) === norm(hit), 1500)) return { ok: true, options };
    // Fallback: reopen if closed, type the option letters + Enter.
    if (!openOptions(btn).length) await open();
    typeKeys(hit);
    key(keyTarget(), 'Enter', 13);
    const ok = !!(await waitFor(() => norm(btnText(btn)) === norm(hit), 1500));
    if (!ok) await closePopup(keyTarget());
    return { ok, options };
  }

  // ---- prompt search (type, Enter, pick promptOption, chip) ----
  const wrapperOf = (el) => el.closest('[data-automation-id^="formField-"]') || el.parentElement?.parentElement || el;
  const chips = (input) => [...wrapperOf(input).querySelectorAll(auto(M.prompt.chip))].map((c) => (c.textContent || '').trim());
  const promptOpts = () => [...document.querySelectorAll(auto(M.prompt.option))].filter(visible);

  // Resolves { opts } (result list), { chip } (Enter auto-selected a unique result) or null (text did not stick).
  async function search(input, query) {
    if (promptOpts().length) { await closePopup(); await waitFor(() => !promptOpts().length, 1000); }
    const before = chips(input);
    if (!(await setText(input, query, undefined, { blur: false }))) return null;
    input.focus();
    key(input, 'Enter', 13);
    return (await waitFor(() => {
      const o = promptOpts();
      if (o.length) return { opts: o };
      const fresh = chips(input).find((c) => !before.includes(c));
      return fresh ? { chip: fresh } : null;
    }, 4000)) || { opts: [] };
  }

  async function promptSelect(inputId, query, exact) {
    const input = byId(inputId);
    if (!input) return { ok: false, options: [] };
    if (chips(input).some((c) => norm(c) === norm(exact))) return { ok: true, options: [], already: true };
    const s = await search(input, query);
    if (s === null) return { ok: false, options: [] };
    // ponytail: a wrong auto-selected chip is reported (options = [chip]) but not removed; the user fixes it.
    if (s.chip) return { ok: norm(s.chip) === norm(exact), options: [s.chip] };
    let opts = s.opts;
    const hit = W.pickOption(opts.map(optText), exact);
    if (hit) {
      const el = opts.find((o) => optText(o) === hit);
      safeClick(el);
      let ok = !!(await waitFor(() => chips(input).some((c) => norm(c) === norm(hit)), 2000));
      if (!ok) {
        const radio = el.querySelector('input[type="radio"]') || el.querySelector('label');
        if (radio) { safeClick(radio); ok = !!(await waitFor(() => chips(input).some((c) => norm(c) === norm(hit)), 2000)); }
      }
      if (promptOpts().length) await closePopup();
      return { ok, options: opts.map(optText) };
    }
    if (!opts.length) {
      const shorter = W.shorterQuery(query);
      if (shorter !== query) {
        const s2 = await search(input, shorter);
        if (s2?.chip) return { ok: norm(s2.chip) === norm(exact), options: [s2.chip] };
        opts = s2?.opts || [];
      }
    }
    const options = opts.map(optText);
    await closePopup();
    await setText(input, '');
    return { ok: false, options };
  }

  // ---- uploads ----
  const deleteBtn = (name) => [...document.querySelectorAll(auto(M.upload.remove))].find((b) => b.getAttribute('aria-label') === `Delete ${name}`);
  function toFile({ name, type, base64 }) {
    const bin = atob(base64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new File([bytes], name, { type: type || 'application/pdf' });
  }
  const uploadInput = () => document.querySelector(`${auto(M.upload.zone)} input[type="file"]${auto(M.upload.input)}`);

  // Returns per file 'already' | 'uploaded' | 'failed'.
  async function upload(input, files) {
    const out = {};
    for (const f of files) {
      if (deleteBtn(f.name)) { out[f.name] = 'already'; continue; }
      const el = input?.isConnected ? input : uploadInput();
      if (!el) { out[f.name] = 'failed'; continue; }
      const dt = new DataTransfer();
      dt.items.add(toFile(f));
      el.files = dt.files;
      fire(el, 'input'); fire(el, 'change');
      out[f.name] = (await waitFor(() => deleteBtn(f.name), 15000)) ? 'uploaded' : 'failed';
    }
    return out;
  }

  // ---- add buttons ----
  const HEADINGS = 'h2, h3, h4, [role="heading"]';
  function headingBefore(el) {
    let last = '';
    for (const h of document.querySelectorAll(HEADINGS)) {
      if (h.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING) last = h.textContent || '';
      else break;
    }
    return last;
  }
  const allIds = () => [...document.querySelectorAll('[id]')].map((e) => e.id);

  async function clickAdd(section) {
    const cfg = M[section];
    const buttons = [...document.querySelectorAll(auto(M.addButton))].filter(visible);
    const btn = buttons.find((b) => cfg.addLabel.test(`${b.getAttribute('aria-label') || ''} ${b.textContent || ''}`))
      || buttons.find((b) => cfg.addLabel.test(headingBefore(b)));
    if (!btn) return null;
    const before = W.blockNumbers(allIds(), cfg.prefix);
    safeClick(btn);
    return waitFor(() => W.blockNumbers(allIds(), cfg.prefix).find((n) => !before.includes(n)) ?? null, 4000);
  }

  // ---- fill rules + report ----
  function newReport(step) { return { step, filled: [], skipped: [], unmatchedOptions: [], seen: new Set() }; }

  async function guard(r, field, wanted, fn) {
    try { await fn(); } catch (e) { r.skipped.push({ field, wanted: String(wanted ?? ''), reason: `error: ${e.message}` }); }
  }

  // Equal → leave; empty → fill; different → skipped `page has "<value>"`.
  async function ruleText(r, field, id, wanted) {
    if (wanted == null || wanted === '') return;
    const el = byId(id);
    r.seen.add(id);
    if (!el) { r.skipped.push({ field, wanted: String(wanted), reason: 'field not on page' }); return; }
    if (norm(el.value) === norm(wanted)) return;
    if (el.value.trim() !== '') { r.skipped.push({ field, wanted: String(wanted), reason: `page has "${el.value}"` }); return; }
    if (await setText(el, wanted)) r.filled.push(field);
    else r.skipped.push({ field, wanted: String(wanted), reason: 'value did not stick' });
  }

  async function ruleDate(r, field, ids, month, year) {
    if (year == null) return;
    const m = month != null ? byId(ids.month) : null;
    const y = byId(ids.year);
    r.seen.add(ids.month); r.seen.add(ids.year);
    const want = month != null ? `${String(month).padStart(2, '0')}/${year}` : String(year);
    if (!y || (month != null && !m)) { r.skipped.push({ field, wanted: want, reason: 'field not on page' }); return; }
    const sameM = !m || Number(m.value) === month, sameY = Number(y.value) === year;
    if (sameM && sameY) return;
    const has = [m?.value, y.value].filter((v) => v && v.trim() !== '');
    if (has.length) { r.skipped.push({ field, wanted: want, reason: `page has "${[m?.value, y.value].filter(Boolean).join('/')}"` }); return; }
    if (await setDate(m, y, month, year)) r.filled.push(field);
    else r.skipped.push({ field, wanted: want, reason: 'value did not stick' });
  }

  async function ruleListbox(r, field, label, id, wanted, source = wanted) {
    if (!wanted) return;
    const btn = byId(id);
    r.seen.add(id);
    if (!btn) { r.skipped.push({ field, wanted, reason: 'field not on page' }); return; }
    const cur = btnText(btn);
    if (norm(cur) === norm(wanted)) return;
    if (!isPlaceholder(cur)) { r.skipped.push({ field, wanted, reason: `page has "${cur}"` }); return; }
    const res = await selectListbox(id, wanted);
    if (res.ok) r.filled.push(field);
    else r.unmatchedOptions.push({ field, label, kind: 'listbox', targetId: id, wanted, source, options: res.options });
  }

  async function rulePrompt(r, field, label, id, query, exact, single = true) {
    if (!exact) return;
    const input = byId(id);
    r.seen.add(id);
    if (!input) { r.skipped.push({ field, wanted: exact, reason: 'field not on page' }); return; }
    const cur = chips(input);
    if (cur.some((c) => norm(c) === norm(exact))) return;
    if (single && cur.length) { r.skipped.push({ field, wanted: exact, reason: `page has "${cur[0]}"` }); return; }
    const res = await promptSelect(id, query, exact);
    if (res.ok) { if (!res.already) r.filled.push(field); }
    else r.unmatchedOptions.push({ field, label, kind: 'prompt', targetId: id, wanted: exact, source: exact, options: res.options });
  }

  function labelOf(el) {
    const id = el.id;
    const l = id && document.querySelector(`label[for="${CSS.escape(id)}"]`);
    return ((l && l.textContent) || el.getAttribute('aria-label') || id || el.tagName).replace(/\*/g, '').trim();
  }

  // Every aria-required control still empty after filling, that no rule already reported.
  function sweepRequired(r, root) {
    for (const el of root.querySelectorAll('[aria-required="true"]')) {
      if (el.id && r.seen.has(el.id)) continue;
      let empty;
      if (el.matches('input[type="radio"], input[type="checkbox"]')) continue;
      if (el.matches('[role="radiogroup"], fieldset')) empty = !el.querySelector('input:checked');
      else if (el.tagName === 'BUTTON') empty = isPlaceholder(btnText(el));
      else if ('value' in el) empty = el.value.trim() === '' && !chips(el).length;
      else continue;
      if (empty) r.skipped.push({ field: labelOf(el), wanted: '', reason: 'no source in apply.json' });
    }
  }

  async function fillMyInfo(r, data) {
    const c = data.candidate, f = M.myInfo;
    const wantRadio = c.previouslyWorked ? 'Yes' : 'No';
    await guard(r, 'Previously worked here', wantRadio, async () => {
      const rs = radios(f.previousWorkerRadio);
      if (!rs.length) return;
      const checked = rs.find((x) => x.checked);
      if (checked && norm(radioLabel(checked)) === norm(wantRadio)) return;
      if (checked) { r.skipped.push({ field: 'Previously worked here', wanted: wantRadio, reason: `page has "${radioLabel(checked)}"` }); return; }
      if (await setRadio(f.previousWorkerRadio, wantRadio)) r.filled.push('Previously worked here');
      else r.skipped.push({ field: 'Previously worked here', wanted: wantRadio, reason: 'value did not stick' });
    });
    await guard(r, 'Country', c.country, async () => {
      const before = r.filled.length;
      await ruleListbox(r, 'Country', 'Country', f.country, c.country);
      if (r.filled.length > before) { await sleep(500); await waitFor(() => byId(f.addressLine1), 4000); }
    });
    const texts = [['First Name', f.firstName, c.firstName], ['Last Name', f.lastName, c.lastName],
      ['Address Line 1', f.addressLine1, c.addressLine1], ['Postal Code', f.postalCode, c.postalCode], ['City', f.city, c.city]];
    for (const [field, id, v] of texts) await guard(r, field, v, () => ruleText(r, field, id, v));
    await guard(r, 'Phone Device Type', c.phoneType, () => ruleListbox(r, 'Phone Device Type', 'Phone Device Type', f.phoneType, c.phoneType));
    await guard(r, 'Country Phone Code', c.countryPhoneCode, () => rulePrompt(r, 'Country Phone Code', 'Country Phone Code', f.countryPhoneCode, 'Switzerland', c.countryPhoneCode));
    await guard(r, 'Phone Number', c.phone, () => ruleText(r, 'Phone Number', f.phoneNumber, c.phone));
  }

  const yearOf = (id) => { const v = byId(id)?.value?.trim(); return v ? Number(v) : ''; };

  // wantParts(w) / pageParts(n) -> [name, year]; key = W.workKey (same shape as W.eduKey).
  async function blocks(r, section, wanted, wantParts, pageParts, fillOne, label) {
    const cfg = M[section];
    const keyOf = ([nm, y]) => W.workKey(nm, y);
    const existing = W.blockNumbers(allIds(), cfg.prefix).map((n) => { const p = pageParts(n); return { n, nm: norm(p[0]), y: p[1], key: keyOf(p) }; });
    const want = wanted.map(wantParts);
    const { pairs, toAdd, extra } = W.matchBlocks(existing, want.map(keyOf));
    // A half-filled block (name but no year, or year but no name; e.g. a failed setDate) is reused, not duplicated.
    const spare = new Set(extra);
    const add = [];
    for (const w of toAdd) {
      const [nm, y] = want[w];
      const b = existing.find((e) => spare.has(e.n) && ((e.nm === norm(nm) && e.y === '') || (e.y === y && e.nm === '')));
      if (b) { spare.delete(b.n); pairs.push({ n: b.n, wanted: w }); } else add.push(w);
    }
    for (const n of spare) r.skipped.push({ field: `${label} block ${n}`, wanted: '', reason: 'extra block on page, left as is' });
    for (const w of add) {
      const n = await clickAdd(section);
      if (n == null) { r.skipped.push({ field: `${label} ${w + 1}`, wanted: keyOf(want[w]), reason: 'Add button not found or no new block appeared' }); continue; }
      pairs.push({ n, wanted: w });
    }
    for (const { n, wanted: w } of pairs.sort((a, b) => a.wanted - b.wanted)) await fillOne(n, wanted[w]);
  }

  async function fillWork(r, data) {
    const c = M.work, P = c.prefix, id = (n, f) => W.fieldId(P, n, f);
    await blocks(r, 'work', data.work, (w) => [w.company, w.startYear],
      (n) => [byId(id(n, c.company))?.value ?? '', yearOf(W.dateIds(P, n, c.start).year)],
      async (n, w) => {
        const tag = `${w.company} (${w.startYear})`;
        for (const [name, f, v] of [['Job Title', c.title, w.title], ['Company', c.company, w.company], ['Location', c.location, w.location]]) {
          await guard(r, `${tag}: ${name}`, v, () => ruleText(r, `${tag}: ${name}`, id(n, f), v));
        }
        await guard(r, `${tag}: I currently work here`, String(w.current), async () => {
          const box = byId(id(n, c.current));
          r.seen.add(id(n, c.current));
          if (!box) return;
          if (w.current && !box.checked) {
            if (await setCheckbox(box, true)) { r.filled.push(`${tag}: I currently work here`); await sleep(300); }
            else r.skipped.push({ field: `${tag}: I currently work here`, wanted: 'checked', reason: 'value did not stick' });
          } else if (!w.current && box.checked) {
            r.skipped.push({ field: `${tag}: I currently work here`, wanted: 'unchecked', reason: 'page has "checked"' });
          }
        });
        await guard(r, `${tag}: From`, w.startYear, () => ruleDate(r, `${tag}: From`, W.dateIds(P, n, c.start), w.startMonth, w.startYear));
        if (!w.current) await guard(r, `${tag}: To`, w.endYear, () => ruleDate(r, `${tag}: To`, W.dateIds(P, n, c.end), w.endMonth, w.endYear));
        await guard(r, `${tag}: Role Description`, '…', () => ruleText(r, `${tag}: Role Description`, id(n, c.description), w.description));
      }, 'work');
  }

  async function fillEducation(r, data) {
    const c = M.education, P = c.prefix, id = (n, f) => W.fieldId(P, n, f);
    await blocks(r, 'education', data.education, (e) => [e.school, e.startYear],
      (n) => [byId(id(n, c.school))?.value ?? '', yearOf(W.dateIds(P, n, c.first).year)],
      async (n, e) => {
        const tag = e.school;
        await guard(r, `${tag}: School`, e.school, () => ruleText(r, `${tag}: School`, id(n, c.school), e.school));
        await guard(r, `${tag}: Degree`, e.degreeText, async () => {
          const bid = id(n, c.degree);
          if (e.degreeCode) { await ruleListbox(r, `${tag}: Degree`, 'Degree', bid, e.degreeCode, e.degreeText); return; }
          // No code: read the tenant's options (an exact degreeText hit still fills) and hand them over.
          const btn = byId(bid);
          r.seen.add(bid);
          if (!btn) { r.skipped.push({ field: `${tag}: Degree`, wanted: e.degreeText, reason: 'field not on page' }); return; }
          const cur = btnText(btn);
          if (norm(cur) === norm(e.degreeText)) return;
          if (!isPlaceholder(cur)) { r.skipped.push({ field: `${tag}: Degree`, wanted: e.degreeText, reason: `page has "${cur}"` }); return; }
          const res = await selectListbox(bid, e.degreeText);
          if (res.ok) r.filled.push(`${tag}: Degree`);
          else r.unmatchedOptions.push({ field: `${tag}: Degree`, label: 'Degree', kind: 'listbox', targetId: bid, wanted: e.degreeText, source: e.degreeText, options: res.options });
        });
        await guard(r, `${tag}: Field of Study`, e.fieldOfStudy, () => rulePrompt(r, `${tag}: Field of Study`, 'Field of Study', id(n, c.fieldOfStudy), e.fieldOfStudy, e.fieldOfStudy));
        await guard(r, `${tag}: From`, e.startYear, () => ruleDate(r, `${tag}: From`, W.dateIds(P, n, c.first), null, e.startYear));
        await guard(r, `${tag}: To`, e.endYear, () => ruleDate(r, `${tag}: To`, W.dateIds(P, n, c.last), null, e.endYear));
      }, 'education');
  }

  async function fillSkills(r, data) {
    if (!byId(M.skills)) return;
    for (const s of (data.skills || []).slice(0, M.maxSkills)) {
      await guard(r, `Skill: ${s}`, s, async () => {
        const before = r.unmatchedOptions.length;
        await rulePrompt(r, `Skill: ${s}`, 'Skill not in catalog', M.skills, s, s, false);
        if (r.unmatchedOptions.length > before) r.unmatchedOptions[before].field = `skill "${s}"`;
      });
    }
  }

  async function fillUploads(r, data, files) {
    const names = Object.values(data.files || {}).filter(Boolean);
    if (!names.length) return;
    const input = uploadInput();
    const have = names.map((n) => files.find((f) => f.name === n)).filter(Boolean);
    for (const n of names) if (!have.some((f) => f.name === n)) r.skipped.push({ field: `Upload ${n}`, wanted: n, reason: 'file not passed to the filler' });
    if (!have.length) return;
    const res = await upload(input, have);
    for (const [n, s] of Object.entries(res)) {
      if (s === 'uploaded') r.filled.push(`Upload ${n}`);
      else if (s === 'failed') r.skipped.push({ field: `Upload ${n}`, wanted: n, reason: 'Workday did not accept the file; drop it by hand' });
    }
  }

  async function run(data, files = []) {
    const step = W.stepOf([...document.querySelectorAll('[data-automation-id]')].map((e) => e.getAttribute('data-automation-id')));
    if (!step) return { step: null, filled: [], skipped: [], unmatchedOptions: [] };
    const r = newReport(step);
    const section = async (name, fn) => {
      try { await fn(); } catch (e) { r.skipped.push({ field: name, wanted: '', reason: 'error: ' + (e && e.message || e) }); }
    };
    if (step === 'myInfo') await section('My Information', () => fillMyInfo(r, data));
    else {
      await section('Work Experience', () => fillWork(r, data));
      await section('Education', () => fillEducation(r, data));
      await section('Skills', () => fillSkills(r, data));
      await section('LinkedIn', () => guard(r, 'LinkedIn', data.candidate.linkedin, () => ruleText(r, 'LinkedIn', M.linkedin, data.candidate.linkedin)));
      await section('Uploads', () => guard(r, 'Uploads', '', () => fillUploads(r, data, files)));
    }
    await section('Required sweep', async () => {
      const root = document.querySelector(auto(M.steps[step]));
      if (root) sweepRequired(r, root);
    });
    const { seen, ...report } = r;
    return report;
  }

  async function applyOption(entry, text) {
    const res = entry.kind === 'listbox' ? await selectListbox(entry.targetId, text) : await promptSelect(entry.targetId, text, text);
    return { ok: res.ok, options: res.options };
  }

  globalThis.CareerOpsFill = { run, applyOption };
})();
