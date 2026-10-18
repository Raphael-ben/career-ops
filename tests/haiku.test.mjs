import { test } from 'node:test';
import assert from 'node:assert/strict';

await import('../extension/haiku.js');
const H = globalThis.CareerOpsHaiku;

const entry = {
  field: 'education 1 degree', label: 'Degree', kind: 'listbox', targetId: 'education-3--degree',
  wanted: 'MS', source: 'Master of Mechanical Engineering', options: ['BS', 'MEng', 'MBA'],
};
const reply = (text) => ({ content: [{ type: 'text', text }] });

test('buildHaikuRequest targets the Messages API', () => {
  const { url, init } = H.buildHaikuRequest(entry, 'k');
  assert.equal(url, 'https://api.anthropic.com/v1/messages');
  assert.equal(init.method, 'POST');
  assert.equal(init.headers['x-api-key'], 'k');
  assert.equal(init.headers['anthropic-version'], '2023-06-01');
  assert.equal(init.headers['content-type'], 'application/json');
  assert.equal(init.headers['anthropic-dangerous-direct-browser-access'], 'true');
});

test('buildHaikuRequest body', () => {
  const body = JSON.parse(H.buildHaikuRequest(entry, 'k').init.body);
  assert.equal(body.model, 'claude-haiku-5-5');
  assert.equal(body.max_tokens, 256);
  assert.deepEqual(body.thinking, { type: 'disabled' });
  assert.equal(body.output_config.effort, 'low');
  assert.equal(body.output_config.format.type, 'json_schema');
  const schema = body.output_config.format.schema;
  assert.deepEqual(schema.required, ['choice', 'why']);
  assert.equal(schema.additionalProperties, false);
  const variants = schema.properties.choice.anyOf;
  assert.ok(variants.some((v) => v.type === 'null'));
  assert.deepEqual(variants.find((v) => v.enum).enum, entry.options);
  assert.equal(body.messages.length, 1);
  const text = body.messages[0].content;
  for (const s of ['Degree', 'MS', 'Master of Mechanical Engineering', ...entry.options]) {
    assert.ok(text.includes(s), s);
  }
});

test('parseHaikuResponse accepts a verbatim option', () => {
  assert.deepEqual(
    H.parseHaikuResponse(reply('{"choice":"MEng","why":"engineering master"}'), entry.options),
    { choice: 'MEng', why: 'engineering master' });
});

test('parseHaikuResponse rejects a choice not verbatim in options', () => {
  for (const c of ['MEng ', 'meng', 'PhD']) {
    const r = H.parseHaikuResponse(reply(JSON.stringify({ choice: c, why: 'x' })), entry.options);
    assert.equal(r.choice, null, c);
  }
});

test('parseHaikuResponse keeps null and survives junk', () => {
  assert.deepEqual(H.parseHaikuResponse(reply('{"choice":null,"why":"none fit"}'), entry.options),
    { choice: null, why: 'none fit' });
  for (const body of [reply('not json'), {}, null]) {
    const r = H.parseHaikuResponse(body, entry.options);
    assert.equal(r.choice, null);
    assert.ok(typeof r.why === 'string' && r.why.length > 0);
  }
});
