import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { Validation } from "../api/types";
import { confirmedFicha, mdj } from "../test/documents";
import { emptyFicha, project } from "../test/fixtures";
import { renderAt } from "../test/render";
import { api, server } from "../test/server";
import { issue, personal, validation } from "../test/validation";

function withProject(state: Validation, ficha = confirmedFicha(), documents: unknown[] = [mdj()]) {
  server.use(
    http.get(api("/projects/p1"), () => HttpResponse.json(project())),
    http.get(api("/projects/p1/ficha"), () => HttpResponse.json(ficha)),
    http.get(api("/projects/p1/documents"), () => HttpResponse.json(documents)),
    http.get(api("/projects/p1/validation"), () => HttpResponse.json(state)),
    http.get(api("/projects/p1/events"), () => new HttpResponse("", { headers: { "Content-Type": "text/event-stream" } })),
  );
}

describe("validation (screen E)", () => {
  it("waits for a confirmed ficha-base and pieces", async () => {
    withProject({ ...validation(), ready: false, run: null, issues: [] }, emptyFicha(), []);
    renderAt("/projetos/p1/validacao");
    expect(
      await screen.findByRole("heading", {
        name: "A validação fica disponível quando houver ficha-base confirmada e peças do projeto",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/MDJ e CTE montados, ou carregados como peças existentes/)).toBeInTheDocument();
  });

  it("offers the first validation", async () => {
    let asked: unknown = null;
    withProject({ ...validation(), run: null, issues: [], matrix: {} });
    server.use(
      http.post(api("/projects/p1/validation"), async ({ request }) => {
        asked = await request.json();
        return HttpResponse.json({}, { status: 202 });
      }),
    );
    renderAt("/projetos/p1/validacao");
    await userEvent.click(await screen.findByRole("button", { name: "Validar o projeto" }));
    await expect.poll(() => asked).toEqual({ trigger: "full" });
  });

  it("shows the issues with their evidence, likely reading and actions", async () => {
    withProject(validation());
    renderAt("/projetos/p1/validacao");

    const list = await screen.findByRole("list", { name: "Alertas da validação" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("1 crítico")).toBeInTheDocument();
    const item = within(list).getByText(/N.º de carregadores/).closest("li")!;
    await userEvent.click(within(item).getByText(/N.º de carregadores/));
    expect(within(item).getByText("Erro provável no CTE.")).toBeInTheDocument();
    const evidence = within(item).getByRole("region", { name: "Evidência: valores comparados" });
    expect(within(evidence).getByText("ficha-base")).toBeInTheDocument();
    expect(within(item).getByRole("link", { name: "Abrir no editor" })).toHaveAttribute(
      "href",
      "/projetos/p1/documentos?doc=CTE&origem=existente",
    );
    expect(within(item).getByRole("link", { name: "Abrir na ficha" })).toHaveAttribute("href", "/projetos/p1/ficha");
  });

  it("filters by severity", async () => {
    withProject(validation());
    renderAt("/projetos/p1/validacao");
    const list = await screen.findByRole("list", { name: "Alertas da validação" });
    await userEvent.click(within(screen.getByRole("group", { name: "Severidade" })).getByRole("button", { name: "Crítico" }));
    expect(within(list).getAllByRole("listitem")).toHaveLength(1);
    expect(within(list).getByText(/sem o número da secção/)).toBeInTheDocument();
  });

  it("ignores an issue only with a justification", async () => {
    let body: unknown = null;
    withProject(validation());
    server.use(
      http.post(api("/validation/issues/i1/ignore"), async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(issue({ status: "ignored" }));
      }),
    );
    renderAt("/projetos/p1/validacao");
    const list = await screen.findByRole("list", { name: "Alertas da validação" });
    const item = within(list).getByText(/N.º de carregadores/).closest("li")!;
    await userEvent.click(within(item).getByText(/N.º de carregadores/));
    await userEvent.click(within(item).getByRole("button", { name: "Ignorar com justificação" }));
    const ignore = within(item).getByRole("button", { name: "Ignorar" });
    expect(ignore).toBeDisabled();
    await userEvent.type(within(item).getByLabelText(/Porque é que este alerta pode ser ignorado/), "Confirmado com o técnico.");
    await userEvent.click(ignore);
    await expect.poll(() => body).toEqual({ reason: "Confirmado com o técnico." });
  });

  it("never shows personal values, only that they differ", async () => {
    withProject(validation([personal()]));
    renderAt("/projetos/p1/validacao");
    await userEvent.click(await screen.findByText(/Dados do técnico diferentes/));
    const evidence = screen.getByRole("region", { name: "Evidência: valores comparados" });
    expect(within(evidence).getAllByLabelText("Dado pessoal mascarado")).toHaveLength(2);
    expect(screen.getByText("Confirmar com o perfil do técnico.")).toBeInTheDocument();
  });

  it("blocks sending the pieces for review while a critical issue is open", async () => {
    withProject(validation());
    renderAt("/projetos/p1/validacao");
    expect(await screen.findByText(/1 alerta crítico aberto: as peças não podem ser enviadas/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enviar as peças para revisão" })).toBeDisabled();
  });

  it("shows the coherence matrix with the ficha-base as reference", async () => {
    withProject(validation());
    renderAt("/projetos/p1/validacao");
    const matrix = await screen.findByRole("region", { name: "Matriz de coerência do projeto" });
    const row = within(matrix).getByRole("row", { name: /N.º de carregadores VE/ });
    expect(within(row).getAllByRole("cell").map((c) => c.textContent)).toContain("6 (diverge)");
    expect(within(row).getByText("Erro provável no CTE.")).toBeInTheDocument();
    expect(within(matrix).getByText("Coerente")).toBeInTheDocument();
  });
});
