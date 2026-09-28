/**
 * Phase 4 acceptance journey with the anonymized R1, against the real stack and the real LLM (SPEC 14):
 * open R1 → assemble the MDJ → states and modes → draft a section and ask for a rewrite → accept it
 * in the diff → mark it as reviewed. Screenshots in light, dark and phone width.
 *
 * The setup goes through the API: a new R1 project from data/fixtures (ficha eletrotécnica, Tabela
 * de Cálculo, MQT), ficha-base confirmed by the technician and the LLM allowed by the admin (D5:
 * only projects of the fixtures). It creates data in the development database and calls Gemini
 * twice, so it only runs when asked: `make up`, `make seed-library`, then
 * RUN_R1_EDITOR_JOURNEY=1 npm run e2e (reset with docker compose down -v).
 */

import { existsSync, readFileSync } from "node:fs";
import { basename, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { type APIRequestContext, expect, type Page, test } from "@playwright/test";

import { expectNoSeriousA11yIssues, horizontalOverflow, screenshot } from "./support";

const R1 = resolve(dirname(fileURLToPath(import.meta.url)), "../../data/fixtures/R1/MBERAL");
const FILES = [
  "2-PE/Editavel/MBERAL_FichaEletrotécnica_PE_ELE.xlsm",
  "1-CALC/Folha de Calculo_MD_E.xlsx",
  "2-PE/Editavel/MBERAL_MQT_PE_ELE_v0.xlsx",
];
// A generic adaptive section of R1: its text needs no value the ficha-base of R1 lacks.
const SECTION = "Tomadas de Usos Gerais";
const LLM_WAIT = 180_000;

test.skip(!existsSync(R1), "data/fixtures/R1 não existe");
test.skip(
  !process.env.RUN_R1_EDITOR_JOURNEY,
  "cria dados na BD de desenvolvimento e chama o Gemini: correr com RUN_R1_EDITOR_JOURNEY=1, make up e make seed-library",
);

const as = (login: string) => ({ "X-Dev-User": login });

async function r1Project(request: APIRequestContext): Promise<string> {
  const created = await request.post("/api/projects", {
    headers: as("redator"),
    // the code is unique: one project per run
    data: {
      code: `R1-E2E-${Date.now().toString(36).toUpperCase()}`,
      name: "Moradia unifamiliar (R1, percurso da Fase 4)",
    },
  });
  expect(created.ok()).toBeTruthy();
  const { id } = (await created.json()) as { id: string };
  for (const file of FILES) {
    const path = resolve(R1, file);
    const upload = await request.post(`/api/projects/${id}/files`, {
      headers: as("redator"),
      multipart: { file: { name: basename(path), mimeType: "application/octet-stream", buffer: readFileSync(path) } },
    });
    expect(upload.status()).toBe(202);
  }
  await expect
    .poll(
      async () => {
        const files = (await (await request.get(`/api/projects/${id}/files`, { headers: as("redator") })).json()) as {
          ingest_status: string;
        }[];
        return files.every((f) => ["done", "failed"].includes(f.ingest_status));
      },
      { timeout: 60_000 },
    )
    .toBe(true);
  const ficha = (await (await request.get(`/api/projects/${id}/ficha`, { headers: as("redator") })).json()) as {
    open_conflicts: number;
    revision: { id: string };
  };
  expect(ficha.open_conflicts).toBe(0); // R1: the power agrees between the sources (control case)
  expect(
    (await request.post(`/api/ficha/revisions/${ficha.revision.id}/confirm`, { headers: as("tecnico") })).ok(),
  ).toBe(true);
  const llm = await request.patch(`/api/projects/${id}/llm`, {
    headers: as("admin"),
    data: { allowed: true, reason: "Projeto das fixtures (R1), percurso da Fase 4." },
  });
  expect(llm.ok()).toBeTruthy();
  return id;
}

/** The agent's proposal, or a clear failure when the LLM gave up (quota, 503 after the retries). */
async function waitForProposal(page: Page) {
  const proposal = page.getByRole("region", { name: "Proposta do agente" });
  const failed = page.getByRole("article").getByText(/^O LLM não respondeu/);
  await expect(proposal.or(failed)).toBeVisible({ timeout: LLM_WAIT });
  if (await failed.isVisible()) throw new Error(`o LLM falhou: ${await failed.innerText()}`);
  return proposal;
}

function sectionButton(page: Page, title: string) {
  return page
    .getByRole("navigation", { name: "Secções do MDJ" })
    .getByRole("button")
    .filter({ hasText: new RegExp(`\\d+\\. (↳ )?${title}`) })
    .first();
}

test("R1: assemble the MDJ, draft, rewrite, accept in the diff and review", async ({ page, request }, info) => {
  test.setTimeout(3 * LLM_WAIT + 120_000);
  const projectId = await r1Project(request);

  await page.goto(`/projetos/${projectId}/documentos?doc=MDJ`);
  await page.getByRole("button", { name: "Montar o MDJ" }).click();
  const nav = page.getByRole("navigation", { name: "Secções do MDJ" });
  await expect(nav).toBeVisible();

  // states and modes: a fixed block generated, an adaptive one to do, an inactive one with its reason
  await expect(sectionButton(page, "LEGISLAÇÃO E NORMAS")).toContainText("fixo");
  await expect(sectionButton(page, "LEGISLAÇÃO E NORMAS")).toContainText("Gerada, por rever");
  await expect(sectionButton(page, "INTRODUÇÃO")).toContainText("adaptativo");
  await expect(sectionButton(page, "INTRODUÇÃO")).toContainText("Por fazer");
  await expect(sectionButton(page, "INTRODUÇÃO")).toContainText("não aprovado");
  const rpc = sectionButton(page, "REGULAMENTO DOS PRODUTOS DE CONSTRUÇÃO");
  await expect(rpc).toContainText("Desativada");
  await rpc.click();
  await expect(page.getByRole("article").getByText(/Desativada pela regra/)).toBeVisible();
  await screenshot(page, info, "r1-mdj-montada-claro");

  // draft one adaptive section, then ask for a rewrite in natural language
  await sectionButton(page, SECTION).click();
  const article = page.getByRole("article");
  await expect(article.getByRole("heading", { name: SECTION })).toBeVisible();
  await page.getByRole("button", { name: "Gerar esta secção" }).click();
  const proposal = await waitForProposal(page);
  await proposal.getByRole("button", { name: "Aceitar proposta" }).click();
  await expect(proposal).toBeHidden();
  await expect(article.locator("[data-generated]").first()).toBeVisible();

  await page.getByLabel(/Pedido em linguagem natural/).fill("Reescreve em frases mais curtas, sem mudar o sentido.");
  await page.getByRole("button", { name: "Enviar pedido" }).click();
  await waitForProposal(page);
  await expect(proposal.getByText("«Reescreve em frases mais curtas, sem mudar o sentido.»")).toBeVisible();
  const diff = proposal.getByLabel("Diferenças entre o texto atual e a proposta");
  await expect(diff.locator("ins, del").first()).toBeVisible();
  await expectNoSeriousA11yIssues(page);
  await screenshot(page, info, "r1-reescrita-diff-claro");

  await page.emulateMedia({ colorScheme: "dark" });
  await expectNoSeriousA11yIssues(page);
  await screenshot(page, info, "r1-reescrita-diff-escuro");
  await page.emulateMedia({ colorScheme: "light" });

  await proposal.getByRole("button", { name: "Aceitar proposta" }).click();
  await expect(proposal).toBeHidden();
  await page.getByRole("button", { name: "✓ Marcar como revista" }).click();
  await expect(sectionButton(page, SECTION)).toContainText("Revista");

  await page.setViewportSize({ width: 400, height: 860 });
  await expect(article).toBeVisible();
  expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
  await screenshot(page, info, "r1-seccao-revista-telemovel");
  await page.setViewportSize({ width: 1280, height: 900 });

  // everything is in the audit, with the agent as the author of the proposals
  const audit = (await (await request.get(`/api/projects/${projectId}/audit`, { headers: as("redator") })).json()) as {
    description: string;
  }[];
  const described = audit.map((e) => e.description);
  expect(described).toContain(`Marcou «${SECTION}» como revista`);
  expect(
    described.filter((d) => d.startsWith("Aceitou a versão") && d.endsWith(`«${SECTION}»`)).length,
  ).toBeGreaterThanOrEqual(2);
});
