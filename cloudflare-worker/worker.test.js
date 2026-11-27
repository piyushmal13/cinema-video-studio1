import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import worker from "./worker.js";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

function makeRequest(message) {
  return new Request("https://worker.example/webhook", {
    method: "POST",
    body: JSON.stringify({ message }),
    headers: { "Content-Type": "application/json" },
  });
}

function makeEnv(overrides = {}) {
  return {
    TELEGRAM_BOT_TOKEN: "test-token",
    GITHUB_PAT: "test-pat",
    GITHUB_REPO: "owner/repo",
    ALLOWED_CHAT_ID: "123",
    ...overrides,
  };
}

test("dispatches a request and stores it in per-chat context", async () => {
  const calls = [];
  const values = new Map();
  globalThis.fetch = async (url, init) => {
    calls.push({ url: String(url), body: init?.body });
    return new Response(null, { status: String(url).includes("dispatches") ? 204 : 200 });
  };
  const env = makeEnv({
    PROMPT_CONTEXT_KV: {
      async get(key) {
        return values.get(key) ?? null;
      },
      async put(key, value, options) {
        values.set(key, value);
        assert.equal(options.expirationTtl, 30 * 24 * 60 * 60);
      },
    },
  });

  const response = await worker.fetch(
    makeRequest({ chat: { id: 123 }, text: "/video Explain ocean tides" }),
    env
  );

  assert.equal(response.status, 200);
  const dispatch = JSON.parse(calls[0].body);
  assert.equal(dispatch.client_payload.text, "Explain ocean tides");
  assert.equal(dispatch.client_payload.format, "vertical");
  assert.equal(dispatch.client_payload.prompt_context, "");
  assert.deepEqual(JSON.parse(values.get("chat:123")).prompts, [
    { text: "Explain ocean tides", format: "vertical" },
  ]);
});

test("passes prior requests only for a clear follow-up and supports forgetting", async () => {
  const calls = [];
  const values = new Map([
    [
      "chat:123",
      JSON.stringify({
        prompts: [{ text: "A film about ocean science", format: "landscape" }],
      }),
    ],
  ]);
  globalThis.fetch = async (url, init) => {
    calls.push({ url: String(url), body: init?.body });
    return new Response(null, { status: String(url).includes("dispatches") ? 204 : 200 });
  };
  const env = makeEnv({
    PROMPT_CONTEXT_KV: {
      async get(key) {
        return values.get(key) ?? null;
      },
      async put(key, value) {
        values.set(key, value);
      },
      async delete(key) {
        values.delete(key);
      },
    },
  });

  await worker.fetch(
    makeRequest({ chat: { id: 123 }, text: "Make it more emotional" }),
    env
  );
  const dispatch = JSON.parse(calls[0].body);
  assert.equal(dispatch.client_payload.prompt_context, "A film about ocean science");
  assert.equal(dispatch.client_payload.format, "landscape");

  await worker.fetch(makeRequest({ chat: { id: 123 }, text: "/forget" }), env);
  assert.equal(values.has("chat:123"), false);
  assert.match(JSON.parse(calls.at(-1).body).text, /context cleared/i);
});

test("honors natural landscape intent and reports GitHub dispatch failures", async () => {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url: String(url), body: init?.body });
    return String(url).includes("dispatches")
      ? new Response("denied", { status: 403 })
      : new Response(null, { status: 200 });
  };

  const response = await worker.fetch(
    makeRequest({
      chat: { id: 123 },
      text: "/video Make a 60-second widescreen explainer about tides",
    }),
    makeEnv()
  );

  assert.equal(response.status, 502);
  assert.equal(JSON.parse(calls[0].body).client_payload.format, "landscape");
  assert.match(JSON.parse(calls[1].body).text, /could not be queued/);
});

test("blocks unauthorized commands before revealing the chat id", async () => {
  let fetchCalls = 0;
  globalThis.fetch = async () => {
    fetchCalls += 1;
    return new Response(null, { status: 200 });
  };

  const response = await worker.fetch(
    makeRequest({ chat: { id: 999 }, text: "/id" }),
    makeEnv()
  );

  assert.equal(response.status, 403);
  assert.equal(fetchCalls, 0);
});

test("rejects oversized prompts and allows standalone work without memory binding", async () => {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url: String(url), body: init?.body });
    return new Response(null, { status: String(url).includes("dispatches") ? 204 : 200 });
  };

  const response = await worker.fetch(
    makeRequest({ chat: { id: 123 }, text: `/video ${"x".repeat(4001)}` }),
    makeEnv()
  );
  assert.equal(response.status, 413);

  const standalone = await worker.fetch(
    makeRequest({ chat: { id: 123 }, text: "Explain ocean tides" }),
    makeEnv()
  );
  assert.equal(standalone.status, 200);
  assert.equal(JSON.parse(calls[1].body).client_payload.prompt_context, "");
  assert.match(JSON.parse(calls[2].body).text, /memory is not configured/i);
});


test("dispatches Telegram photo references with their file metadata", async () => {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url: String(url), body: init?.body });
    return new Response(null, { status: String(url).includes("dispatches") ? 204 : 200 });
  };
  const response = await worker.fetch(
    makeRequest({
      chat: { id: 123 },
      photo: [
        { file_id: "small-photo", file_unique_id: "small", file_size: 1000 },
        { file_id: "large-photo", file_unique_id: "large", file_size: 5000 },
      ],
      caption: "/reel Create a premium product reel",
    }),
    makeEnv()
  );
  assert.equal(response.status, 200);
  const dispatch = JSON.parse(calls[0].body);
  assert.equal(dispatch.client_payload.reference_file_id, "large-photo");
  assert.equal(dispatch.client_payload.reference_kind, "image");
  assert.equal(dispatch.client_payload.reference_mime_type, "image/jpeg");
  assert.equal(dispatch.client_payload.text, "Create a premium product reel");
});

test("accepts a reference video without caption and supplies a style-only brief", async () => {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url: String(url), body: init?.body });
    return new Response(null, { status: String(url).includes("dispatches") ? 204 : 200 });
  };
  const response = await worker.fetch(
    makeRequest({
      chat: { id: 123 },
      video: { file_id: "reference-video", file_unique_id: "v1", file_size: 900000, mime_type: "video/mp4" },
    }),
    makeEnv()
  );
  assert.equal(response.status, 200);
  const dispatch = JSON.parse(calls[0].body);
  assert.equal(dispatch.client_payload.reference_kind, "video");
  assert.match(dispatch.client_payload.text, /editing rhythm/i);
});

test("rejects unsupported and oversized reference attachments", async () => {
  const messages = [];
  globalThis.fetch = async (url, init) => {
    messages.push(JSON.parse(init.body));
    return new Response(null, { status: 200 });
  };
  const unsupported = await worker.fetch(
    makeRequest({ chat: { id: 123 }, document: { file_id: "zip", mime_type: "application/zip" }, caption: "make a video" }),
    makeEnv()
  );
  assert.equal(unsupported.status, 415);
  const oversized = await worker.fetch(
    makeRequest({ chat: { id: 123 }, video: { file_id: "big", file_size: 21 * 1024 * 1024, mime_type: "video/mp4" }, caption: "make a video" }),
    makeEnv()
  );
  assert.equal(oversized.status, 415);
  assert.match(messages.at(-1).text, /20 MB/i);
});
