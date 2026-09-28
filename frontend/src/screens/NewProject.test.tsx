import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import type { ProjectFile } from "../api/types";
import { confirmedFicha } from "../test/documents";
import { emptyFicha, file, project, sse } from "../test/fixtures";
import { renderAt } from "../test/render";
import { api, server } from "../test/server";

// jsdom's FormData cannot go through Node's fetch: the upload call is replaced here and the
// real multipart request is exercised by the Playwright journey.
const uploaded: { projectId: string; name: string }[] = [];
let onUpload: () => void = () => undefined;
vi.mock("../api/queries", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/queries")>();
  return {
    ...actual,
    uploadFile: vi.fn(async (projectId: string, f: File) => {
      uploaded.push({ projectId, name: f.name });
      onUpload();
      return { file: { id: "f1" }, duplicate: false, job_id: "job-1" };
    }),
  };
});

describe("new project wizard", () => {
  it("creates the project from the first two steps and moves on to the files", async () => {
    let body: unknown = null;
    server.use(
      http.post(api("/projects"), async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(project(), { status: 201 });
      }),
      http.get(api("/projects/p1"), () => HttpResponse.json(project())),
      http.get(api("/projects/p1/files"), () => HttpResponse.json([])),
      http.get(api("/projects/p1/ficha"), () => HttpResponse.json(emptyFicha())),
      http.get(api("/projects/p1/events"), () => new HttpResponse("", { headers: { "Content-Type": "text/event-stream" } })),
    );
    const { router } = renderAt("/projetos/novo");
    const user = userEvent.setup();

    expect(screen.getByRole("list", { name: "Passos" })).toHaveTextContent("ProjetoÂmbitoFicheirosFicha-baseMontar");
    await user.type(screen.getByLabelText("Código do projeto"), "r9");
    await user.type(screen.getByLabelText("Designação"), "Moradia");
    await user.type(screen.getByLabelText("Tipo de edifício"), "Moradia unifamiliar");
    await user.click(screen.getByRole("button", { name: /Seguinte/ }));
    await user.click(screen.getByRole("button", { name: "Licenciamento" }));
    await user.click(screen.getByLabelText(/Contratação pública/));
    await user.click(screen.getByRole("button", { name: /Criar projeto/ }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/projetos/p1/ficheiros"));
    expect(body).toEqual({
      code: "R9",
      name: "Moradia",
      building_type: "Moradia unifamiliar",
      phase: "licenciamento",
      public_procurement: true,
    });
    expect(await screen.findByText("Ainda não há ficheiros neste projeto.")).toBeInTheDocument();
  });

  it("shows why the project could not be created", async () => {
    server.use(
      http.post(api("/projects"), () =>
        HttpResponse.json({ detail: "Já existe um projeto com esse código." }, { status: 409 }),
      ),
    );
    renderAt("/projetos/novo");
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Código do projeto"), "R9");
    await user.type(screen.getByLabelText("Designação"), "x");
    await user.click(screen.getByRole("button", { name: /Seguinte/ }));
    await user.click(screen.getByRole("button", { name: /Criar projeto/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Já existe um projeto com esse código.");
  });
});

describe("project files", () => {
  it("uploads files, follows their reading and keeps 'Montar' locked without a confirmed ficha", async () => {
    let files: ProjectFile[] = [];
    server.use(
      http.get(api("/projects/p1"), () => HttpResponse.json(project())),
      http.get(api("/projects/p1/files"), () => HttpResponse.json(files)),
      http.get(api("/projects/p1/ficha"), () => HttpResponse.json(emptyFicha())),
      http.get(api("/projects/p1/audit"), () => HttpResponse.json([])),
      http.get(api("/projects/p1/events"), () =>
        new HttpResponse(sse(), { headers: { "Content-Type": "text/event-stream" } }),
      ),
    );
    onUpload = () => {
      files = [file({ ingest_status: "done", ingest_message: "21 valores lidos (21 novos)" })];
    };
    renderAt("/projetos/p1/ficheiros");
    const user = userEvent.setup();
    expect(await screen.findByText("Ainda não há ficheiros neste projeto.")).toBeInTheDocument();

    await user.upload(screen.getByLabelText("Escolher ficheiros"), new File(["x"], "FE.xlsm"));

    const list = screen.getByRole("list", { name: "Ficheiros carregados" });
    expect(await within(list).findByText("FE.xlsm")).toBeInTheDocument();
    expect(within(list).getByText(/Ficha eletrotécnica · 20 KB · 21 valores lidos/)).toBeInTheDocument();
    expect(within(list).getByText("Lido")).toBeInTheDocument();
    expect(uploaded).toEqual([{ projectId: "p1", name: "FE.xlsm" }]);
    expect(screen.getByRole("button", { name: "Montar peças" })).toBeDisabled();
    expect(screen.getByRole("link", { name: /Ver a ficha do projeto/ })).toHaveAttribute("href", "/projetos/p1/ficha");
    expect(screen.getByText("Não é possível montar peças sem ficha-base confirmada.")).toBeInTheDocument();
  });

  it("opens the assembly in Documentos once the ficha is confirmed", async () => {
    server.use(
      http.get(api("/projects/p1"), () => HttpResponse.json(project())),
      http.get(api("/projects/p1/files"), () => HttpResponse.json([file({ ingest_status: "done" })])),
      http.get(api("/projects/p1/ficha"), () => HttpResponse.json(confirmedFicha())),
      http.get(api("/projects/p1/events"), () =>
        new HttpResponse(sse(), { headers: { "Content-Type": "text/event-stream" } }),
      ),
    );
    renderAt("/projetos/p1/ficheiros");

    const assemble = await screen.findByRole("link", { name: "Montar peças" });
    expect(assemble).toHaveAttribute("href", "/projetos/p1/documentos");
    expect(screen.getByText(/O MDJ e o CTE montam-se em Documentos/)).toBeInTheDocument();
    expect(screen.queryByText(/Fase 4/)).toBeNull();
  });
});

describe("what was read", () => {
  const withFiles = (files: ProjectFile[]) =>
    server.use(
      http.get(api("/projects/p1"), () => HttpResponse.json(project())),
      http.get(api("/projects/p1/files"), () => HttpResponse.json(files)),
      http.get(api("/projects/p1/ficha"), () => HttpResponse.json(emptyFicha())),
      http.get(api("/projects/p1/events"), () =>
        new HttpResponse(sse(), { headers: { "Content-Type": "text/event-stream" } }),
      ),
    );

  it("summarizes every kind that is read, with warnings and files not read", async () => {
    withFiles([
      file({ id: "a", kind: "calc_summary", filename: "Tabela.xlsx", ingest_status: "done",
        ingest_message: "4 valores lidos (4 novos) · 20 troços" }),
      file({ id: "b", kind: "calc_circuit", filename: "09-Folha QEG-ATRIO.xls", ingest_status: "done",
        ingest_message: "9 valores lidos · associada ao troço pelo nome do ficheiro",
        ingest_warnings: ["Célula proteccao!J9 vazia ou sem número."] }),
      file({ id: "c", kind: "calc_circuit", filename: "09-Folha ARM-QEG.xls", ingest_status: "failed",
        ingest_message: "09-Folha ilegível ou corrompida." }),
      file({ id: "d", kind: "lpu", filename: "LPU.xlsx", ingest_status: "done",
        ingest_message: "LPU: 170 artigos (34 associados, 136 por associar)" }),
      file({ id: "e", kind: "other", filename: "MDJ.pdf", ingest_status: "skipped",
        ingest_message: "PDF sem carimbadura: guardado, não lido como peças desenhadas." }),
    ]); // prettier-ignore
    renderAt("/projetos/p1/ficheiros");

    const summary = await screen.findByRole("list", { name: "Resumo por tipo de ficheiro" });
    const row = (label: string) => within(summary).getByText(label).closest("li") as HTMLElement;
    expect(within(row("Tabela de Cálculo")).getByText("Lido")).toBeInTheDocument();
    expect(within(row("09-Folhas de Cálculo")).getByText("1 não lido")).toBeInTheDocument();
    expect(within(row("MQT / LPU")).getByText("Lido")).toBeInTheDocument();
    expect(within(row("Ficha eletrotécnica")).getByText("Por carregar")).toBeInTheDocument();
    expect(within(row("Peças desenhadas (PDF)")).getByText("Por carregar")).toBeInTheDocument();

    const list = screen.getByRole("list", { name: "Ficheiros carregados" });
    const warned = within(list).getByRole("list", { name: "Avisos de 09-Folha QEG-ATRIO.xls" });
    expect(within(warned).getByText("Célula proteccao!J9 vazia ou sem número.")).toBeInTheDocument();
    expect(within(list).getByText("Lido com avisos")).toBeInTheDocument();
    expect(within(list).getByText(/não entrou na ficha-base; os outros continuam a ser lidos/)).toBeInTheDocument();
    expect(within(list).getByText(/PDF sem carimbadura/)).toBeInTheDocument();
  });

  it("accepts the files of every reader", async () => {
    withFiles([]);
    renderAt("/projetos/p1/ficheiros");
    const input = await screen.findByLabelText("Escolher ficheiros");
    expect(input.getAttribute("accept")).toBe(".xlsm,.xlsx,.xls,.pdf,.dwg,.dwfx,.docx");
    expect(screen.getByText(/09-Folhas de Cálculo \(\.xls\) e peças desenhadas \(\.pdf\)/)).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("list", { name: "Resumo por tipo de ficheiro" })).toBeNull());
  });
});
