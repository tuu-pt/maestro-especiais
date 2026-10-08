import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { setDevUser } from "../api/client";
import type { Approval, AuditEntry, ProjectExport } from "../api/types";
import { mdj } from "../test/documents";
import { project } from "../test/fixtures";
import { renderAt } from "../test/render";
import { approval, approvedWithHistory, diff, exportDone, readyApproval } from "../test/review";
import { api, server } from "../test/server";

const audit: AuditEntry[] = [
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
];

function serve({
  documents = [mdj()],
  card = approval(),
  exports = [],
}: { documents?: unknown[]; card?: Approval; exports?: ProjectExport[] } = {}) {
  server.use(
    http.get(api("/projects/p1"), () => HttpResponse.json(project())),
    http.get(api("/projects/p1/audit"), () => HttpResponse.json(audit)),
    http.get(api("/projects/p1/documents"), () => HttpResponse.json(documents)),
    http.get(api("/documents/d1"), () => HttpResponse.json(mdj())),
    http.get(api("/documents/d1/approval"), () => HttpResponse.json(card)),
    http.get(api("/documents/d1/diff"), () => HttpResponse.json(diff())),
    http.get(api("/projects/p1/exports"), () => HttpResponse.json(exports)),
    http.get(api("/sections/:id/versions"), () => HttpResponse.json([])),
  );
}

afterEach(() => setDevUser("redator"));

describe("review and export (screen H)", () => {
  it("says what is missing before there is anything to review", async () => {
    serve({ documents: [] });
    renderAt("/projetos/p1/revisao");

    expect(await screen.findByRole("heading", { name: "Ainda não há peças para rever" })).toBeInTheDocument();
    expect(await screen.findByText("Projeto R9 criado")).toBeInTheDocument();
  });

  it("shows each condition with its reason and where to resolve it", async () => {
    setDevUser("tecnico");
    serve();
    renderAt("/projetos/p1/revisao");

    const card = await screen.findByRole("list", { name: "Condições para aprovar" });
    expect(within(card).getByText(/1 secção por rever/)).toBeInTheDocument();
    expect(within(card).getByText(/2 blocos por aprovar/)).toBeInTheDocument();
    const links = within(card).getAllByRole("link", { name: "Resolver" });
    expect(links.map((l) => l.getAttribute("href"))).toEqual([
      "/projetos/p1/documentos?doc=MDJ&seccao=s-supply",
      "/conhecimento?separador=blocos",
    ]);
    expect(screen.getByRole("button", { name: "Aprovar MDJ" })).toBeDisabled();
    expect(screen.getByText("Há condições por cumprir.")).toBeInTheDocument();
  });

  it("lets the técnico assigned approve when every condition is met", async () => {
    setDevUser("tecnico");
    let card = readyApproval();
    serve();
    server.use(
      http.get(api("/documents/d1/approval"), () => HttpResponse.json(card)),
      http.post(api("/documents/d1/approve"), () => {
        card = approvedWithHistory();
        return HttpResponse.json(card);
      }),
    );
    renderAt("/projetos/p1/revisao");

    const button = await screen.findByRole("button", { name: "Aprovar MDJ" });
    await waitFor(() => expect(button).toBeEnabled());
    await userEvent.click(button);

    expect(await screen.findByRole("button", { name: "Reabrir MDJ" })).toBeDisabled(); // a reason first
    expect(screen.getByText(/Aprovada por Técnico responsável/)).toBeInTheDocument();
  });

  it("shows what changed since revision A, change by change", async () => {
    serve({ card: approvedWithHistory() });
    renderAt("/projetos/p1/revisao");

    const text = await screen.findByRole("region", { name: "Diferenças em «Alimentação de Energia»" });
    expect(text.querySelector("del")).toHaveTextContent("monofásica");
    expect(text.querySelector("ins")).toHaveTextContent("trifásica");
    expect(screen.getByText(/rev\. A · V0 · R00/)).toBeInTheDocument();
  });

  it("exports a draft at any time and the official set only with the pieces approved", async () => {
    let asked: unknown = null;
    serve({ exports: [exportDone()] });
    server.use(
      http.post(api("/projects/p1/exports"), async ({ request }) => {
        asked = await request.json();
        return HttpResponse.json(exportDone({ id: "e2", status: "queued" }), { status: 202 });
      }),
    );
    renderAt("/projetos/p1/revisao");

    expect(await screen.findByRole("button", { name: "Exportar conjunto oficial" })).toBeDisabled();
    expect(screen.getByText("O conjunto oficial precisa do MDJ e do CTE.")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Descarregar R9_Conjunto_RASCUNHO-nao-aprovado.zip" }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Exportar rascunho" }));

    await waitFor(() => expect(asked).toEqual({ kind: "draft", pdf: false }));
  });
});
