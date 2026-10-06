import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { setDevUser } from "../api/client";
import type { ProjectEquipment } from "../api/types";
import { alternative, detail, projectEquipment, slot, slotDetail, summary } from "../test/equipment";
import { project } from "../test/fixtures";
import { renderAt } from "../test/render";
import { api, server } from "../test/server";

function serve(equipment: ProjectEquipment = projectEquipment()) {
  const puts: unknown[] = [];
  server.use(
    http.get(api("/projects/p1"), () => HttpResponse.json(project())),
    http.get(api("/projects/p1/equipment"), () => HttpResponse.json(equipment)),
    http.get(api("/project-equipment/s1"), () => HttpResponse.json(slotDetail())),
    http.get(api("/project-equipment/s2"), () =>
      HttpResponse.json({ ...equipment.slots[1], alternatives: [] }),
    ),
    http.get(api("/equipment"), () => HttpResponse.json([summary(), summary({ id: "e2", params_reviewed: 3 })])),
    http.put(api("/project-equipment/s1"), async ({ request }) => {
      const body = (await request.json()) as { equipment_id: string; reason?: string };
      puts.push(body);
      return HttpResponse.json(
        slotDetail({ item: alternative, is_reference: body.equipment_id === "e1", chosen: true, verdict: "ok" }),
      );
    }),
  );
  return puts;
}

afterEach(() => setDevUser("redator"));

describe("equipment (screen F)", () => {
  it("says the CTE has to be assembled first", async () => {
    serve(projectEquipment({ document_id: null, document_status: null, slots: [] }));
    renderAt("/projetos/p1/equipamentos");

    expect(await screen.findByRole("heading", { name: "O CTE ainda não foi montado" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Montar o CTE" })).toHaveAttribute("href", "/projetos/p1/documentos");
  });

  it("lists the reference equipment with the quantity, the datasheet and why it fails", async () => {
    serve();
    renderAt("/projetos/p1/equipamentos");

    const table = await screen.findByRole("region", { name: "Equipamentos de referência do CTE" });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(3);
    expect(within(rows[1]!).getByText("IP44 < IP55")).toBeInTheDocument();
    expect(within(rows[2]!).getByText("L14 · Aplique exterior")).toBeInTheDocument();
    expect(within(rows[2]!).getByText("21 un")).toBeInTheDocument();
    expect(within(rows[2]!).getByText("Sem ficha")).toBeInTheDocument();
    expect(screen.getByText("1 não cumpre")).toBeInTheDocument();
    expect(screen.getByText("1 sem ficha")).toBeInTheDocument();
    expect(await screen.findByText("Biblioteca de equipamentos TUU")).toBeInTheDocument();
  });

  it("compares parameter by parameter and proposes the alternative that meets the CTE", async () => {
    serve();
    renderAt("/projetos/p1/equipamentos");

    const comparison = await screen.findByRole("region", { name: "Requisito do CTE contra a ficha do fabricante" });
    const row = within(comparison).getByRole("row", { name: /Índice de proteção/ });
    expect(within(row).getByText("≥ IP55")).toBeInTheDocument();
    expect(within(row).getByText("IP44")).toBeInTheDocument();
    expect(within(row).getByText("não cumpre")).toBeInTheDocument();
    expect(screen.getByText(/1 equipamento da biblioteca cumpre: Portinhola alternativa/)).toBeInTheDocument();
  });

  it("changes to an alternative only with a reason, and confirms the reference one", async () => {
    const puts = serve();
    const user = userEvent.setup();
    renderAt("/projetos/p1/equipamentos");

    await user.click(await screen.findByRole("button", { name: "Confirmar e incluir a imagem" }));
    await waitFor(() => expect(puts).toEqual([{ equipment_id: "e1" }]));

    await user.selectOptions(screen.getByLabelText(/Equipamento \(1 da mesma categoria\)/), "e2");
    const change = screen.getByRole("button", { name: "Trocar" });
    expect(change).toBeDisabled();
    await user.type(screen.getByLabelText(/Porque troca/), "Pedido do dono de obra.");
    await user.click(change);
    await waitFor(() => expect(puts).toHaveLength(2));
    expect(puts[1]).toEqual({ equipment_id: "e2", reason: "Pedido do dono de obra." });
  });

  it("selects another row and keeps it in the address", async () => {
    serve();
    const user = userEvent.setup();
    const { router } = renderAt("/projetos/p1/equipamentos");

    await user.click(await screen.findByRole("button", { name: "L14 · Aplique exterior" }));

    expect(router.state.location.search).toBe("?slot=s2");
    expect(await screen.findByRole("heading", { level: 3, name: "L14 · Aplique exterior" })).toBeInTheDocument();
    expect(screen.getByText(/Sem ficha técnica na biblioteca: peça-a ao curador/)).toBeInTheDocument();
  });

  it("is read only for the curator and on an approved CTE", async () => {
    setDevUser("curador");
    serve(projectEquipment({ document_status: "approved", slots: [slot()] }));
    renderAt("/projetos/p1/equipamentos");

    expect(await screen.findByText("CTE aprovado: só leitura")).toBeInTheDocument();
    await screen.findByRole("region", { name: "Requisito do CTE contra a ficha do fabricante" });
    expect(screen.queryByRole("button", { name: "Trocar" })).not.toBeInTheDocument();
    expect(screen.getByText("Só o redator e o técnico escolhem os equipamentos do projeto.")).toBeInTheDocument();
  });
});

describe("equipment library (screen G)", () => {
  it("starts empty and says how it is seeded", async () => {
    server.use(
      http.get(api("/equipment"), () => HttpResponse.json([])),
      http.get(api("/equipment/categories"), () => HttpResponse.json([])),
    );
    renderAt("/conhecimento?separador=equipamentos");

    expect(await screen.findByRole("heading", { name: "A biblioteca de equipamentos está vazia" })).toBeInTheDocument();
  });

  it("lets the curator review a parameter read from the datasheet", async () => {
    setDevUser("curador");
    const patches: unknown[] = [];
    server.use(
      http.get(api("/equipment"), () => HttpResponse.json([summary()])),
      http.get(api("/equipment/categories"), () => HttpResponse.json([{ id: "portinhola", label: "Portinhola" }])),
      http.get(api("/equipment/params"), () => HttpResponse.json([])),
      http.get(api("/equipment/e1"), () => HttpResponse.json(detail())),
      http.patch(api("/equipment/params/pa1"), async ({ request }) => {
        patches.push(await request.json());
        return HttpResponse.json(detail());
      }),
    );
    const user = userEvent.setup();
    renderAt("/conhecimento?separador=equipamentos");

    await user.click(await screen.findByRole("button", { name: "Portinhola de exemplo" }));
    const params = await screen.findByRole("region", { name: "Parâmetros da ficha técnica" });
    expect(within(params).getByText("Por rever")).toBeInTheDocument();
    expect(screen.getByText(/R9 ·/)).toBeInTheDocument();
    await user.type(within(params).getByLabelText("Corrigir Índice de proteção (IP)"), "IP54");
    await user.click(within(params).getByRole("button", { name: "Corrigir e rever Índice de proteção (IP)" }));

    await waitFor(() => expect(patches).toEqual([{ value: "IP54", page: null }]));
    expect(screen.getByLabelText(/Carregar ficha técnica/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aprovar Portinhola de exemplo" })).toBeEnabled();
  });

  it("is read only for the others", async () => {
    server.use(
      http.get(api("/equipment"), () => HttpResponse.json([summary()])),
      http.get(api("/equipment/categories"), () => HttpResponse.json([])),
      http.get(api("/equipment/e1"), () => HttpResponse.json(detail())),
    );
    renderAt("/conhecimento?separador=equipamentos&equipamento=e1");

    expect(await screen.findByText("Só um curador aprova, rejeita ou revê.")).toBeInTheDocument();
    expect(screen.queryByLabelText(/Carregar ficha técnica/)).not.toBeInTheDocument();
  });
});
