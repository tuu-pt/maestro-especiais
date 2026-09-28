/**
 * Phase 5 acceptance journey, audit mode, against the real stack (SPEC 14):
 * create project → upload the full anonymized R2 set with the MDJ and the CTE made by hand →
 * run the validation → see the issues and the coherence matrix → ignore a warning with a
 * justification → the review request stays blocked by the critical issues.
 * Screenshots in light, dark and phone.
 *
 * The conflicts of the ficha-base are resolved through the API, as the approved project did
 * (Tabela de Cálculo first, then the LPU, the ficha eletrotécnica, the drawings): the journey is
 * about the validation, the resolution has its own journeys (R2, Phase 1 and 2).
 *
 * Creates a project in the development database: `make up`, `make seed-library`, then
 * RUN_AUDIT_JOURNEY=1 npm run e2e.
 */

import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { expect, type APIRequestContext, test } from "@playwright/test";

import { expectNoSeriousA11yIssues, horizontalOverflow, screenshot } from "./support";

const R2 = resolve(dirname(fileURLToPath(import.meta.url)), "../../data/fixtures/R2");
const ORDER = ["calc", "mqt", "ficha_eletrotecnica", "drawing", "calc_sheet", "manual"];
const TECNICO = { "X-Dev-User": "tecnico" };

function allFiles(dir: string): string[] {
  return readdirSync(dir)
    .filter((name) => !name.startsWith(".")) // .pii-allowlist.json: the anonymizer's, not a piece
    .flatMap((name) => {
      const path = join(dir, name);
      return statSync(path).isDirectory() ? allFiles(path) : [path];
    });
}

type Candidate = { source_type: string };
type Conflict = { id: string; candidates: Candidate[] };

async function resolveAsApproved(request: APIRequestContext, projectId: string): Promise<void> {
  const ficha = await (await request.get(`/api/projects/${projectId}/ficha`, { headers: TECNICO })).json();
  const conflicts: Conflict[] = [
    ...ficha.groups.flatMap((g: { values: { conflict: Conflict | null }[] }) =>
      g.values.map((v) => v.conflict).filter(Boolean),
    ),
    ...ficha.circuits.flatMap((c: { conflicts: Conflict[] }) => c.conflicts),
  ];
  for (const conflict of conflicts) {
    const rank = (c: Candidate) => (ORDER.includes(c.source_type) ? ORDER.indexOf(c.source_type) : 99);
    const best = conflict.candidates.reduce((b, c, i, all) => (rank(c) < rank(all[b]!) ? i : b), 0);
    const response = await request.post(`/api/ficha/conflicts/${conflict.id}/resolve`, {
      headers: TECNICO,
      data: { candidate: best, note: "Como no projeto aprovado (auditoria)." },
    });
    expect(response.ok()).toBeTruthy();
  }
}

test.skip(!existsSync(R2), "data/fixtures/R2 não existe");
test.skip(!process.env.RUN_AUDIT_JOURNEY, "cria dados na BD de desenvolvimento: RUN_AUDIT_JOURNEY=1 com make up");

test("R2 audit: validation, issues, matrix, ignore a warning, review blocked", async ({ page }, info) => {
  test.setTimeout(420_000);
  const files = allFiles(R2);

  await page.goto("/projetos/novo");
  await page.getByLabel("Código do projeto").fill(`E2E-AUD-${Date.now()}`);
  await page.getByLabel("Designação").fill("Biblioteca municipal (R2 anonimizado, auditoria)");
  await page.getByLabel("Tipo de edifício").fill("Biblioteca");
  await page.getByRole("button", { name: "Seguinte: âmbito →" }).click();
  await page.getByRole("button", { name: "Criar projeto e carregar ficheiros →" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Ficheiros do projeto" })).toBeVisible();
  const projectId = /projetos\/([^/]+)\/ficheiros/.exec(page.url())![1]!;

  // The contents, not the paths: some Chromium builds drop paths with non-ASCII names ("Peças").
  await page.locator('input[type="file"]').setInputFiles(
    files.map((path) => ({ name: basename(path), mimeType: "application/octet-stream", buffer: readFileSync(path) })),
  );
  const list = page.getByRole("list", { name: "Ficheiros carregados" });
  await expect(list.getByRole("listitem")).toHaveCount(files.length, { timeout: 120_000 });
  await expect(list.getByText(/^(Na fila|A ler…|A carregar)$/)).toHaveCount(0, { timeout: 240_000 });
  const summary = page.getByRole("list", { name: "Resumo por tipo de ficheiro" });
  await expect(summary.getByText("Peças escritas existentes (auditoria)")).toBeVisible();
  await expect(summary.getByText("Por carregar")).toHaveCount(0);
  await screenshot(page, info, "auditoria-ficheiros");

  await resolveAsApproved(page.request, projectId);
  await page.getByLabel("Utilizador de desenvolvimento").selectOption({ label: "Técnico responsável (desenvolvimento)" });
  await page.goto(`/projetos/${projectId}/ficha`);
  await page.getByRole("button", { name: /^Confirmar revisão / }).click();
  await expect(page.getByText("Esta revisão já está confirmada.")).toBeVisible();

  // The existing MDJ, read-only in the editor
  await page.goto(`/projetos/${projectId}/documentos?doc=MDJ&origem=existente`);
  await expect(page.getByText("Peça existente, carregada para auditoria: só leitura.")).toBeVisible();

  // Validate
  await page.goto(`/projetos/${projectId}/validacao`);
  await page.getByRole("button", { name: "Validar o projeto" }).click();
  const issues = page.getByRole("list", { name: "Alertas da validação" });
  await expect(issues).toBeVisible({ timeout: 180_000 });
  await expect(issues.getByText(/Potência a alimentar diferente da ficha-base/)).toBeVisible();
  await expect(issues.getByText(/carregadores de veículos elétricos diferente/)).toBeVisible();
  const matrix = page.getByRole("region", { name: "Matriz de coerência do projeto" });
  await expect(matrix.getByRole("row", { name: /N.º de carregadores VE/ }).getByText("Erro provável no CTE.")).toBeVisible();
  await expect(matrix.getByRole("row", { name: /Potência a alimentar/ }).getByText("Erro provável na ficha eletrotécnica.")).toBeVisible();

  // Ignore a warning with a justification
  const warning = issues.getByRole("listitem").filter({ hasText: "«secções da RTIEBT» sem o número da secção" }).first();
  await warning.locator("summary").click();
  await warning.getByRole("button", { name: "Ignorar com justificação" }).click();
  await warning.getByLabel(/Porque é que este alerta pode ser ignorado/).fill("A secção é indicada no parágrafo seguinte.");
  await warning.getByRole("button", { name: "Ignorar", exact: true }).click();
  await page.getByLabel("Estado").selectOption({ label: "Ignorados" });
  await expect(issues.getByText("«secções da RTIEBT» sem o número da secção", { exact: false })).toBeVisible();
  await page.getByLabel("Estado").selectOption({ label: "Abertos" });

  // The review request stays blocked by the critical issues
  await expect(page.getByText(/alertas? críticos? abertos?: as peças não podem ser enviadas para revisão/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Enviar as peças para revisão" })).toBeDisabled();
  const refused = await page.request.post(`/api/projects/${projectId}/review-request`, { headers: TECNICO, data: {} });
  expect(refused.status()).toBe(409);

  await issues.getByRole("listitem").first().locator("summary").click();
  await expectNoSeriousA11yIssues(page);
  await screenshot(page, info, "auditoria-validacao-claro");
  await page.emulateMedia({ colorScheme: "dark" });
  await expectNoSeriousA11yIssues(page);
  await screenshot(page, info, "auditoria-validacao-escuro");
  await page.setViewportSize({ width: 400, height: 900 });
  expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
  await screenshot(page, info, "auditoria-validacao-telemovel");

  // The audit log and the dashboard
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(`/projetos/${projectId}/revisao`);
  await expect(page.getByText(/Ignorou um alerta REF-03: A secção é indicada/)).toBeVisible();
  await page.goto("/");
  await expect(page.getByRole("link", { name: /\d+ críticos?/ }).first()).toBeVisible();
});
