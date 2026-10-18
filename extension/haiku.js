// Haiku assist: build the Messages API request and parse a single-choice answer. Classic script.
(function () {
  function buildHaikuRequest(entry, apiKey) {
    const options = [...new Set(entry.options)];
    const prompt = [
      'A job application form has a field with no exact match for our value.',
      `Field: ${entry.label}`,
      `Wanted value: ${entry.wanted}`,
      `Source line: ${entry.source}`,
      'Options:',
      ...options,
      '',
      'Pick the one option a recruiter would treat as the same thing, copied verbatim, or null if none fits.',
    ].join('\n');
    const body = {
      model: 'claude-haiku-5-5',
      max_tokens: 256,
      thinking: { type: 'disabled' },
      output_config: {
        effort: 'low',
        format: {
          type: 'json_schema',
          schema: {
            type: 'object',
            properties: {
              choice: { anyOf: [{ type: 'string', enum: options }, { type: 'null' }] },
              why: { type: 'string' },
            },
            required: ['choice', 'why'],
            additionalProperties: false,
          },
        },
      },
      messages: [{ role: 'user', content: prompt }],
    };
    return {
      url: 'https://api.anthropic.com/v1/messages',
      init: {
        method: 'POST',
        headers: {
          'x-api-key': apiKey,
          'anthropic-version': '2023-06-01',
          'content-type': 'application/json',
          'anthropic-dangerous-direct-browser-access': 'true',
        },
        body: JSON.stringify(body),
      },
    };
  }

  function parseHaikuResponse(body, options) {
    try {
      const block = (body.content || []).find((b) => b.type === 'text');
      const out = JSON.parse(block.text);
      const why = typeof out.why === 'string' ? out.why : '';
      return { choice: options.includes(out.choice) ? out.choice : null, why };
    } catch {
      return { choice: null, why: 'unparseable response' };
    }
  }

  globalThis.CareerOpsHaiku = { buildHaikuRequest, parseHaikuResponse };
})();
