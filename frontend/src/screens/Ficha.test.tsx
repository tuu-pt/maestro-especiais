import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { setDevUser } from "../api/client";
import type { Circuit, Ficha, FichaValue } from "../api/types";
import { emptyFicha, project } from "../test/fixtures";
import { renderAt } from "../test/render";
import { api, server } from "../test/server";

const value = (over: Partial<FichaValue>): FichaValue => ({
  id: "v1",
  key: "ele.potencia_instalada_kva",
  label: "Potência instalada",
  value: 34.5,
  unit: "kVA",
  masked: false,
  personal_data: false,
  status: "pending",
  source_type: "ficha_eletrotecnica",
  source_ref: "Ficha Eletrotecnica!P29",
  source_file: "FE.xlsm",
  conflict: null,
  ...over,
});

const circuit = (over: Partial<Circuit>): Circuit => ({
  id: "c1",
  row_index: 3,
  section: "ENTRADA DE ENERGIA",
  origin: "Portinhola",
  destination: "Q.E.G.",
  kva: "200",
  ib_a: "50",
  in_a: "63",
  idn_ma: null,
  iz_a: "347.17",
  i2_a: "504",
  iz145_a: "503.4",
  cable_raw: "XZ1(frt,zh) 4x16",
  section_mm2: "16",
  length_m: "25",
  vd_section_pct: "0.8",
  vd_total_pct: "0.8",
  breaking_capacity_ka: "6",
  installation: "ENT",
  phases: 3,
  source_ref: "Tabela!linha 3",
  cal01: { ib_in_iz: "ok", i2_iz145: "fail" },
  conflicts: [],
  ...over,
});

function fichaWith(values: FichaValue[], over: Partial<Ficha> = {}): Ficha {
  const base = emptyFicha();
  const revision = { id: "r1", label: "A", status: "draft" as const, confirmed_by: null, confirmed_at: null, created_at: "2026-09-24T10:00:00Z" };
  return {
    ...base,
    revision,
    revisions: [revision],
    groups: base.groups.map((g) => ({ ...g, values: values.filter((v) => groupOf(v) === g.name) })),
    open_conflicts: values.filter((v) => v.conflict).length,
    can_confirm: values.length > 0 && !values.some((v) => v.conflict),
    ...over,
  };
}

const groupOf = (v: FichaValue) => (v.key.startsWith("id.") ? "Identificação" : "Alimentação");

const conflictValue = value({
  id: "v2",
  key: "ele.potencia_alimentar_kva",
  label: "Potência a alimentar",
  value: null,
  status: "conflict",
  conflict: {
    id: "k1",
    candidates: [
      { value: 180, source_type: "ficha_eletrotecnica", source_ref: "Ficha Eletrotecnica!R29", source_file: "FE.xlsm", file_date: "2026-09-24T10:01:00Z" },
      { value: 200, source_type: "calc", source_ref: "Tabela!linha 3", source_file: "Tabela.xlsx", file_date: "2026-09-24T10:02:00Z" },
    ],
  },
});

function serve(ficha: Ficha) {
  server.use(
    http.get(api("/projects/p1"), () => HttpResponse.json(project())),
    http.get(api("/projects/p1/ficha"), () => HttpResponse.json(ficha)),
  );
}

describe("ficha do projeto", () => {
  it("asks for the ficha eletrotécnica and the Tabela de Cálculo when there is no ficha-base", async () => {
    serve(emptyFicha());
    renderAt("/projetos/p1/ficha");

    expect(await screen.findByText("Carregue a ficha eletrotécnica e a Tabela de Cálculo para criar a ficha-base.")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Carregar ficheiros" })[0]).toHaveAttribute("href", "/projetos/p1/ficheiros");
  });

  it("shows each value with its origin and masks personal data until asked", async () => {
    let revealedId = "";
    serve(
      fichaWith([
        value({}),
        value({ id: "v9", key: "id.requerente.nome", label: "Requerente", value: "•••", unit: null, masked: true, personal_data: true, source_ref: "Ficha Eletrotecnica!C5" }),
      ]),
    );
    server.use(
      http.post(api("/ficha/values/:id/reveal"), ({ params }) => {
        revealedId = String(params.id);
        return HttpResponse.json(value({ id: "v9", value: "Nome revelado", unit: null, masked: false }));
      }),
    );
    renderAt("/projetos/p1/ficha");

    expect(await screen.findByRole("heading", { name: "Ficha-base · rev. A" })).toBeInTheDocument();
    expect(screen.getByText("34,5 kVA")).toBeInTheDocument();
    expect(screen.getByLabelText("FICHA ELE: FE.xlsm · Ficha Eletrotecnica!P29")).toBeInTheDocument();
    expect(screen.queryByText("Nome revelado")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Mostrar" }));

    expect(await screen.findByText("Nome revelado")).toBeInTheDocument();
    expect(revealedId).toBe("v9");
  });

  it("lets only the técnico resolve a conflict, with a note", async () => {
    serve(fichaWith([value({}), conflictValue]));
    renderAt("/projetos/p1/ficha");
    const box = await screen.findByRole("region", { name: "Potência a alimentar: as fontes não coincidem" });
    expect(within(box).getByText("Só um técnico responsável pode resolver conflitos.")).toBeInTheDocument();
    expect(within(box).getByRole("button", { name: /180 kVA/ })).toBeDisabled();
  });

  it("sends the chosen candidate and the justification", async () => {
    setDevUser("tecnico");
    let body: unknown = null;
    serve(fichaWith([value({}), conflictValue]));
    server.use(
      http.post(api("/ficha/conflicts/k1/resolve"), async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(value({ id: "v2" }));
      }),
    );
    renderAt("/projetos/p1/ficha");
    const user = userEvent.setup();
    const box = await screen.findByRole("region", { name: /as fontes não coincidem/ });
    const confirmChoice = await within(box).findByRole("button", { name: "Confirmar escolha" });

    await user.click(within(box).getByRole("button", { name: /200 kVA/ }));
    expect(confirmChoice).toBeDisabled(); // a justification is required
    await user.type(within(box).getByLabelText("Justificação (fica registada)"), "Tabela de Cálculo atualizada");
    await user.click(confirmChoice);

    await waitFor(() => expect(body).toEqual({ candidate: 1, manual_value: null, note: "Tabela de Cálculo atualizada" }));
  });

  it("does not let anyone confirm while conflicts are open", async () => {
    setDevUser("tecnico");
    serve(fichaWith([value({}), conflictValue]));
    renderAt("/projetos/p1/ficha");

    expect(await screen.findByRole("button", { name: "Confirmar revisão A" })).toBeDisabled();
    expect(screen.getByText("Resolva primeiro os conflitos.")).toBeInTheDocument();
  });

  it("confirms the revision as técnico", async () => {
    setDevUser("tecnico");
    let confirmed = "";
    serve(fichaWith([value({})]));
    server.use(
      http.post(api("/ficha/revisions/:id/confirm"), ({ params }) => {
        confirmed = String(params.id);
        return HttpResponse.json({ id: "r1", label: "A", status: "confirmed" });
      }),
    );
    renderAt("/projetos/p1/ficha");
    const button = await screen.findByRole("button", { name: "Confirmar revisão A" });
    await waitFor(() => expect(button).toBeEnabled());

    await userEvent.click(button);
    await waitFor(() => expect(confirmed).toBe("r1"));
  });

  it("lets a técnico add a value no source gives, with a note", async () => {
    setDevUser("tecnico");
    let sent: unknown = null;
    const missing = [{ key: "id.obra.designacao", label: "Designação da obra", group: "Identificação", unit: null, numeric: false }];
    serve(fichaWith([value({})], { missing_keys: missing }));
    server.use(
      http.post(api("/projects/p1/ficha/values"), async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json(value({ key: "id.obra.designacao" }), { status: 201 });
      }),
    );
    renderAt("/projetos/p1/ficha");

    const card = (await screen.findByRole("heading", { name: "Valores em falta" })).closest("section")!;
    await userEvent.selectOptions(within(card).getByLabelText("Campo"), "id.obra.designacao");
    await userEvent.type(within(card).getByLabelText("Valor"), "Moradia em Coimbra");
    const add = within(card).getByRole("button", { name: "Acrescentar à ficha-base" });
    expect(add).toBeDisabled(); // the note is required
    await userEvent.type(within(card).getByLabelText("De onde vem o valor (fica registado)"), "Do cliente.");
    await userEvent.click(add);

    await waitFor(() =>
      expect(sent).toEqual({ key: "id.obra.designacao", value: "Moradia em Coimbra", note: "Do cliente." }),
    );
  });

  it("does not offer manual values to a redator", async () => {
    setDevUser("redator");
    const missing = [{ key: "id.local.cp", label: "Código postal", group: "Identificação", unit: null, numeric: false }];
    serve(fichaWith([value({})], { missing_keys: missing }));
    renderAt("/projetos/p1/ficha");
    await screen.findByRole("button", { name: "Confirmar revisão A" });
    expect(screen.queryByRole("heading", { name: "Valores em falta" })).not.toBeInTheDocument();
  });

  it("highlights circuits that fail a CAL-01 comparison without computing anything", async () => {
    serve(fichaWith([value({})], { circuits: [circuit({}), circuit({ id: "c2", origin: "Q.E.G.", destination: "Q.P.1", cal01: { ib_in_iz: "ok", i2_iz145: "ok" } })] }));
    renderAt("/projetos/p1/ficha");

    const table = await screen.findByRole("region", { name: "Troços da Tabela de Cálculo" });
    const [failing, passing] = within(table).getAllByText("504").map((e) => e.closest("td"));
    expect(failing).toHaveTextContent("(não cumpre I2 ≤ 1,45·Iz)");
    expect(passing).not.toHaveTextContent("não cumpre");
    expect(screen.getByText("CAL-01: 1 troço a confirmar na folha")).toBeInTheDocument();
    expect(screen.getByText(/verificados na validação/)).toBeInTheDocument();
  });
});

describe("ficha do projeto: 09-Folhas, MQT/LPU and drawings", () => {
  const sheetConflict = {
    id: "kc1",
    field: "in_a",
    label: "In",
    candidates: [
      { value: 315, source_type: "calc" as const, source_ref: "Tabela!linha 12", source_file: "Tabela.xlsx", file_date: null },
      { value: 250, source_type: "calc_sheet" as const, source_ref: "09-Folha ARM-QEG · proteccao!E9", source_file: "ARM-QEG.xls", file_date: null },
    ],
  };
  const sheet = (over: object = {}) => ({
    id: "s1", origin_hint: "ARM", destination_hint: "QEG", source_file: "ARM-QEG.xls", template: "TUU_09",
    values: { in_a: { value: 250, ref: "proteccao!E9" } }, circuit_ids: ["c1"], link_status: "rule" as const, ...over,
  }); // prettier-ignore
  const article = (over: object = {}) => ({
    id: "b1", variant: "lpu" as const, source_ref: "LPU!linha 41", source_file: "LPU.xlsx", code: "1.8.1.1",
    level: 4, kind: "article" as const, designation: "Q.E.G.", unit: "Un", quantity: "1", link_key: "ele.quadros",
    link_label: "Quadros", link_status: "rule" as const, link_rule: "board", ...over,
  }); // prettier-ignore

  it("lists circuit conflicts with the others and marks the cells that differ from the 09-Folha", async () => {
    setDevUser("tecnico");
    let body: unknown = null;
    serve(fichaWith([value({})], {
      circuits: [circuit({ conflicts: [sheetConflict] })], circuit_sheets: [sheet()], open_conflicts: 1, can_confirm: false,
    })); // prettier-ignore
    server.use(
      http.post(api("/ficha/conflicts/kc1/resolve"), async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(circuit({}));
      }),
    );
    renderAt("/projetos/p1/ficha");
    const user = userEvent.setup();

    expect(await screen.findByRole("heading", { name: "Conflitos por resolver (1)" })).toBeInTheDocument();
    // Conflicts of a circuit with its 09-Folha are grouped and folded: one line per circuit.
    expect(screen.queryByRole("region", { name: /Portinhola → Q.E.G. · In/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("heading", { name: "Portinhola → Q.E.G.: difere da 09-Folha" }));
    const box = screen.getByRole("region", { name: "Portinhola → Q.E.G. · In: as fontes não coincidem" });
    expect(within(box).getByText(/09-FOLHA · ARM-QEG.xls/)).toBeInTheDocument();
    const table = screen.getByRole("region", { name: "Troços da Tabela de Cálculo" });
    expect(within(table).getByText("(difere da 09-Folha)")).toBeInTheDocument();
    expect(within(table).getByLabelText(/^09-FOLHA: ARM-QEG.xls · In 250 A/)).toBeInTheDocument();

    await user.click(within(box).getByRole("button", { name: /250/ }));
    await user.type(within(box).getByLabelText("Justificação (fica registada)"), "Confirmado na folha");
    await user.click(within(box).getByRole("button", { name: "Confirmar escolha" }));
    await waitFor(() => expect(body).toEqual({ candidate: 1, manual_value: null, note: "Confirmado na folha" }));
  });

  it("links a 09-Folha that has no single circuit", async () => {
    let body: unknown = null;
    serve(fichaWith([value({})], {
      circuits: [circuit({}), circuit({ id: "c2", origin: "Q.P.EXTERIOR", destination: "CVE 1" })],
      circuit_sheets: [sheet({ id: "s2", origin_hint: "QPEXT", destination_hint: "CVE", source_file: "QPEXT-CVE.xls", circuit_ids: [], link_status: "unlinked" })],
    })); // prettier-ignore
    server.use(
      http.post(api("/circuit-sheets/s2/link"), async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(sheet({ id: "s2", link_status: "manual" }));
      }),
    );
    renderAt("/projetos/p1/ficha");
    const user = userEvent.setup();

    expect(await screen.findByRole("heading", { name: "09-Folhas por associar (1)" })).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Troço(s) da Tabela para QPEXT-CVE"), "c2");
    await user.click(screen.getByRole("button", { name: "Associar QPEXT-CVE" }));
    await waitFor(() => expect(body).toEqual({ circuit_ids: ["c2"] }));
  });

  it("lists the articles, shows the unlinked ones first and links one by hand", async () => {
    let body: unknown = null;
    serve(fichaWith([value({})], {
      bom_items: [
        article(),
        article({ id: "b2", code: "1.2.1.1", designation: "XAV 4(1x185)mm²", unit: "ml", quantity: "25", link_key: null, link_label: null, link_status: "unlinked", link_rule: null }),
        article({ id: "b3", code: "1", kind: "chapter", designation: "INSTALAÇÕES ELÉTRICAS", unit: null, quantity: null }),
      ],
      bom_link_keys: [{ key: "ele.cabos", label: "Cabos", group: "Distribuição" }, { key: "ele.quadros", label: "Quadros", group: "Distribuição" }],
    })); // prettier-ignore
    server.use(
      http.post(api("/bom-items/b2/link"), async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(article({ id: "b2", link_key: "ele.cabos", link_status: "manual" }));
      }),
    );
    renderAt("/projetos/p1/ficha");
    const user = userEvent.setup();

    // Folded by default, with the count in its title.
    expect(await screen.findByText("1 de 2 por associar")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Tabela dos artigos do LPU" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("heading", { name: "Artigos do LPU" }));
    const table = screen.getByRole("region", { name: "Tabela dos artigos do LPU" });
    expect(within(table).getByText("XAV 4(1x185)mm²")).toBeInTheDocument();
    expect(within(table).queryByText("Q.E.G.")).not.toBeInTheDocument(); // "Por associar" first
    expect(screen.getByRole("button", { name: "Por associar (1)" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "Todos (2)" })); // chapters are not articles
    expect(within(table).getByText("Quadros · por regra")).toBeInTheDocument();

    await user.selectOptions(within(table).getByLabelText(/Associação do artigo 1.2.1.1/), "ele.cabos");
    await waitFor(() => expect(body).toEqual({ key: "ele.cabos" }));
  });

  it("shows the index of the drawings and when it does not match the PDF (C4)", async () => {
    serve(fichaWith([
      value({ id: "p1", key: "pd.indice", label: "Índice das folhas", unit: null, source_type: "drawing", source_ref: "PDF · pág. 1 · índice",
        value: [{ codigo: "EL001", titulo: "ÍNDICE", data: "06/26", revisao: null }, { codigo: "EL002", titulo: "PISO 1", data: "06/26", revisao: null }] }),
    ], { drawings_check: { index_sheets: 2, pages: 1, missing_in_pdf: ["EL002"], not_in_index: [], matches: false } })); // prettier-ignore
    renderAt("/projetos/p1/ficha");

    expect(await screen.findByText("2 folhas (ver o índice abaixo)")).toBeInTheDocument();
    expect(screen.getByText("Índice e PDF não coincidem")).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("O índice lista 2 folhas e o PDF tem 1 página. Sem página no PDF: EL002.");
    const index = screen.getByRole("region", { name: "Folhas do índice" });
    expect(within(index).getByText("Sem página")).toBeInTheDocument();
  });
});

describe("long sections fold", () => {
  it("opens and closes, and the index stays closed when it matches the PDF", async () => {
    serve(fichaWith([
      value({ id: "p1", key: "pd.indice", label: "Índice das folhas", unit: null, source_type: "drawing",
        value: [{ codigo: "EL001", titulo: "ÍNDICE", data: "06/26", revisao: null }] }),
    ], { drawings_check: { index_sheets: 1, pages: 1, missing_in_pdf: [], not_in_index: [], matches: true } })); // prettier-ignore
    renderAt("/projetos/p1/ficha");
    const user = userEvent.setup();

    const heading = await screen.findByRole("heading", { name: "Índice das peças desenhadas" });
    expect(screen.getByText("Índice e PDF coincidem")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Folhas do índice" })).not.toBeInTheDocument();

    // The keyboard (Enter on the summary) is checked in a real browser: e2e/ficha-layout.spec.ts.
    await user.click(heading);
    expect(screen.getByRole("region", { name: "Folhas do índice" })).toBeInTheDocument();
    await user.click(heading);
    expect(screen.queryByRole("region", { name: "Folhas do índice" })).not.toBeInTheDocument();
  });
});
