import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import type { ProjectFile } from "../api/types";
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
  });
});
