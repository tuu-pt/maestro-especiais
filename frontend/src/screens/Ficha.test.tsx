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
  length_m: "25",
  vd_total_pct: "0.8",
  breaking_capacity_ka: "6",
  installation: "ENT",
  phases: 3,
  source_ref: "Tabela!linha 3",
  cal01: { ib_in_iz: "ok", i2_iz145: "fail" },
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

  it("highlights circuits that fail a CAL-01 comparison without computing anything", async () => {
    serve(fichaWith([value({})], { circuits: [circuit({}), circuit({ id: "c2", origin: "Q.E.G.", destination: "Q.P.1", cal01: { ib_in_iz: "ok", i2_iz145: "ok" } })] }));
    renderAt("/projetos/p1/ficha");

    const table = await screen.findByRole("region", { name: "Troços da Tabela de Cálculo" });
    const [failing, passing] = within(table).getAllByText("504").map((e) => e.closest("td"));
    expect(failing).toHaveTextContent("(não cumpre I2 ≤ 1,45·Iz)");
    expect(passing).not.toHaveTextContent("não cumpre");
    expect(screen.getByText("CAL-01: 1 troço a confirmar na folha")).toBeInTheDocument();
    expect(screen.getByText(/aguarda|disponível quando houver MDJ/)).toBeInTheDocument();
  });
});
