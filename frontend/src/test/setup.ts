import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, vi } from "vitest";

import { BASE, seenUsers, server } from "./server";

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
  // The app calls relative URLs (/api/…); Node's fetch needs absolute ones.
  const patched = globalThis.fetch;
  globalThis.fetch = (input: RequestInfo | URL, init?: RequestInit) =>
    patched(typeof input === "string" && input.startsWith("/") ? `${BASE}${input}` : input, init);
});

afterEach(() => {
  cleanup();
  server.resetHandlers();
  seenUsers.length = 0;
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  vi.restoreAllMocks();
});

afterAll(() => server.close());
