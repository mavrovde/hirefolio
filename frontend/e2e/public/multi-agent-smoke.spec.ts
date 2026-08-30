import { test, expect } from '@playwright/test';
import { API_PREFIX } from '../config';

/**
 * UNMOCKED contract smoke test for POST /ai/multi-chat (issue #187).
 *
 * `multi-agent.spec.ts` — the spec named after this endpoint — `page.route`-mocks
 * it, so nothing in the suite ever exercised the real thing. That is exactly how
 * #180 hid: crewai 1.x rejected the LangChain client and the endpoint raised
 * *before* the generator's first yield, which (the body having already started)
 * surfaced as **HTTP 200 + a truncated body**, not a 500. `response.ok` was true,
 * every guard passed, and 778 unit tests stayed green while the public /llm page
 * showed "Connection Error".
 *
 * So this test asserts the two things a mocked spec structurally cannot:
 *   1. the stream carries real generated content, and
 *   2. it TERMINATES with `{"done": true}` rather than the connection dropping.
 *
 * Rule 10: the E2E stack runs with an empty GEMINI_API_KEY, so generation falls
 * back to the in-stack Ollama — no paid API is reached.
 */
test.describe('Multi-Agent Conversation — unmocked contract', () => {
  // Local models are slow; the failure mode this guards against (an immediate
  // abort) shows up in seconds, but a healthy run needs room to generate.
  test.setTimeout(180_000);

  test('streams well-formed NDJSON and terminates with done:true', async ({ request }) => {
    const response = await request.post(`${API_PREFIX}/ai/multi-chat`, {
      data: {
        topic: 'One short sentence about testing.',
        agents: [
          { id: 1, description: 'Answers in one short sentence.', role: 'Tester', goal: 'Be brief' },
        ],
      },
      timeout: 170_000,
    });

    // A pre-yield crash also returns 200, so status alone proves nothing —
    // it is the body that has to be checked.
    expect(response.status()).toBe(200);

    const raw = await response.text();
    const lines = raw.split('\n').filter(l => l.trim().length > 0);
    expect(lines.length, 'the stream must carry at least one chunk').toBeGreaterThan(0);

    // Every chunk must be parseable: a mid-body abort leaves a truncated tail.
    const chunks = lines.map((line, i) => {
      try {
        return JSON.parse(line);
      } catch {
        throw new Error(`chunk ${i} is not valid JSON (truncated stream?): ${line.slice(0, 200)}`);
      }
    });

    // The terminator is the contract the frontend relies on to stop reading.
    const last = chunks[chunks.length - 1];
    expect(last.done, `stream must end with done:true, got: ${JSON.stringify(last)}`).toBe(true);

    // And the conversation must actually have produced content, not just a
    // terminator — otherwise a silently-degraded endpoint would still pass.
    const produced = chunks
      .filter(c => c.agent === 1)
      .map(c => String(c.content ?? ''))
      .join('');
    expect(produced.trim().length, 'agent 1 must produce some content').toBeGreaterThan(0);
  });

  test('rejects a request with no agents without breaking the stream', async ({ request }) => {
    const response = await request.post(`${API_PREFIX}/ai/multi-chat`, {
      data: { topic: 'Empty roster', agents: [] },
      timeout: 30_000,
    });

    expect(response.status()).toBe(200);
    const raw = await response.text();
    // An empty roster yields no chunks at all — the point is that the request
    // completes cleanly rather than erroring or hanging.
    for (const line of raw.split('\n').filter(l => l.trim().length > 0)) {
      expect(() => JSON.parse(line)).not.toThrow();
    }
  });
});
