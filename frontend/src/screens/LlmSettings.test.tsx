import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { setDevUser } from "../api/client";
import type { LlmSettings } from "../api/types";
import { renderAt } from "../test/render";
import { api, server } from "../test/server";

const provider = (name: "gemini" | "groq" | "claude", label: string, configured: boolean, key = configured) => ({
  name,
  label,
  key_set: key,
  models: configured ? { drafting: `${name}-modelo`, extraction: `${name}-modelo` } : { drafting: "", extraction: "" },
  rpm: 10,
  rpd: 200,
  configured,
});

const settings = (primary = "gemini"): LlmSettings => ({
  primary,
  order: primary === "groq" ? ["groq", "gemini"] : ["gemini", "groq"],
  providers: [
    provider("gemini", "Gemini (Google)", true),
    provider("groq", "Groq", true),
    provider("claude", "Claude (Anthropic)", false, true),
  ],
});

const ADMIN = { login: "admin", id: "dev:admin", name: "Admin (desenvolvimento)", roles: [{ id: "admin", label: "Administrador" }] };

afterEach(() => setDevUser("redator"));

describe("LLM providers (screen Definições)", () => {
  it("shows the order and what each provider lacks, read only for a redator", async () => {
    server.use(http.get(api("/settings/llm"), () => HttpResponse.json(settings())));
    renderAt("/definicoes");

    expect(await screen.findByText("Gemini (Google) → Groq")).toBeInTheDocument();
    const claude = screen.getByText("Claude (Anthropic)").closest("li")!;
    expect(within(claude).getByText("Sem modelo no .env")).toBeInTheDocument();
    expect(within(claude).getByRole("radio")).toBeDisabled();
    expect(screen.getByText(/Só o administrador muda o fornecedor principal/)).toBeInTheDocument();
  });

  it("lets the admin change the main provider with a reason", async () => {
    setDevUser("admin");
    const puts: unknown[] = [];
    server.use(
      http.get(api("/me"), () => HttpResponse.json(ADMIN)),
      http.get(api("/settings/llm"), () => HttpResponse.json(settings())),
      http.put(api("/settings/llm"), async ({ request }) => {
        puts.push(await request.json());
        return HttpResponse.json(settings("groq"));
      }),
    );
    const user = userEvent.setup();
    renderAt("/definicoes");

    await user.click(await screen.findByRole("radio", { name: /Groq/ }));
    const change = screen.getByRole("button", { name: "Mudar o principal" });
    expect(change).toBeDisabled();
    await user.type(screen.getByLabelText(/Porque muda/), "Gemini em 503.");
    await user.click(change);

    await waitFor(() => expect(puts).toEqual([{ primary: "groq", reason: "Gemini em 503." }]));
    expect(await screen.findByText("Groq → Gemini (Google)")).toBeInTheDocument();
  });
});
