/**
 * Phase 6 acceptance journey with the anonymized R1, against the real stack (SPEC 14):
 * open R1 → review the last sections → the card with its conditions → try the official export and
 * see it blocked → blocks approved by the curator → approve as the técnico → export the set →
 * download the .zip. Screenshots in light, dark and phone width. No LLM: the adaptive text is
 * written by the técnico.
 *
 * The setup goes through the API: an R1 project from data/fixtures (ficha eletrotécnica, Tabela,
 * MQT), the values no source gives added by the técnico (designation of the work, postal code),
 * the ficha-base confirmed, the MDJ and the CTE assembled, the adaptive sections written, the
 * validation run in the worker and its known critical alerts of R1 (C1, C3) ignored with a
 * justification, the review requested. It approves every block of the library in the development
 * database, so it only runs when asked: `make up`, `make seed-library`, then
 * RUN_EXPORT_JOURNEY=1 npm run e2e (reset with docker compose down -v and make seed-library).
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

test.skip(!existsSync(R1), "data/fixtures/R1 não existe");
test.skip(
  !process.env.RUN_EXPORT_JOURNEY,
  "aprova os blocos na BD de desenvolvimento: correr com RUN_EXPORT_JOURNEY=1, make up e make seed-library",
);

const as = (login: string) => ({ "X-Dev-User": login });
type Section = { id: string; title: string; active: boolean; status: string; content: { content: { type: string }[] } };
type Doc = { id: string; type: string; sections: Section[] };

async function ok(response: Awaited<ReturnType<APIRequestContext["get"]>>, what: string) {
  expect(response.ok(), `${what}: ${response.status()} ${await response.text()}`).toBeTruthy();
  return response;
}

async function waitForValidation(request: APIRequestContext, id: string) {
  await expect
    .poll(
      async () => {
        const v = (await (await request.get(`/api/projects/${id}/validation`, { headers: as("tecnico") })).json()) as {
          current: { status: string } | null;
        };
        return v.current?.status;
      },
      { timeout: 180_000, intervals: [1000] },
    )
    .toBe("done");
}

/** R1 ready for the review, all through the API (what the team did before this screen). */
async function r1ForReview(request: APIRequestContext): Promise<{ id: string; code: string; mdj: Doc }> {
  const code = `R1-E2E-EXP-${Date.now().toString(36).toUpperCase()}`.slice(0, 32);
  const created = await ok(
    await request.post("/api/projects", { headers: as("redator"), data: { code, name: "Moradia (R1, Fase 6)" } }),
    "projeto",
  );
  const { id } = (await created.json()) as { id: string };
  for (const file of FILES) {
    const path = resolve(R1, file);
    await ok(
      await request.post(`/api/projects/${id}/files`, {
        headers: as("redator"),
        multipart: { file: { name: basename(path), mimeType: "application/octet-stream", buffer: readFileSync(path) } },
      }),
      "carregar",
    );
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
  const confirm = async () => {
    const ficha = (await (await request.get(`/api/projects/${id}/ficha`, { headers: as("tecnico") })).json()) as {
      revision: { id: string };
    };
    await ok(
      await request.post(`/api/ficha/revisions/${ficha.revision.id}/confirm`, { headers: as("tecnico") }),
      "confirmar",
    );
  };
  await confirm();
  for (const [key, value] of [
    ["id.obra.designacao", "Moradia unifamiliar"],
    ["id.local.cp", "3000-000"],
  ]) {
    await ok(
      await request.post(`/api/projects/${id}/ficha/values`, {
        headers: as("tecnico"),
        data: { key, value, note: "Indicado pelo cliente (percurso da Fase 6)." },
      }),
      "valor manual",
    );
  }
  await confirm(); // rev. B
  const docs: Doc[] = [];
  for (const type of ["MDJ", "CTE"]) {
    const doc = await ok(
      await request.post(`/api/projects/${id}/documents`, { headers: as("redator"), data: { type } }),
      `montar ${type}`,
    );
    docs.push((await doc.json()) as Doc);
  }
  // the adaptive text, written by the técnico (no LLM in this journey)
  for (const doc of docs) {
    for (const s of doc.sections.filter((x) => x.active && x.content.content.some((n) => n.type === "pending"))) {
      const content = {
        ...s.content,
        content: s.content.content.map((n) =>
          n.type === "pending"
            ? { type: "paragraph", content: [{ type: "text", text: "Texto escrito pelo técnico." }] }
            : n,
        ),
      };
      await ok(
        await request.put(`/api/sections/${s.id}/content`, { headers: as("tecnico"), data: { content } }),
        "texto",
      );
    }
  }
  // every section reviewed except the last two of the MDJ, reviewed in the interface
  const fresh: Doc[] = [];
  for (const doc of docs) {
    fresh.push((await (await request.get(`/api/documents/${doc.id}`, { headers: as("tecnico") })).json()) as Doc);
  }
  const mdj = fresh.find((d) => d.type === "MDJ")!;
  const leave = new Set(
    mdj.sections
      .filter((s) => s.active)
      .slice(-2)
      .map((s) => s.id),
  );
  for (const doc of fresh) {
    for (const s of doc.sections.filter((x) => x.active && !leave.has(x.id))) {
      const reviewed = await request.post(`/api/sections/${s.id}/review`, { headers: as("tecnico"), data: {} });
      if (!reviewed.ok()) {
        // a block with nothing to say in R1 (e.g. no text in either reference project): deactivated
        await ok(
          await request.post(`/api/sections/${s.id}/activation`, {
            headers: as("tecnico"),
            data: { active: false, reason: "Não se aplica a esta moradia (percurso da Fase 6)." },
          }),
          `desativar ${s.title}`,
        );
      }
    }
  }
  // the validation in the worker, then the known critical alerts of R1 ignored with a reason
  await waitForValidation(request, id).catch(() => undefined);
  await ok(
    await request.post(`/api/projects/${id}/validation`, { headers: as("tecnico"), data: { trigger: "full" } }),
    "validar",
  );
  await waitForValidation(request, id);
  const validation = (await (
    await request.get(`/api/projects/${id}/validation`, { headers: as("tecnico") })
  ).json()) as {
    issues: { id: string; severity: string; status: string }[];
  };
  for (const issue of validation.issues.filter((i) => i.severity === "critical" && i.status === "open")) {
    await ok(
      await request.post(`/api/validation/issues/${issue.id}/ignore`, {
        headers: as("tecnico"),
        data: { reason: "Divergência conhecida de R1 (Anexo C): revista com a equipa." },
      }),
      "ignorar",
    );
  }
  await ok(
    await request.post(`/api/projects/${id}/review-request`, { headers: as("tecnico"), data: {} }),
    "pedir revisão",
  );
  return { id, code, mdj };
}

async function asTecnico(page: Page) {
  await page
    .getByLabel("Utilizador de desenvolvimento")
    .selectOption({ label: "Técnico responsável (desenvolvimento)" });
}

test("R1: review, see the conditions, approve and export the official set", async ({ page, request }, info) => {
  test.setTimeout(600_000);
  const { id, code, mdj } = await r1ForReview(request);

  // the card says what is left: two sections of the MDJ and the blocks of the curator
  await page.goto(`/projetos/${id}/revisao?doc=MDJ`);
  await asTecnico(page);
  const conditions = page.getByRole("list", { name: "Condições para aprovar" });
  await expect(conditions.getByText("2 secções por rever", { exact: false })).toBeVisible();
  await expect(conditions.getByText("por aprovar", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Aprovar MDJ" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Exportar conjunto oficial" })).toBeDisabled();
  const refused = await request.post(`/api/projects/${id}/exports`, {
    headers: as("tecnico"),
    data: { kind: "official" },
  });
  expect(refused.status()).toBe(409);
  await screenshot(page, info, "r1-revisao-condicoes-claro");

  // review the last two sections in the editor, from the card's link
  const left = mdj.sections.filter((s) => s.active).slice(-2);
  for (const s of left) {
    await page.goto(`/projetos/${id}/documentos?doc=MDJ&seccao=${s.id}`);
    await page.getByRole("button", { name: "✓ Marcar como revista" }).click();
    await expect(page.getByRole("button", { name: "✓ Marcar como revista" })).toBeDisabled();
  }

  // the curator approves the blocks (through the API: the curator journey shows the screen)
  const blocks = (await (await request.get("/api/library/blocks", { headers: as("curador") })).json()) as {
    id: string;
    status: string;
  }[];
  for (const b of blocks.filter((x) => x.status === "proposed")) {
    await ok(
      await request.post(`/api/library/blocks/${b.id}/review`, {
        headers: as("curador"),
        data: { decision: "approved", note: "Aprovado para o percurso da Fase 6." },
      }),
      "aprovar bloco",
    );
  }

  // the técnico approves the MDJ and the CTE in screen H
  for (const type of ["MDJ", "CTE"]) {
    await page.goto(`/projetos/${id}/revisao?doc=${type}`);
    const approve = page.getByRole("button", { name: `Aprovar ${type}` });
    await expect(approve).toBeEnabled({ timeout: 15_000 });
    await approve.click();
    await expect(page.getByRole("button", { name: `Reabrir ${type}` })).toBeVisible();
  }

  // export the official set and download it
  const official = page.getByRole("button", { name: "Exportar conjunto oficial" });
  await expect(official).toBeEnabled();
  await official.click();
  const zipName = `${code}_PE_ELE_V0.zip`;
  const downloadButton = page.getByRole("button", { name: `Descarregar ${zipName}` });
  await expect(downloadButton).toBeVisible({ timeout: 300_000 });
  const [download] = await Promise.all([page.waitForEvent("download"), downloadButton.click()]);
  expect(download.suggestedFilename()).toBe(zipName);
  const zip = readFileSync((await download.path())!);
  for (const name of [
    `${code}_MDJ_PE_ELE_V0.docx`,
    `${code}_CTE_PE_ELE_V0.docx`,
    `${code}_FichaEletrotecnica_PE_ELE_V0.xlsm`,
    `${code}_IdentificacaoProjeto_PE_ELE_V0.docx`,
    `${code}_TermoResponsabilidade_PE_ELE_V0.docx`,
    "manifesto.json",
  ]) {
    expect(zip.includes(Buffer.from(name)), name).toBe(true); // names are stored as is in a zip
  }

  await page.goto(`/projetos/${id}/revisao?doc=MDJ`);
  await expect(page.getByText("Oficial V0")).toBeVisible();
  await expectNoSeriousA11yIssues(page);
  await screenshot(page, info, "r1-revisao-aprovada-claro");
  await page.emulateMedia({ colorScheme: "dark" });
  await expectNoSeriousA11yIssues(page);
  await screenshot(page, info, "r1-revisao-aprovada-escuro");
  await page.emulateMedia({ colorScheme: "light" });
  await page.setViewportSize({ width: 400, height: 860 });
  expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
  await screenshot(page, info, "r1-revisao-telemovel");
});
