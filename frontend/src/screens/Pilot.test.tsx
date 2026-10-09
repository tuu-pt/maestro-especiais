import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { setDevUser } from "../api/client";
import type { PilotProject } from "../api/types";
import { project } from "../test/fixtures";
import { renderAt } from "../test/render";
import { api, server } from "../test/server";
import { duration, percent } from "../lib/format";

const STEPS = [
  ["dados", "Juntar e conferir os dados de partida"],
  ["ficha", "Ficha eletrotécnica e ficha-base"],
  ["mdj", "Escrever a MDJ"],
  ["cte", "Escrever o CTE"],
  ["formularios", "Identificação, termo e ficha eletrotécnica"],
  ["verificacao", "Verificar a coerência entre peças"],
  ["correcoes", "Corrigir o que a revisão aponta"],
  ["conjunto", "Montar o conjunto final"],
] as const;

function pilot(over: Partial<PilotProject> = {}): PilotProject {
  return {
    project_id: "p1",
    code: "R9",
    typology: "habitação unifamiliar",
    steps: STEPS.map(([step, label]) => ({
      step,
      label,
      seconds: step === "mdj" ? 3600 : 0,
      estimate_min: step === "mdj" ? [100, 140] : null,
    })),
    seconds: 3600,
    estimate_seconds: 7200,
    reduction: 0.5,
    has_estimate: true,
    rounds_estimate: 2,
    errors_estimate: null,
    approvals: [
      {
        document: "MDJ",
        revision: "A",
        approved_at: "2026-10-09T10:00:00Z",
        groups: {
          identificacao: { found: 1, open: 0, ignored: 0 },
          potencia: { found: 0, open: 0, ignored: 0 },
          cabos: { found: 2, open: 0, ignored: 1 },
        },
        clean: false,
      },
    ],
    goal: { reduction: 0.5, time_ok: true, approved: true, coherent: false, met: false },
    notes_open: 1,
    notes_total: 1,
    baseline: {
      steps: { mdj: [100, 140] },
      rounds: 2,
      errors: null,
      typology: "habitação unifamiliar",
      updated_by: "dev:tecnico",
      updated_at: "2026-10-09T08:00:00Z",
    },
    notes: [
      {
        id: "n1",
        project_id: "p1",
        screen: "documentos",
        step: "cte",
        text: "O bloco da introdução repete a obra.",
        status: "open",
        created_by: "dev:redator",
        created_at: "2026-10-09T09:00:00Z",
        resolved_by: null,
        resolved_at: null,
      },
    ],
    ...over,
  };
}

function withPilot(data: PilotProject = pilot()) {
  server.use(
    http.get(api("/projects/p1"), () => HttpResponse.json(project())),
    http.get(api("/projects/p1/pilot"), () => HttpResponse.json(data)),
  );
}

afterEach(() => setDevUser("redator"));

describe("pilot screen (Phase 8)", () => {
  it("says how a project enters the pilot when there is none", async () => {
    renderAt("/piloto");
    expect(await screen.findByRole("heading", { name: "Ainda não há projetos no piloto" })).toBeInTheDocument();
  });

  it("shows the time per step against the estimate, the goal and the incoherences", async () => {
    withPilot();
    renderAt("/projetos/p1/piloto");

    const times = await screen.findByRole("region", { name: "Tempo por passo" });
    const mdj = within(times).getByRole("row", { name: /Escrever a MDJ/ });
    expect(mdj).toHaveTextContent("60 min");
    expect(mdj).toHaveTextContent("100–140 min");
    expect(screen.getByText("Tempo: 50 % de redução (meta ≥ 40 %)")).toBeInTheDocument();
    expect(screen.getByText("Coerência: há incoerências na aprovação")).toBeInTheDocument();
    const approvals = screen.getByRole("region", { name: "Incoerências na aprovação" });
    expect(within(approvals).getByRole("row", { name: /MDJ · rev\. A/ })).toHaveTextContent(
      "2 encontradas · 0 abertas · 1 ignoradas",
    );
    expect(screen.getByText("O bloco da introdução repete a obra.")).toBeInTheDocument();
  });

  it("lets the technician write the estimate, step by step in minutes", async () => {
    setDevUser("tecnico");
    withPilot();
    const sent: unknown[] = [];
    server.use(
      http.put(api("/projects/p1/pilot/baseline"), async ({ request }) => {
        sent.push(await request.json());
        return HttpResponse.json(pilot().baseline);
      }),
    );
    renderAt("/projetos/p1/piloto");

    await userEvent.type(await screen.findByLabelText("Escrever o CTE: mínimo (min)"), "80");
    expect(screen.getByRole("button", { name: "Guardar estimativa" })).toBeDisabled(); // a maximum too
    await userEvent.type(screen.getByLabelText("Escrever o CTE: máximo (min)"), "100");
    await userEvent.click(screen.getByRole("button", { name: "Guardar estimativa" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Guardada.");
    expect(sent).toEqual([
      { steps: { mdj: [100, 140], cte: [80, 100] }, rounds: 2, errors: null, typology: "habitação unifamiliar" },
    ]);
  });

  it("does not let the writer change the estimate", async () => {
    withPilot();
    renderAt("/projetos/p1/piloto");

    expect(await screen.findByLabelText("Escrever a MDJ: mínimo (min)")).toBeDisabled();
    expect(screen.getByText("Só o técnico responsável ou o administrador escreve a estimativa.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Marcar como resolvido" })).not.toBeInTheDocument();
  });

  it("writes a problem from any screen, with the project and the screen", async () => {
    withPilot();
    const sent: unknown[] = [];
    server.use(
      http.post(api("/pilot/notes"), async ({ request }) => {
        sent.push(await request.json());
        return HttpResponse.json(pilot().notes[0], { status: 201 });
      }),
    );
    renderAt("/projetos/p1/piloto");

    await userEvent.click(await screen.findByRole("button", { name: "Registar problema" }));
    const dialog = screen.getByRole("dialog", { name: "Registar problema do piloto" });
    await userEvent.type(within(dialog).getByRole("textbox"), "Alerta de cabos errado.");
    await userEvent.click(within(dialog).getByRole("button", { name: "Registar" }));

    await expect.poll(() => sent).toEqual([
      { text: "Alerta de cabos errado.", screen: "piloto", project_id: "p1", hint: null },
    ]);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("formats durations and percentages in Portuguese", () => {
    expect(duration(45 * 60)).toBe("45 min");
    expect(duration(2 * 3600)).toBe("2,0 h");
    expect(duration(null)).toBe("—");
    expect(percent(0.416)).toBe("42 %");
  });
});
