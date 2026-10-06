/** Shapes of the equipment API for the screen F and G tests (invented values, tests only). */

import type {
  Datasheet,
  EquipmentCheck,
  EquipmentDetail,
  EquipmentItem,
  EquipmentSlot,
  EquipmentSlotDetail,
  EquipmentSummary,
  ProjectEquipment,
} from "../api/types";

export const sheet = (over: Partial<Datasheet> = {}): Datasheet => ({
  id: "ds1",
  file_name: "portinhola.pdf",
  size: 20480,
  pages: 2,
  issue_date: "2025-05-01",
  issue_date_text: "rev. 05/2025",
  language: "pt",
  status: "current",
  warnings: [],
  created_at: "2026-10-06T10:00:00Z",
  old: false,
  ...over,
});

export const check = (over: Partial<EquipmentCheck> = {}): EquipmentCheck => ({
  requirement_id: "r1",
  param: "ip_rating",
  label: "Índice de proteção (IP)",
  operator: ">=class",
  required: "IP55",
  requirement_status: "approved",
  block_key: "ele.cte.condicoes_tecnicas_especiais.entrada_de_energia",
  result: "fails",
  offered: "IP44",
  page: 1,
  review_status: "reviewed",
  param_id: "pa1",
  others: [],
  evidence: ["R9: «IP55»"],
  ...over,
});

export const item = (over: Partial<EquipmentItem> = {}): EquipmentItem => ({
  id: "e1",
  category: "portinhola",
  category_label: "Portinhola",
  name: "Portinhola de exemplo",
  manufacturer: "Fabricante A",
  model: null,
  reference: "+100",
  code: null,
  status: "proposed",
  datasheet: sheet(),
  has_image: true,
  ...over,
});

export const slot = (over: Partial<EquipmentSlot> = {}): EquipmentSlot => ({
  id: "s1",
  document_id: "d2",
  section_id: "sec1",
  section_title: "Entrada de Energia",
  entry: 3,
  block_key: "ele.cte.condicoes_tecnicas_especiais.entrada_de_energia",
  item: item(),
  is_reference: true,
  chosen: false,
  chosen_by: null,
  chosen_at: null,
  reason: null,
  or_equivalent: true,
  ficha_key: "eq.portinhola",
  quantity: "1.000",
  unit: "un",
  articles: ["8.1.1 · Portinhola"],
  verdict: "fails",
  checks: [check(), check({ requirement_id: "r2", param: "ik_rating", label: "Resistência ao impacto (IK)", required: "IK10", offered: "IK10", result: "ok" })],
  ...over,
});

export const alternative = item({
  id: "e2",
  name: "Portinhola alternativa",
  manufacturer: "Fabricante B",
  reference: "+200",
  datasheet: sheet({ id: "ds2", file_name: "alternativa.pdf" }),
  has_image: false,
});

export const slotDetail = (over: Partial<EquipmentSlotDetail> = {}): EquipmentSlotDetail => ({
  ...slot(),
  alternatives: [{ item: alternative, verdict: "ok", checks: [check({ result: "ok", offered: "IP66" })] }],
  ...over,
});

export const luminaire = slot({
  id: "s2",
  section_id: "sec2",
  section_title: "Iluminação Normal",
  entry: 7,
  item: item({ id: "e3", category: "luminaria", category_label: "Luminária", name: "Aplique exterior", code: "L14", manufacturer: "Fabricante C", model: "2525", reference: null, datasheet: null, has_image: false }),
  ficha_key: "eq.luminarias",
  quantity: "21.000",
  verdict: "no_datasheet",
  checks: [],
});

export const projectEquipment = (over: Partial<ProjectEquipment> = {}): ProjectEquipment => ({
  document_id: "d2",
  document_status: "draft",
  slots: [slot(), luminaire],
  ...over,
});

export const summary = (over: Partial<EquipmentSummary> = {}): EquipmentSummary => ({
  id: "e1",
  category: "portinhola",
  category_label: "Portinhola",
  name: "Portinhola de exemplo",
  manufacturer: "Fabricante A",
  model: null,
  reference: "+100",
  code: null,
  or_equivalent: true,
  status: "proposed",
  projects: ["R9"],
  datasheet: null,
  params_reviewed: 0,
  params_to_review: 0,
  verdict: "no_datasheet",
  ...over,
});

export const detail = (over: Partial<EquipmentDetail> = {}): EquipmentDetail => ({
  ...summary(),
  datasheet: sheet(),
  params_to_review: 1,
  verdict: "to_confirm",
  sources: [
    { project: "R9", block_key: "ele.cte.condicoes_tecnicas_especiais.entrada_de_energia", entry: 3, unit: 9, text: "Portinhola de exemplo, referência +100, ou equivalente." },
  ],
  image: { project: "R9", block_key: "ele.cte.condicoes_tecnicas_especiais.entrada_de_energia", entry: 4 },
  params: [
    { id: "pc1", name: "ip_rating", label: "Índice de proteção (IP)", value: "IP55", shown: "IP55", unit: "", origin: "cte", text: "IP55", page: null, datasheet_id: null, review_status: "extracted", reviewed_by: null },
    { id: "pa1", name: "ip_rating", label: "Índice de proteção (IP)", value: "IP44", shown: "IP44", unit: "", origin: "datasheet", text: "Grau de proteção IP44", page: 1, datasheet_id: "ds1", review_status: "extracted", reviewed_by: null },
  ],
  datasheets: [sheet()],
  checks: [check({ result: "unconfirmed_fails", review_status: "extracted", requirement_status: "proposed" })],
  review_note: null,
  reviewed_by: null,
  reviewed_at: null,
  ...over,
});
