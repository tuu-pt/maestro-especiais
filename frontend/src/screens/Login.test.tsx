import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { api, server } from "../test/server";
import { renderAt } from "../test/render";
import { backTo } from "../lib/backTo";

const ACCOUNT = {
  id: "user:1",
  name: "Técnica de Teste",
  roles: [{ id: "tecnico", label: "Técnico responsável" }],
  session: "account",
};

function signedOut() {
  let signedIn = false;
  server.use(
    http.get(api("/me"), () =>
      signedIn ? HttpResponse.json(ACCOUNT) : HttpResponse.json({ detail: "Sessão não iniciada." }, { status: 401 }),
    ),
    http.post(api("/auth/login"), async ({ request }) => {
      const body = (await request.json()) as { password: string };
      if (body.password !== "certa-de-teste") {
        return HttpResponse.json({ detail: "Email ou password inválidos. Tente novamente." }, { status: 401 });
      }
      signedIn = true;
      return HttpResponse.json(ACCOUNT);
    }),
  );
}

describe("login (accounts with a password, until D6)", () => {
  it("sends whoever is not signed in to the login page, and back after signing in", async () => {
    signedOut();
    const { router } = renderAt("/definicoes");

    expect(await screen.findByRole("heading", { name: "Maestro Especiais" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/entrar");
    await userEvent.type(screen.getByLabelText("Email"), "tecnica@exemplo.test");
    await userEvent.type(screen.getByLabelText("Password"), "certa-de-teste");
    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByRole("heading", { name: "Definições" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/definicoes");
    expect(screen.getByText("Técnica de Teste")).toBeInTheDocument();
    expect(screen.queryByLabelText("Utilizador de desenvolvimento")).not.toBeInTheDocument();
  });

  it("says only that the email or the password is wrong", async () => {
    signedOut();
    renderAt("/entrar");

    await userEvent.type(await screen.findByLabelText("Email"), "tecnica@exemplo.test");
    await userEvent.type(screen.getByLabelText("Password"), "errada");
    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Email ou password inválidos. Tente novamente.");
  });

  it("signs out with Sair", async () => {
    let ended = false;
    server.use(
      http.get(api("/me"), () =>
        ended ? HttpResponse.json({ detail: "Sessão não iniciada." }, { status: 401 }) : HttpResponse.json(ACCOUNT),
      ),
      http.post(api("/auth/logout"), () => {
        ended = true;
        return HttpResponse.json({ ended: true });
      }),
    );
    const { router } = renderAt("/");

    await userEvent.click(await screen.findByRole("button", { name: "Sair" }));

    expect(await screen.findByRole("button", { name: "Entrar" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/entrar");
    expect(ended).toBe(true);
  });

  it("goes back only to a page of the application", () => {
    expect(backTo("/projetos/1/ficha")).toBe("/projetos/1/ficha");
    expect(backTo("//outro.site")).toBe("/");
    expect(backTo("https://outro.site")).toBe("/");
    expect(backTo(null)).toBe("/");
  });
});
