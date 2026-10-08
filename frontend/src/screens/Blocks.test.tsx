import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { setDevUser } from "../api/client";
import type { BlockDetail, BlockPreview, BlockSummary } from "../api/types";
import { project } from "../test/fixtures";
import { renderAt } from "../test/render";
import { api, server } from "../test/server";

const review = { status: "proposed", reviewed_by: null, reviewed_at: null, review_note: null } as const;

function summary(over: Partial<BlockSummary> = {}): BlockSummary {
  return {
    id: "b1",
    key: "ele.mdj.instalacao_de_alimentacao.alimentacao_de_energia",
    doc_type: "MDJ",
    kind: "block",
    level: 2,
    title: "Alimentação de Energia",
    order: 9,
    mode: "adaptive",
    activation_rule: "true",
    projects: ["R1", "R2"],
    required_keys: ["ele.potencia_alimentar_kva"],
    notes: ["Texto diferente em R1 e R2."],
    version: 1,
    ...review,
    ...over,
  };
}

function detail(): BlockDetail {
  return {
    ...summary(),
    entries: [
      {
        mode: "fixed",
        project: "R1",
        units: { R1: [0], R2: [0] },
        text: "Alimentação de Energia",
        keys: [],
        single_source: false,
        note: null,
      },
      {
        mode: "adaptive",
        project: "R1",
        units: { R1: [1], R2: [1] },
        text: null,
        keys: [],
        single_source: false,
        note: "Texto diferente em R1 e R2.",
      },
      {
        mode: "parametric",
        project: "R1",
        units: { R1: [5] },
        text: "Prevê-se uma potência de {{v:ele.potencia_alimentar_kva}} kVA.",
        keys: ["ele.potencia_alimentar_kva"],
        single_source: true,
        note: "Só em R1: os valores da ficha foram trocados por marcadores, com evidência de um só projeto.",
      },
    ],
    evidence: {
      R1: [
        { index: 0, kind: "paragraph", text: "Alimentação de Energia" },
        { index: 1, kind: "paragraph", text: "A entrada foi dimensionada de forma a garantir…" },
        { index: 5, kind: "paragraph", text: "Prevê-se uma potência de {{v:ele.potencia_alimentar_kva}} kVA." },
      ],
      R2: [
        { index: 0, kind: "paragraph", text: "Alimentação de Energia" },
        { index: 1, kind: "paragraph", text: "A entrada de energia será mantida…" },
      ],
    },
    labels: { "ele.potencia_alimentar_kva": "Potência a alimentar" },
    archive_refs: ["arc:R1:ele.mdj.x", "arc:R2:ele.mdj.x"],
    equipment_slots: [{ entry: 2, reasons: ["ou equivalente"], projects: ["R1"] }],
  };
}

const preview: BlockPreview = {
  project_id: "p1",
  project_code: "R9",
  active: true,
  rule_error: null,
  paragraphs: [
    { mode: "fixed", text: "Alimentação de Energia", missing: [], masked: [] },
    { mode: "adaptive", text: null, missing: [], masked: [] },
    { mode: "parametric", text: "Prevê-se uma potência de 34,5 kVA.", missing: [], masked: [] },
  ],
};

function withBlocks() {
  server.use(
    http.get(api("/library/blocks"), () =>
      HttpResponse.json([summary(), summary({ id: "b2", key: "ele.cte.x", doc_type: "CTE", title: "Cabos" })]),
    ),
    http.get(api("/library/blocks/b1"), () => HttpResponse.json(detail())),
    http.get(api("/library/blocks/b1/history"), () => HttpResponse.json([])),
    http.get(api("/projects"), () => HttpResponse.json([project()])),
    http.get(api("/library/blocks/b1/preview"), () => HttpResponse.json(preview)),
  );
}

afterEach(() => setDevUser("redator"));

describe("block library (screen G)", () => {
  it("starts empty and says where the blocks come from", async () => {
    renderAt("/conhecimento?separador=blocos");

    expect(await screen.findByRole("heading", { name: "Ainda não há blocos propostos" })).toBeInTheDocument();
  });

  it("lists the blocks of one document and opens one with its evidence side by side", async () => {
    withBlocks();
    renderAt("/conhecimento?separador=blocos");

    const list = await screen.findByRole("list", { name: "Blocos do MDJ" });
    expect(within(list).getAllByRole("button")).toHaveLength(1); // the CTE block is in the other tab
    await userEvent.click(within(list).getByRole("button", { name: /Alimentação de Energia/ }));

    const article = await screen.findByRole("article", { name: "Alimentação de Energia" });
    // the template and the evidence of R1 both show the placeholder, highlighted
    expect(within(article).getAllByText("Potência a alimentar", { selector: "mark" })).toHaveLength(2);
    expect(within(article).getByText("evidência de um só projeto")).toBeInTheDocument();
    expect(within(article).getByText("equipamento de referência (ou equivalente)")).toBeInTheDocument();
    const sides = within(article).getAllByLabelText("Evidência lado a lado");
    expect(sides).toHaveLength(2); // the adaptive and the parametric paragraphs, not the equal title
    expect(within(sides[0]!).getByText("A entrada de energia será mantida…")).toBeInTheDocument();
    expect(within(article).getByText("Texto diferente em R1 e R2.", { selector: "li" })).toBeInTheDocument();
    expect(within(article).getByText("Só um curador pode aprovar, editar ou rejeitar blocos.")).toBeInTheDocument();
  });

  it("previews the block with the ficha of a project and the rule evaluated", async () => {
    withBlocks();
    renderAt("/conhecimento?separador=blocos&bloco=b1");

    await userEvent.selectOptions(await screen.findByLabelText("Projeto"), "p1");

    expect(await screen.findByText("Prevê-se uma potência de 34,5 kVA.")).toBeInTheDocument();
    expect(screen.getByText("A regra ativa este bloco em R9")).toBeInTheDocument();
    expect(screen.getByText("[texto adaptativo: escrito na Fase 4]")).toBeInTheDocument();
  });

  it("lets a curator approve, and edit with a reason", async () => {
    setDevUser("curador");
    withBlocks();
    const sent: unknown[] = [];
    server.use(
      http.post(api("/library/blocks/b1/review"), async ({ request }) => {
        sent.push(await request.json());
        return HttpResponse.json(summary({ status: "approved" }));
      }),
      http.patch(api("/library/blocks/b1"), async ({ request }) => {
        sent.push(await request.json());
        return HttpResponse.json(
          { detail: { message: "Regra inválida: Falta a comparação depois de «sys.fv» (posição 7)", position: 6 } },
          { status: 422 },
        );
      }),
    );
    renderAt("/conhecimento?separador=blocos&bloco=b1");

    await userEvent.click(await screen.findByRole("button", { name: "Aprovar bloco" }));
    await expect.poll(() => sent).toEqual([{ decision: "approved", note: "" }]);

    await userEvent.click(screen.getByRole("button", { name: "Editar" }));
    const rule = screen.getByRole("textbox", { name: "Regra de ativação" });
    await userEvent.clear(rule);
    await userEvent.type(rule, "sys.fv");
    expect(screen.getByRole("button", { name: "Guardar alterações" })).toBeDisabled(); // a reason is required
    await userEvent.type(screen.getByLabelText("Porquê (obrigatório, fica registado)"), "Mais simples.");
    await userEvent.click(screen.getByRole("button", { name: "Guardar alterações" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Falta a comparação depois de «sys.fv» (posição 7)");
    expect(sent[1]).toEqual({ note: "Mais simples.", activation_rule: "sys.fv" });
  });

  it("lets a curator approve every proposal at once, with a reason", async () => {
    setDevUser("curador");
    withBlocks();
    const sent: unknown[] = [];
    server.use(
      http.post(api("/library/blocks/approve-all"), async ({ request }) => {
        sent.push(await request.json());
        return HttpResponse.json({
          approved: 1,
          requirements_approved: 0,
          skipped: [{ key: "ele.cte.x", title: "Cabos", doc_type: "CTE", why: "Regra de ativação inválida: x" }],
        });
      }),
    );
    renderAt("/conhecimento?separador=blocos");

    await userEvent.click(await screen.findByRole("button", { name: "Aprovar todas as propostas (2)" }));
    const go = screen.getByRole("button", { name: "Aprovar 2 blocos" });
    expect(go).toBeDisabled(); // a reason first
    await userEvent.type(screen.getByLabelText(/^Porquê \(obrigatório, pelo menos 10/), "Piloto: dadas como boas.");
    await userEvent.selectOptions(screen.getByLabelText("Que blocos"), "MDJ");
    await userEvent.click(screen.getByRole("button", { name: "Aprovar 1 bloco" }));

    expect(await screen.findByRole("status")).toHaveTextContent("1 bloco aprovado. Ficaram por aprovar: Cabos (CTE)");
    expect(sent).toEqual([{ reason: "Piloto: dadas como boas.", doc_type: "MDJ" }]);
  });

  it("does not offer it to whoever is not a curator", async () => {
    withBlocks();
    renderAt("/conhecimento?separador=blocos");

    await screen.findByRole("list", { name: "Blocos do MDJ" });
    expect(screen.queryByRole("button", { name: /Aprovar todas as propostas/ })).not.toBeInTheDocument();
  });
});
