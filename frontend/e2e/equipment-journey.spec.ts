/**
 * Phase 7 journey with the anonymized R1, against the real stack: the curator adds a datasheet to
 * the portinhola of the library, reviews its parameters and approves the block of the supply (its
 * requirements with it); the técnico sees in screen F the portinhola that meets the CTE and the
 * other items without a datasheet, then confirms a mirror and its illustration goes into the CTE.
 *
 * The datasheet is a small PDF written by the test (there are no manufacturers' datasheets in
 * data/fixtures yet). It changes the development database (a datasheet, a block approved), so it
 * only runs when asked: `make up`, `make seed-library`, then RUN_EQUIPMENT_JOURNEY=1 npm run e2e
 * (reset with docker compose down -v and make seed-library).
 */

import { existsSync, readFileSync } from "node:fs";
import { basename, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { inflateRawSync } from "node:zlib";

import { type APIRequestContext, expect, test } from "@playwright/test";

import { expectNoSeriousA11yIssues, horizontalOverflow, screenshot } from "./support";

const R1 = resolve(dirname(fileURLToPath(import.meta.url)), "../../data/fixtures/R1/MBERAL");
const FILES = [
  "2-PE/Editavel/MBERAL_FichaEletrotécnica_PE_ELE.xlsm",
  "1-CALC/Folha de Calculo_MD_E.xlsx",
  "2-PE/Editavel/MBERAL_MQT_PE_ELE_v0.xlsx",
];

test.skip(!existsSync(R1), "data/fixtures/R1 não existe");
test.skip(
  !process.env.RUN_EQUIPMENT_JOURNEY,
  "muda a BD de desenvolvimento: correr com RUN_EQUIPMENT_JOURNEY=1, make up e make seed-library",
);

const as = (login: string) => ({ "X-Dev-User": login });

async function ok(response: Awaited<ReturnType<APIRequestContext["get"]>>, what: string) {
  expect(response.ok(), `${what}: ${response.status()} ${await response.text()}`).toBeTruthy();
  return response;
}

/** A one-page PDF with the standard Helvetica font: what a datasheet says, for the reader. */
function pdf(lines: string[]): Buffer {
  const text = lines.map((l) => `(${l.replace(/[\\()]/g, (c) => `\\${c}`)}) '`).join(" ");
  const stream = `BT /F1 11 Tf 50 780 Td 14 TL ${text} ET`;
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let out = "%PDF-1.4\n";
  const offsets: number[] = [];
  objects.forEach((o, i) => {
    offsets.push(out.length);
    out += `${i + 1} 0 obj\n${o}\nendobj\n`;
  });
  const xref = out.length;
  out += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  out += offsets.map((o) => `${String(o).padStart(10, "0")} 00000 n \n`).join("");
  out += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(out, "latin1");
}

/** word/document.xml of a .docx (the local headers of the zip, as Python writes them). */
function documentXml(docx: Buffer): string {
  let at = 0;
  while (docx.readUInt32LE(at) === 0x04034b50) {
    const method = docx.readUInt16LE(at + 8);
    const size = docx.readUInt32LE(at + 18);
    const nameLength = docx.readUInt16LE(at + 26);
    const extraLength = docx.readUInt16LE(at + 28);
    const name = docx.subarray(at + 30, at + 30 + nameLength).toString("utf8");
    const start = at + 30 + nameLength + extraLength;
    const data = docx.subarray(start, start + size);
    if (name === "word/document.xml") return (method === 8 ? inflateRawSync(data) : data).toString("utf8");
    at = start + size;
  }
  throw new Error("word/document.xml não encontrado");
}

const drawings = (docx: Buffer) => documentXml(docx).split("<w:drawing").length - 1;

async function r1WithCte(request: APIRequestContext): Promise<{ id: string; cte: string }> {
  const code = `R1-E2E-EQP-${Date.now().toString(36).toUpperCase()}`.slice(0, 32);
  const created = await ok(
    await request.post("/api/projects", { headers: as("redator"), data: { code, name: "Moradia (R1, Fase 7)" } }),
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
  const ficha = (await (await request.get(`/api/projects/${id}/ficha`, { headers: as("tecnico") })).json()) as {
    revision: { id: string };
  };
  await ok(await request.post(`/api/ficha/revisions/${ficha.revision.id}/confirm`, { headers: as("tecnico") }), "ficha");
  const cte = await ok(
    await request.post(`/api/projects/${id}/documents`, { headers: as("redator"), data: { type: "CTE" } }),
    "montar o CTE",
  );
  return { id, cte: ((await cte.json()) as { id: string }).id };
}

/** The curator: a datasheet for the portinhola, its parameters reviewed, the supply block approved. */
async function curatorReviewsThePortinhola(request: APIRequestContext) {
  const items = (await (
    await request.get("/api/equipment?category=portinhola", { headers: as("curador") })
  ).json()) as { id: string; reference: string | null }[];
  const portinhola = items.find((i) => i.reference === "+32470");
  expect(portinhola, "portinhola de R1 na biblioteca (make seed-library)").toBeTruthy();
  const uploaded = await ok(
    await request.post(`/api/equipment/${portinhola!.id}/datasheets`, {
      headers: as("curador"),
      multipart: {
        file: {
          name: "Portinhola PBT Tri.pdf",
          mimeType: "application/pdf",
          buffer: pdf(["Portinhola PBT Tri", "Grau de protecao IP55 IK10", "Icc 25 kA", "Rev. 05/2025"]),
        },
      },
    }),
    "ficha técnica",
  );
  const detail = (await uploaded.json()) as { params: { id: string; origin: string }[] };
  for (const p of detail.params.filter((x) => x.origin === "datasheet")) {
    await ok(await request.patch(`/api/equipment/params/${p.id}`, { headers: as("curador"), data: {} }), "rever");
  }
  const blocks = (await (
    await request.get("/api/library/blocks?doc_type=CTE", { headers: as("curador") })
  ).json()) as { id: string; key: string }[];
  const supply = blocks.find((b) => b.key.endsWith(".entrada_de_energia"))!;
  await ok(
    await request.post(`/api/library/blocks/${supply.id}/review`, {
      headers: as("curador"),
      data: { decision: "approved", note: "Aprovado para o percurso da Fase 7." },
    }),
    "aprovar o bloco",
  );
}

test("R1: the portinhola meets the CTE, the others ask for a datasheet, a mirror brings its image", async ({
  page,
  request,
}, info) => {
  test.setTimeout(300_000);
  const { id, cte } = await r1WithCte(request);
  await curatorReviewsThePortinhola(request);
  const before = drawings(
    await (await ok(await request.get(`/api/documents/${cte}/draft.docx`, { headers: as("redator") }), "rascunho")).body(),
  );

  await page.goto(`/projetos/${id}/equipamentos`);
  await page.getByLabel("Utilizador de desenvolvimento").selectOption({ label: "Técnico responsável (desenvolvimento)" });
  const table = page.getByRole("region", { name: "Equipamentos de referência do CTE" });
  const portinhola = table.getByRole("row", { name: /Portinhola PBT Tri/ });
  await expect(portinhola.getByText("Cumpre")).toBeVisible();
  await expect(table.getByText("Sem ficha").first()).toBeVisible();
  await expectNoSeriousA11yIssues(page);
  await screenshot(page, info, "r1-equipamentos-claro");

  await table.getByRole("button", { name: "Espelhos simples" }).click();
  await page.getByRole("button", { name: "Confirmar e incluir a imagem" }).click();
  await expect(page.getByText("imagem no CTE")).toBeVisible();
  const after = drawings(
    await (await ok(await request.get(`/api/documents/${cte}/draft.docx`, { headers: as("redator") }), "rascunho")).body(),
  );
  expect(after).toBe(before + 1);

  await page.emulateMedia({ colorScheme: "dark" });
  await expectNoSeriousA11yIssues(page);
  await screenshot(page, info, "r1-equipamentos-escuro");
  await page.emulateMedia({ colorScheme: "light" });
  await page.setViewportSize({ width: 400, height: 860 });
  expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
  await screenshot(page, info, "r1-equipamentos-telemovel");
});
