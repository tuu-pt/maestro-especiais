import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";

import { setDevUser } from "../api/client";
import { confirmedFicha, forms, mdj, proposal, supplySection } from "../test/documents";
import { emptyFicha, project } from "../test/fixtures";
import { renderAt } from "../test/render";
import { api, server } from "../test/server";

function withProject(documents: unknown[] = [mdj()], ficha = confirmedFicha()) {
  server.use(
    http.get(api("/projects/p1"), () => HttpResponse.json(project())),
    http.get(api("/projects/p1/ficha"), () => HttpResponse.json(ficha)),
    http.get(api("/projects/p1/documents"), () => HttpResponse.json(documents)),
    http.get(api("/documents/d1"), () => HttpResponse.json(mdj())),
    http.get(api("/projects/p1/forms"), () => HttpResponse.json(forms())),
    http.get(
      api("/projects/p1/events"),
      () => new HttpResponse("", { headers: { "Content-Type": "text/event-stream" } }),
    ),
    http.get(api("/sections/:id/versions"), ({ params }) =>
      HttpResponse.json(
        params.id === "s-supply"
          ? [
              {
                ...proposal(),
                id: "v1",
                number: 1,
                status: "current",
                author_type: "system",
                content: supplySection().content,
              },
              proposal(),
            ]
          : [],
      ),
    ),
  );
}

afterEach(() => setDevUser("redator"));

describe("assisted editor (screen D)", () => {
  it("waits for a confirmed ficha-base", async () => {
    withProject([], emptyFicha());
    renderAt("/projetos/p1/documentos");
    expect(await screen.findByRole("heading", { name: "Ainda não há documentos" })).toBeInTheDocument();
    expect(screen.getByText("Ficha-base confirmada por um técnico responsável")).toBeInTheDocument();
  });

  it("shows a piece made by hand read-only, next to the assembled one", async () => {
    const existing = { ...mdj(), id: "d2", origin: "existing", source_file_id: "f9" };
    withProject([mdj(), existing]);
    server.use(http.get(api("/documents/d2"), () => HttpResponse.json(existing)));
    renderAt("/projetos/p1/documentos?doc=MDJ&origem=existente");

    expect(await screen.findByText(/Peça existente, carregada para auditoria: só leitura/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Existente (auditoria, só leitura)" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.queryByRole("button", { name: /Gerar texto adaptativo/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Editar" })).not.toBeInTheDocument();
  });

  it("offers to assemble the MDJ", async () => {
    withProject([]);
    let assembled: unknown = null;
    server.use(
      http.post(api("/projects/p1/documents"), async ({ request }) => {
        assembled = await request.json();
        return HttpResponse.json(mdj(), { status: 201 });
      }),
    );
    renderAt("/projetos/p1/documentos");

    await userEvent.click(await screen.findByRole("button", { name: "Montar o MDJ" }));

    await expect.poll(() => assembled).toEqual({ type: "MDJ" });
  });

  it("lists the sections with mode, state and whether the block is approved", async () => {
    withProject();
    renderAt("/projetos/p1/documentos");

    const nav = await screen.findByRole("navigation", { name: "Secções do MDJ" });
    const pv = within(nav).getByRole("button", { name: /INSTALAÇÃO FOTOVOLTAICA/ });
    expect(within(pv).getByText("Desativada")).toBeInTheDocument();
    expect(within(nav).getAllByText("não aprovado")).toHaveLength(3);
    expect(within(nav).getByRole("button", { name: /Quedas de Tensão/ })).toHaveTextContent("fixo");
  });

  it("shows why a section is inactive and lets a writer activate it with a reason", async () => {
    withProject();
    let sent: unknown = null;
    server.use(
      http.post(api("/sections/s-pv/activation"), async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({ active: true });
      }),
    );
    renderAt("/projetos/p1/documentos?doc=MDJ&seccao=s-pv");

    expect(await screen.findByText(/Sem «Fotovoltaico» na ficha-base/)).toBeInTheDocument();
    const reason = screen.getByLabelText("Justificação para ativar (fica registada)");
    await userEvent.type(reason, "Painéis previstos pelo dono de obra.");
    await userEvent.click(screen.getByRole("button", { name: "Ativar com justificação" }));

    await expect.poll(() => sent).toEqual({ active: true, reason: "Painéis previstos pelo dono de obra." });
  });

  it("protects fixed blocks: unlocking needs a reason", async () => {
    withProject();
    renderAt("/projetos/p1/documentos?doc=MDJ&seccao=s-fixed");

    expect(await screen.findByText("Bloco fixo: copiado com o OOXML original e protegido.")).toBeInTheDocument();
    expect(screen.getByText("As quedas de tensão não excedem os limites das RTIEBT.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Desbloquear" })).toBeDisabled();
  });

  it("shows the agent's proposal as a diff and accepts it", async () => {
    withProject();
    let decided = "";
    server.use(
      http.post(api("/versions/v2/accept"), () => {
        decided = "accept";
        return HttpResponse.json(proposal());
      }),
    );
    renderAt("/projetos/p1/documentos?doc=MDJ&seccao=s-supply");

    const panel = await screen.findByRole("region", { name: "Proposta do agente" });
    expect(
      within(panel).getByText("A entrada foi dimensionada para garantir a segurança.", { selector: "ins" }),
    ).toBeInTheDocument();
    expect(within(panel).getByText("Faltam: ele.n_pisos.")).toBeInTheDocument();
    await userEvent.click(within(panel).getByRole("button", { name: "Aceitar proposta" }));

    await expect.poll(() => decided).toBe("accept");
    // the value from the ficha-base is marked in the text, with its label
    const value = document.querySelector('[data-value="ele.potencia_alimentar_kva"]');
    expect(value).toHaveTextContent("34,5");
    expect(value).toHaveAttribute("title", "Ficha-base · Potência a alimentar");
  });

  it("sends a request in natural language to the agent", async () => {
    withProject();
    let sent: unknown = null;
    server.use(
      http.post(api("/sections/s-supply/requests"), async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({ queued: 1 }, { status: 202 });
      }),
    );
    renderAt("/projetos/p1/documentos?doc=MDJ&seccao=s-supply");

    await userEvent.type(
      await screen.findByLabelText(/Pedido em linguagem natural/),
      "Reescreve para concurso público.",
    );
    await userEvent.click(screen.getByRole("button", { name: "Enviar pedido" }));

    await expect.poll(() => sent).toEqual({ text: "Reescreve para concurso público." });
  });

  it("asks to confirm when a value from the ficha-base changed", async () => {
    withProject();
    const bodies: { confirm_values: boolean }[] = [];
    server.use(
      http.put(api("/sections/s-supply/content"), async ({ request }) => {
        const body = (await request.json()) as { confirm_values: boolean };
        bodies.push(body);
        if (!body.confirm_values) {
          return HttpResponse.json(
            { detail: { message: "Confirme a alteração de valores que vêm da ficha-base.", anchors: ["e5-v0"] } },
            { status: 409 },
          );
        }
        return HttpResponse.json({ version: 3, values_changed: 1 });
      }),
    );
    renderAt("/projetos/p1/documentos?doc=MDJ&seccao=s-supply");

    await userEvent.click(await screen.findByRole("button", { name: "Editar" }));
    await userEvent.click(screen.getByRole("button", { name: "Guardar" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent("COE-01");
    await userEvent.click(within(dialog).getByRole("button", { name: "Confirmar a alteração dos valores" }));

    await expect.poll(() => bodies.map((b) => b.confirm_values)).toEqual([false, true]);
  });

  it("offers the pre-filled forms and downloads them as the current user", async () => {
    withProject();
    let who: string | null = null;
    server.use(
      http.get(api("/projects/p1/forms/termo"), ({ request }) => {
        who = request.headers.get("X-Dev-User");
        return new HttpResponse("docx");
      }),
    );
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:termo", revokeObjectURL: () => {} }));
    renderAt("/projetos/p1/documentos?doc=MDJ&seccao=s-supply");

    const panel = await screen.findByRole("region", { name: "Formulários pré-preenchidos" });
    expect(within(panel).getByText(/Saem sem data nem assinatura/)).toBeInTheDocument();
    expect(within(panel).getByText("Por preencher: Data e assinatura do técnico responsável")).toBeInTheDocument();
    await userEvent.click(within(panel).getByRole("button", { name: "Termo de Responsabilidade" }));

    await expect.poll(() => who).toBe("redator");
  });

  it("gives no editing to a curator", async () => {
    setDevUser("curador");
    withProject();
    renderAt("/projetos/p1/documentos?doc=MDJ&seccao=s-supply");
    await screen.findByRole("region", { name: "Proposta do agente" });
    expect(screen.queryByRole("button", { name: "Editar" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Aceitar proposta" })).not.toBeInTheDocument();
  });
});
