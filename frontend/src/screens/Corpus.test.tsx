import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { setDevUser } from "../api/client";
import type { Regulation } from "../api/types";
import { renderAt } from "../test/render";
import { api, server } from "../test/server";

function regulation(over: Partial<Regulation> = {}): Regulation {
  return {
    id: "g1",
    code: "rtiebt",
    title: "RTIEBT: Portaria n.º 949-A/2006, na redação atual",
    kind: "diploma",
    edition: null,
    issuer: "Governo",
    scope: "Regras Técnicas das Instalações Elétricas de Baixa Tensão.",
    status: null,
    citable: false,
    copyrighted: false,
    license_note: null,
    last_checked_at: null,
    review_status: "proposed",
    reviewed_by: null,
    reviewed_at: null,
    review_note: null,
    found_in: [
      { project: "R1", source: "MDJ", file: "MDJ.docx", locator: "parágrafo 44", text: "…conforme as RTIEBT…" },
    ],
    found_count: 12,
    ...over,
  };
}

const norm = regulation({
  id: "g2",
  code: "np-en-60529",
  title: "NP EN 60529",
  kind: "norma",
  issuer: "IPQ / CENELEC",
  scope: "Graus de proteção dos invólucros (códigos IP).",
  copyrighted: true,
  license_note: "Norma com direitos de autor: guarda-se só o título e o âmbito.",
  found_in: [],
  found_count: 0,
});

afterEach(() => setDevUser("redator"));

describe("regulation corpus (screen G)", () => {
  it("starts empty", async () => {
    renderAt("/conhecimento?separador=corpus");
    expect(await screen.findByRole("heading", { name: "Ainda não há documentos no corpus" })).toBeInTheDocument();
  });

  it("shows each reference as proposed and not citable, with where it is cited", async () => {
    server.use(http.get(api("/knowledge/regulations"), () => HttpResponse.json([regulation(), norm])));
    renderAt("/conhecimento?separador=corpus");

    const rtiebt = await screen.findByRole("listitem", { name: /RTIEBT/ });
    expect(within(rtiebt).getByText("A confirmar")).toBeInTheDocument();
    expect(within(rtiebt).getByText("Não citável")).toBeInTheDocument();
    expect(within(rtiebt).getByText("Citado 12 vezes nos projetos de referência")).toBeInTheDocument();
    const standard = screen.getByRole("listitem", { name: "NP EN 60529" });
    expect(within(standard).getByText(/guarda-se só o título e o âmbito/)).toBeInTheDocument();
    expect(within(standard).getByText("Não aparece nos documentos de referência (R1, R2).")).toBeInTheDocument();
    expect(screen.getAllByText("Só um curador pode confirmar, rejeitar ou marcar como citável.")).toHaveLength(2);
  });

  it("lets the curator confirm with the legal status, and only then cite", async () => {
    setDevUser("curador");
    let sent: unknown = null;
    server.use(
      http.get(api("/knowledge/regulations"), () => HttpResponse.json([regulation()])),
      http.post(api("/knowledge/regulations/g1/review"), async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json(regulation({ review_status: "confirmed", status: "in_force" }));
      }),
    );
    renderAt("/conhecimento?separador=corpus");

    const card = await screen.findByRole("listitem", { name: /RTIEBT/ });
    const confirm = await within(card).findByRole("button", { name: /^Confirmar RTIEBT/ });
    expect(confirm).toBeDisabled(); // the legal status first
    expect(within(card).getByRole("button", { name: /^Marcar como citável/ })).toBeDisabled();
    await userEvent.selectOptions(within(card).getByLabelText("Estado do documento"), "in_force");
    await userEvent.type(within(card).getByLabelText("Edição em vigor"), "na redação atual");
    await userEvent.click(confirm);

    await expect
      .poll(() => sent)
      .toEqual({ decision: "confirmed", status: "in_force", edition: "na redação atual", note: "" });
  });
});
