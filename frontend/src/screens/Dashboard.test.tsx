import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { AuditEntry, Project } from "../api/types";
import { renderAt } from "../test/render";
import { api, server } from "../test/server";

const project = (over: Partial<Project> = {}): Project => ({
  id: "p1",
  code: "R9",
  name: "Moradia",
  building_type: "moradia unifamiliar",
  phase: "execucao",
  specialties: ["ELE"],
  public_procurement: false,
  status: "active",
  created_at: "2026-09-24T10:00:00Z",
  created_by: "dev:redator",
  file_count: 2,
  ficha_status: "draft",
  open_conflicts: 1,
  ...over,
});

describe("dashboard", () => {
  it("starts empty and offers to create a project", async () => {
    renderAt("/");
    expect(await screen.findByRole("heading", { name: "Ainda não há projetos" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Criar projeto" })).toHaveAttribute("href", "/projetos/novo");
    expect(screen.queryByRole("region", { name: "Projetos" })).not.toBeInTheDocument();
  });

  it("lists projects with the state of their ficha-base and recent activity", async () => {
    const event: AuditEntry = {
      id: "e1",
      at: "2026-09-24T10:05:00Z",
      actor_type: "system",
      actor_name: "Sistema",
      action: "file.ingested",
      description: "Leu Tabela de Cálculo: 1 conflito para resolver",
      project_id: "p1",
      project_code: "R9",
    };
    server.use(
      http.get(api("/projects"), () =>
        HttpResponse.json([project(), project({ id: "p2", code: "R8", open_conflicts: 0, ficha_status: "confirmed" })]),
      ),
      http.get(api("/activity"), () => HttpResponse.json([event])),
    );

    renderAt("/");

    const table = await screen.findByRole("region", { name: "Projetos" });
    expect(within(table).getByRole("link", { name: "R9" })).toHaveAttribute("href", "/projetos/p1/ficha");
    expect(within(table).getByText("1 conflito por resolver")).toBeInTheDocument();
    expect(within(table).getByText("Ficha-base confirmada")).toBeInTheDocument();
    expect(screen.getByText("Conflitos por resolver").nextSibling).toHaveTextContent("1");
    expect(await screen.findByText(/Leu Tabela de Cálculo/)).toBeInTheDocument();
  });

  it("shows new critical issues of a project without opening it", async () => {
    server.use(
      http.get(api("/projects"), () =>
        HttpResponse.json([
          project({
            validation: { status: "done", finished_at: "2026-09-28T10:00:05Z", open_critical: 3, new_critical: 2, warning: 5 },
          }),
          project({ id: "p2", code: "R8", open_conflicts: 0, ficha_status: "confirmed", validation: null }),
        ]),
      ),
      http.get(api("/activity"), () => HttpResponse.json([])),
    );

    renderAt("/");

    const table = await screen.findByRole("region", { name: "Projetos" });
    const alert = within(table).getByRole("link", { name: /3 críticos/ });
    expect(alert).toHaveAttribute("href", "/projetos/p1/validacao");
    expect(within(alert).getByText("2 novos")).toBeInTheDocument();
    expect(within(table).getByText("Por validar")).toBeInTheDocument();
    expect(screen.getByText("Alertas críticos abertos").nextSibling).toHaveTextContent("3");
  });
});
