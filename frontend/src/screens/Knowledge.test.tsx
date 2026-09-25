import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { setDevUser } from "../api/client";
import type { Cables, Typology } from "../api/types";
import { renderAt } from "../test/render";
import { api, server } from "../test/server";

const proposed = { status: "proposed", reviewed_by: null, reviewed_at: null, review_note: null } as const;

function cables(): Cables {
  const occurrence = (project_code: string, source: string, raw_text: string, locator: string) => ({
    project_code,
    source,
    source_file: "file.xlsx",
    locator,
    raw_text,
    geometry: "5G10",
  });
  return {
    designations: [
      {
        id: "d1",
        canonical: "H07V-K",
        aliases: [],
        kind: "fio",
        flexible: true,
        occurrences: [occurrence("R1", "MDJ", "H07V-K", "parágrafo 88")],
        ...proposed,
      },
      {
        id: "d2",
        canonical: "XZ1(frt,zh)",
        aliases: [],
        kind: "cabo",
        flexible: null,
        occurrences: [
          occurrence("R2", "LPU", "XZ1(frt,zh) 5G10mm²", "LPU!linha 40"),
          occurrence("R2", "LPU", "XZ1(frt,zh) 5G6mm²", "LPU!linha 41"),
        ],
        ...proposed,
      },
    ],
    equivalences: [
      {
        id: "e1",
        a: "RZ1-K (AS)",
        b: "XZ1(frt,zh)",
        reason: "No mesmo projeto, a mesma secção aparece com as duas designações.",
        evidence: [
          {
            project: "R2",
            geometry: "5G10",
            a: { source: "Tabela", file: "Tabela.xlsx", locator: "Quadro!B12", raw_text: "RZ1-K (AS) 5G10" },
            b: { source: "LPU", file: "LPU.xlsx", locator: "LPU!linha 40", raw_text: "XZ1(frt,zh) 5G10mm²" },
          },
        ],
        ...proposed,
      },
    ],
  };
}

const typologies: Typology[] = [
  {
    id: "t1",
    name: "moradia unifamiliar",
    evidence: [{ project: "R1", source: "Ficha eletrotécnica", locator: "F23", text: "Unifamiliar" }],
    terms: [
      {
        id: "x1",
        term: "apartamento",
        relation: "incompatible",
        evidence: [
          { project: "R1", source: "CTE", file: "CTE.docx", locator: "parágrafo 120", text: "…cada apartamento…" },
        ],
        ...proposed,
      },
    ],
    ...proposed,
  },
];

afterEach(() => setDevUser("redator"));

describe("knowledge base (screen G)", () => {
  it("starts empty and says where the proposals come from", async () => {
    renderAt("/conhecimento");

    expect(await screen.findByRole("heading", { name: "Ainda não há designações de cabos" })).toBeInTheDocument();
    expect(screen.getByText(/make seed-library/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Léxico de tipologias" }));
    expect(await screen.findByRole("heading", { name: "Ainda não há tipologias no léxico" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Biblioteca de blocos" }));
    expect(screen.getByRole("heading", { name: "Ainda não há blocos propostos" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Corpus regulamentar" }));
    expect(screen.getByRole("heading", { name: "Ainda não há documentos no corpus" })).toBeInTheDocument();
  });

  it("moves between tabs with the arrow keys", async () => {
    renderAt("/conhecimento");
    const first = await screen.findByRole("tab", { name: "Dicionário de cabos" });
    expect(first).toHaveAttribute("aria-selected", "true");

    first.focus();
    await userEvent.keyboard("{ArrowRight}");

    const second = screen.getByRole("tab", { name: "Léxico de tipologias" });
    expect(second).toHaveAttribute("aria-selected", "true");
    expect(second).toHaveFocus();
    await userEvent.keyboard("{ArrowLeft}{ArrowLeft}");
    expect(screen.getByRole("tab", { name: "Arquivo TUU" })).toHaveFocus();
  });

  it("shows each designation as written and where, and the evidence of a proposal side by side", async () => {
    server.use(http.get(api("/knowledge/cables"), () => HttpResponse.json(cables())));

    renderAt("/conhecimento");

    const table = await screen.findByRole("region", { name: "Designações de cabos encontradas" });
    expect(within(table).getByText("R2 · LPU (2)")).toBeInTheDocument();
    expect(within(table).getByText("Flexível")).toBeInTheDocument();
    expect(within(table).getByText("2 ocorrências")).toBeInTheDocument();
    const evidence = screen.getByRole("list", { name: "Evidência de RZ1-K (AS) ≈ XZ1(frt,zh)" });
    expect(within(evidence).getByText("RZ1-K (AS) 5G10")).toBeInTheDocument();
    expect(within(evidence).getByText("Tabela · Tabela.xlsx · Quadro!B12")).toBeInTheDocument();
    expect(screen.getAllByText("Proposto").length).toBeGreaterThan(0);
  });

  it("gives the decision only to a curator", async () => {
    server.use(http.get(api("/knowledge/cables"), () => HttpResponse.json(cables())));

    renderAt("/conhecimento");

    expect(await screen.findByText("Só um curador pode aprovar ou rejeitar.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Aprovar/ })).not.toBeInTheDocument();
  });

  it("sends the curator's decision with the note", async () => {
    setDevUser("curador");
    let sent: unknown = null;
    server.use(
      http.get(api("/knowledge/typologies"), () => HttpResponse.json(typologies)),
      http.post(api("/knowledge/typology-terms/x1/review"), async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({ ...proposed, status: "rejected" });
      }),
    );

    renderAt("/conhecimento?separador=lexico");

    expect(await screen.findByText("…cada apartamento…")).toBeInTheDocument();
    expect(screen.getByText(/CTE · CTE.docx · parágrafo 120/)).toBeInTheDocument();
    const notes = await screen.findAllByLabelText("Nota do curador (opcional, fica registada)");
    await userEvent.type(notes[1]!, "Termo genérico, aparece por engano.");
    await userEvent.click(
      screen.getByRole("button", { name: "Rejeitar o termo apartamento para moradia unifamiliar" }),
    );

    await expect.poll(() => sent).toEqual({ decision: "rejected", note: "Termo genérico, aparece por engano." });
  });
});
