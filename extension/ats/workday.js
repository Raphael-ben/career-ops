// Workday field map + pure helpers. Classic script: no DOM, no import/export.
(function () {
  const map = {
    steps: { myInfo: 'applyFlowMyInfoPage', myExp: 'applyFlowMyExpPage' },
    never: ['pageFooterNextButton'],
    myInfo: {
      previousWorkerRadio: 'candidateIsPreviousWorker', country: 'country--country',
      firstName: 'name--legalName--firstName', lastName: 'name--legalName--lastName',
      addressLine1: 'address--addressLine1', postalCode: 'address--postalCode', city: 'address--city',
      phoneType: 'phoneNumber--phoneType', countryPhoneCode: 'phoneNumber--countryPhoneCode',
      phoneNumber: 'phoneNumber--phoneNumber',
    },
    // addLabel regexes are provisional: all Add buttons share data-automation-id "add-button".
    work: {
      prefix: 'workExperience', addLabel: /Work Experience/i, title: 'jobTitle', company: 'companyName',
      location: 'location', current: 'currentlyWorkHere', description: 'roleDescription',
      start: 'startDate', end: 'endDate',
    },
    education: {
      prefix: 'education', addLabel: /Education/i, school: 'schoolName', degree: 'degree',
      fieldOfStudy: 'fieldOfStudy', first: 'firstYearAttended', last: 'lastYearAttended',
    },
    skills: 'skills--skills',
    linkedin: 'socialNetworkAccounts--linkedInAccount',
    maxSkills: 10,
    upload: { zone: 'attachments-FileUpload', input: 'file-upload-input-ref', remove: 'delete-file' },
    addButton: 'add-button',
    date: { month: 'dateSectionMonth-input', year: 'dateSectionYear-input' },
    prompt: { option: 'promptOption', chip: 'selectedItem' },
    listboxOption: '[role="option"]',
  };

  const norm = (s) => String(s ?? '').trim().toLowerCase().replace(/\s+/g, ' ');
  const alnum = (s) => String(s ?? '').toLowerCase().replace(/[^a-z0-9]/g, '');
  const key = (name, year) => {
    const n = norm(name), y = year ?? '';
    return n === '' && y === '' ? '' : `${n}|${y}`;
  };

  function stepOf(ids) {
    for (const [step, id] of Object.entries(map.steps)) if (ids.includes(id)) return step;
    return null;
  }

  function blockNumbers(ids, prefix) {
    const re = new RegExp('^' + prefix + '-(\\d+)--');
    const out = [];
    for (const id of ids) {
      const m = re.exec(id);
      if (m && !out.includes(+m[1])) out.push(+m[1]);
    }
    return out;
  }

  const fieldId = (prefix, n, field) => `${prefix}-${n}--${field}`;
  const dateIds = (prefix, n, which) => ({
    month: `${prefix}-${n}--${which}-${map.date.month}`,
    year: `${prefix}-${n}--${which}-${map.date.year}`,
  });

  function matchBlocks(existing, wantedKeys) {
    const pairs = [], toAdd = [], used = new Set();
    const unmatched = [];
    wantedKeys.forEach((k, w) => {
      const b = k !== '' && existing.find((e) => !used.has(e.n) && e.key === k);
      if (b) { used.add(b.n); pairs.push({ n: b.n, wanted: w }); } else unmatched.push(w);
    });
    for (const w of unmatched) {
      const b = existing.find((e) => !used.has(e.n) && e.key === '');
      if (b) { used.add(b.n); pairs.push({ n: b.n, wanted: w }); } else toAdd.push(w);
    }
    const extra = existing.filter((e) => !used.has(e.n) && e.key !== '').map((e) => e.n);
    return { pairs, toAdd, extra };
  }

  function pickOption(options, wanted) {
    const w = norm(wanted);
    return options.find((o) => norm(o) === w) ?? null;
  }

  function shorterQuery(text) {
    const words = String(text).trim().split(/\s+/);
    return words.length > 1 ? words[0] : words[0].slice(0, 4);
  }

  function companyMatchesHost(company, host) {
    const first = alnum(String(company).trim().split(/\s+/)[0]);
    return first.length >= 3 && alnum(host).includes(first);
  }

  globalThis.CareerOpsWorkday = {
    map, stepOf, blockNumbers, fieldId, dateIds,
    workKey: key, eduKey: key, matchBlocks, pickOption, shorterQuery, companyMatchesHost,
  };
})();
