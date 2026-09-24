import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { api, seenUsers, server } from "../test/server";
import { renderAt } from "../test/render";

describe("application shell", () => {
  it("has the navigation of the mock-up with the current page marked", async () => {
    renderAt("/");
    const nav = await screen.findByRole("navigation", { name: "Navegação principal" });
    const links = within(nav).getAllByRole("link").map((l) => l.textContent);
    expect(links).toEqual([
      "Painel",
      "Ficha do projeto",
      "Documentos",
      "Validação",
      "Equipamentos",
      "Revisão",
      "Conhecimento",
      "Definições",
    ]);
    expect(within(nav).getByRole("link", { name: "Painel" })).toHaveAttribute("aria-current", "page");
  });

  it("switches the development user for the next requests", async () => {
    renderAt("/definicoes");
    const select = await screen.findByLabelText("Utilizador de desenvolvimento");
    await screen.findByText(/Redator \(desenvolvimento\) · Redator/);

    await userEvent.selectOptions(select, "tecnico");

    expect(await screen.findByText(/Técnico responsável \(desenvolvimento\) ·/)).toBeInTheDocument();
    expect(seenUsers).toContain("tecnico");
  });

  it("hides the switcher when development users are not available", async () => {
    server.use(http.get(api("/dev/users"), () => new HttpResponse(null, { status: 404 })));
    renderAt("/");
    await screen.findByRole("heading", { name: "Painel" });
    expect(screen.queryByLabelText("Utilizador de desenvolvimento")).not.toBeInTheDocument();
  });

  it("lets people choose the light or dark theme", async () => {
    renderAt("/");
    await userEvent.selectOptions(await screen.findByLabelText("Tema"), "dark");
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    await userEvent.selectOptions(screen.getByLabelText("Tema"), "system");
    expect(document.documentElement).not.toHaveAttribute("data-theme");
  });

  it("project screens ask for a project when none is chosen", async () => {
    renderAt("/documentos");
    expect(await screen.findByRole("heading", { name: "Nenhum projeto selecionado" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Criar projeto" })).toHaveAttribute("href", "/projetos/novo");
  });
});
