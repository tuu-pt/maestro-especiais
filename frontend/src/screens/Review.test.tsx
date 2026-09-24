import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { AuditEntry } from "../api/types";
import { emptyFicha, project } from "../test/fixtures";
import { renderAt } from "../test/render";
import { api, server } from "../test/server";

describe("review and export", () => {
  it("shows the real audit log and keeps approval and export locked", async () => {
    const events: AuditEntry[] = [
      {
        id: "1",
        at: "2026-09-24T10:00:00Z",
        actor_type: "user",
        actor_name: "Redator (desenvolvimento)",
        action: "project.created",
        description: "Projeto R9 criado",
        project_id: "p1",
        project_code: "R9",
      },
      {
        id: "2",
        at: "2026-09-24T10:01:00Z",
        actor_type: "system",
        actor_name: "Sistema",
        action: "file.ingested",
        description: "Leu ficha eletrotécnica: 21 valores lidos (21 novos)",
        project_id: "p1",
        project_code: "R9",
      },
    ];
    server.use(
      http.get(api("/projects/p1"), () => HttpResponse.json(project())),
      http.get(api("/projects/p1/ficha"), () => HttpResponse.json(emptyFicha())),
      http.get(api("/projects/p1/audit"), () => HttpResponse.json(events)),
    );

    renderAt("/projetos/p1/revisao");

    expect(await screen.findByText("Projeto R9 criado")).toBeInTheDocument();
    expect(screen.getByText(/Leu ficha eletrotécnica/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aprovar" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "MDJ e CTE (.docx)" })).toBeDisabled();
    expect(screen.getByRole("heading", { name: "Ainda não há propostas para rever" })).toBeInTheDocument();
  });
});
