/** A small assembled MDJ for the editor tests (shapes of the API, no real project data). */

import type { DocSection, Ficha, ProjectDocument, ProjectForm, SectionVersion } from "../api/types";
import { emptyFicha } from "./fixtures";

export const confirmedFicha = (): Ficha => ({
  ...emptyFicha(),
  revisions: [
    {
      id: "rev-a",
      label: "A",
      status: "confirmed",
      confirmed_by: "dev:tecnico",
      confirmed_at: "2026-09-28T10:00:00Z",
      created_at: "2026-09-28T09:00:00Z",
    },
  ],
});

const base = (): Omit<DocSection, "id" | "order" | "title" | "mode" | "block_key" | "status" | "content"> => ({
  level: 1,
  kind: "block",
  block_status: "proposed",
  block_approved: false,
  active: true,
  active_reason: null,
  status_note: null,
  missing_keys: [],
  locked: false,
  equipment_slots: [],
  current_version: 1,
  has_adaptive: false,
  proposals: 0,
  unlocked: null,
  activation_override: null,
  reviewed_by: null,
  reviewed_at: null,
  missing_data: [],
  assumptions: [],
  issues: [],
  citations: [],
});

export const fixedSection = (): DocSection => ({
  ...base(),
  id: "s-fixed",
  order: 14,
  level: 2,
  title: "Quedas de Tensão",
  mode: "fixed",
  block_key: "ele.mdj.dimensionamento_eletrico.quedas_de_tensao",
  status: "generated",
  locked: true,
  content: {
    type: "doc",
    content: [
      {
        type: "locked",
        attrs: { entry: 0, parametric: false },
        content: [{ type: "paragraph", content: [{ type: "text", text: "Quedas de Tensão" }] }],
      },
      {
        type: "locked",
        attrs: { entry: 1, parametric: false },
        content: [
          {
            type: "paragraph",
            content: [{ type: "text", text: "As quedas de tensão não excedem os limites das RTIEBT." }],
          },
        ],
      },
    ],
  },
});

export const supplySection = (): DocSection => ({
  ...base(),
  id: "s-supply",
  order: 9,
  level: 2,
  title: "Alimentação de Energia",
  mode: "adaptive",
  block_key: "ele.mdj.instalacao.alimentacao_de_energia",
  status: "todo",
  status_note: "Por gerar: texto adaptativo.",
  has_adaptive: true,
  proposals: 1,
  // a real source id is long: the side panel must wrap it at phone width (Phase 4 journey)
  citations: [
    {
      anchor: "g0",
      kind: "archive",
      target: "arc:R1:ele.mdj.instalacoes_eletricas_a_considerar.tomadas_de_usos_gerais",
    },
  ],
  content: {
    type: "doc",
    content: [
      { type: "pending", attrs: { entry: 1, note: "Texto diferente em R1 e R2." } },
      {
        type: "paragraph",
        attrs: { entry: 5 },
        content: [
          { type: "text", text: "Prevê-se uma potência elétrica de " },
          {
            type: "text",
            text: "34,5",
            marks: [
              {
                type: "value",
                attrs: {
                  key: "ele.potencia_alimentar_kva",
                  anchor: "e5-v0",
                  label: "Potência a alimentar",
                  personal: false,
                  missing: false,
                },
              },
            ],
          },
          { type: "text", text: " kVA." },
        ],
      },
    ],
  },
});

export const pvSection = (): DocSection => ({
  ...base(),
  id: "s-pv",
  order: 33,
  title: "INSTALAÇÃO FOTOVOLTAICA",
  mode: "adaptive",
  block_key: "ele.mdj.instalacao_fotovoltaica",
  status: "todo",
  active: false,
  active_reason: "Sem «Fotovoltaico» na ficha-base nem artigos do MQT/LPU associados.",
  has_adaptive: true,
  content: { type: "doc", content: [{ type: "pending", attrs: { entry: 1 } }] },
});

export const mdj = (sections: DocSection[] = [supplySection(), fixedSection(), pvSection()]): ProjectDocument => ({
  id: "d1",
  project_id: "p1",
  type: "MDJ",
  status: "draft",
  ficha_revision: "A",
  created_at: "2026-09-28T10:00:00Z",
  counts: { sections: sections.length, todo: 1, generated: 1, inactive: 1, not_approved: sections.length },
  sections,
});

export const proposal = (): SectionVersion => ({
  id: "v2",
  number: 2,
  status: "proposed",
  author_type: "agent",
  request: null,
  missing_data: ["ele.n_pisos"],
  assumptions: ["Entrada na portinhola (texto de R1)."],
  issues: [],
  created_at: "2026-09-28T10:05:00Z",
  created_by: null,
  citations: [{ anchor: "g0", kind: "archive", target: "arc:R1:ele.mdj.instalacao.alimentacao_de_energia" }],
  content: {
    type: "doc",
    content: [
      {
        type: "paragraph",
        attrs: { entry: 1, generated: true },
        content: [
          {
            type: "text",
            text: "A entrada foi dimensionada para garantir a segurança.",
            marks: [{ type: "generated" }],
          },
        ],
      },
    ],
  },
});

export const forms = (): ProjectForm[] => [
  {
    kind: "ficha_eletrotecnica",
    title: "Ficha eletrotécnica",
    filename: "R1_FichaEletrotecnica.xlsm",
    by_hand: ["Telefone do requerente (C6)", "Data (pelo técnico) (M40)"],
  },
  {
    kind: "termo",
    title: "Termo de Responsabilidade",
    filename: "R1_TermoResponsabilidade.docx",
    by_hand: ["Data e assinatura do técnico responsável"],
  },
];
