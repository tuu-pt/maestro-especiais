/** Shapes of the review and export API for the screen H tests (no real project data). */

import type { Approval, ApprovalCondition, DocumentDiff, ProjectExport } from "../api/types";

const condition = (
  code: ApprovalCondition["code"],
  text: string,
  ok: boolean,
  over: Partial<ApprovalCondition> = {},
) => ({
  code,
  text,
  ok,
  reason: null,
  link: null,
  items: [],
  ...over,
});

export const pendingConditions = (): ApprovalCondition[] => [
  condition("assembled", "Peça montada na aplicação", true),
  condition("ficha", "Ficha-base confirmada e usada na peça", true),
  condition("sections", "Todas as secções revistas (1 de 2)", false, {
    reason: "1 secção por rever",
    link: "/projetos/p1/documentos?doc=MDJ&seccao=s-supply",
    items: [
      { section_id: "s-supply", order: 9, title: "Alimentação de Energia", reason: "Por gerar: texto adaptativo." },
    ],
  }),
  condition("blocks", "Blocos usados aprovados pelo curador", false, {
    reason: "2 blocos por aprovar",
    link: "/conhecimento?separador=blocos",
    items: [
      { section_id: "s-supply", order: 9, title: "Alimentação de Energia", reason: "bloco não aprovado" },
      { section_id: "s-fixed", order: 14, title: "Quedas de Tensão", reason: "bloco não aprovado" },
    ],
  }),
  condition("validation", "Validação sem alertas críticos", true),
];

export const approval = (over: Partial<Approval> = {}): Approval => ({
  document_id: "d1",
  type: "MDJ",
  status: "in_review",
  origin: "assembled",
  revision: 0,
  revision_label: "A",
  file_version: "V0",
  header_revision: "R00",
  header_date: null,
  responsible_id: "dev:tecnico",
  responsible_name: "Técnico responsável (desenvolvimento)",
  approved_by_name: null,
  approved_at: null,
  conditions: pendingConditions(),
  ready: false,
  can_approve: false,
  why_not: "Há condições por cumprir.",
  revisions: [],
  tecnicos: [{ id: "dev:tecnico", name: "Técnico responsável (desenvolvimento)" }],
  ...over,
});

export const readyApproval = (over: Partial<Approval> = {}): Approval =>
  approval({
    conditions: pendingConditions().map((c) => ({ ...c, ok: true, reason: null, items: [] })),
    ready: true,
    can_approve: true,
    why_not: null,
    ...over,
  });

export const approvedWithHistory = (): Approval =>
  approval({
    status: "approved",
    conditions: pendingConditions().map((c) => ({ ...c, ok: true, reason: null, items: [] })),
    ready: true,
    why_not: "A peça já está aprovada.",
    approved_by_name: "Técnico responsável (desenvolvimento)",
    approved_at: "2026-10-06T10:00:00Z",
    revisions: [
      {
        number: 0,
        label: "A",
        file_version: "V0",
        header_revision: "R00",
        approved_by: "dev:tecnico",
        approved_by_name: "Técnico responsável (desenvolvimento)",
        approved_at: "2026-10-06T10:00:00Z",
        header_date: null,
        sections: 42,
        reopened_by_name: null,
        reopened_at: null,
        reopen_reason: null,
      },
    ],
  });

export const diff = (): DocumentDiff => ({
  from_label: "A",
  to_label: "atual",
  changed: 1,
  sections: [
    {
      section_id: "s-supply",
      order: 9,
      title: "Alimentação de Energia",
      before: "A entrada é monofásica.",
      after: "A entrada é trifásica.",
      changed: true,
      active_before: true,
      active_after: true,
    },
  ],
});

export const exportDone = (over: Partial<ProjectExport> = {}): ProjectExport => ({
  id: "e1",
  kind: "draft",
  status: "done",
  message: null,
  version: "V0",
  with_pdf: false,
  zip_name: "R9_Conjunto_RASCUNHO-nao-aprovado.zip",
  zip_size: 812345,
  zip_sha256: "0".repeat(64),
  files: [
    { name: "R9_MDJ_RASCUNHO-nao-aprovado.docx", piece: "MDJ", revision: "A", sha256: "1".repeat(64), size: 300000 },
  ],
  created_at: "2026-10-06T10:05:00Z",
  created_by_name: "Redator (desenvolvimento)",
  finished_at: "2026-10-06T10:05:20Z",
  ...over,
});
