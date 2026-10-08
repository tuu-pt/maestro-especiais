/** Mock API for component tests. By default the application is empty, as in production. */

import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

export const BASE = "http://localhost";
export const api = (path: string) => `${BASE}/api${path}`;

export const DEV_USERS = [
  { login: "redator", id: "dev:redator", name: "Redator (desenvolvimento)", roles: [{ id: "redator", label: "Redator" }] },
  {
    login: "tecnico",
    id: "dev:tecnico",
    name: "Técnico responsável (desenvolvimento)",
    roles: [
      { id: "redator", label: "Redator" },
      { id: "tecnico", label: "Técnico responsável" },
    ],
  },
  { login: "curador", id: "dev:curador", name: "Curador (desenvolvimento)", roles: [{ id: "curador", label: "Curador" }] },
];

export const seenUsers: string[] = [];

export const defaultHandlers = [
  http.get(api("/me"), ({ request }) => {
    const login = request.headers.get("X-Dev-User") ?? "";
    seenUsers.push(login);
    const user = DEV_USERS.find((u) => u.login === login) ?? DEV_USERS[0];
    return HttpResponse.json(user);
  }),
  http.get(api("/dev/users"), () => HttpResponse.json(DEV_USERS)),
  http.get(api("/projects"), () => HttpResponse.json([])),
  http.get(api("/activity"), () => HttpResponse.json([])),
  http.get(api("/knowledge/cables"), () => HttpResponse.json({ designations: [], equivalences: [] })),
  http.get(api("/knowledge/typologies"), () => HttpResponse.json([])),
  http.get(api("/library/blocks"), () => HttpResponse.json([])),
  http.get(api("/knowledge/regulations"), () => HttpResponse.json([])),
  http.get(api("/settings/llm"), () => HttpResponse.json({ primary: "gemini", order: [], providers: [] })),
  http.get(api("/health"), () =>
    HttpResponse.json({ status: "ok", services: { database: { status: "ok" } } }),
  ),
];

export const server = setupServer(...defaultHandlers);
