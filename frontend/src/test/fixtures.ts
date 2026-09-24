/** API payloads for component tests. Shapes of the backend, invented values (tests only). */

import type { Ficha, Project, ProjectFile } from "../api/types";

export const project = (over: Partial<Project> = {}): Project => ({
  id: "p1",
  code: "R9",
  name: "Moradia",
  building_type: "Moradia unifamiliar",
  phase: "execucao",
  specialties: ["ELE"],
  public_procurement: false,
  status: "active",
  created_at: "2026-09-24T10:00:00Z",
  created_by: "dev:redator",
  file_count: 0,
  ficha_status: null,
  open_conflicts: 0,
  ...over,
});

export const file = (over: Partial<ProjectFile> = {}): ProjectFile => ({
  id: "f1",
  kind: "ficha_eletrotecnica",
  filename: "FE.xlsm",
  content_type: null,
  size_bytes: 20480,
  checksum: "a".repeat(64),
  template_version: "FE_v.20190222",
  ingest_status: "pending",
  ingest_message: null,
  created_at: "2026-09-24T10:01:00Z",
  created_by: "dev:redator",
  ...over,
});

export const emptyFicha = (): Ficha => ({
  revision: null,
  revisions: [],
  groups: ["Identificação", "Imóvel", "Alimentação", "Distribuição", "Sistemas", "Equipamentos", "Peças desenhadas"].map(
    (name) => ({ name, values: [] }),
  ),
  circuits: [],
  open_conflicts: 0,
  can_confirm: false,
  cal01_note: "Queda de tensão e poder de corte: a verificação fica disponível quando houver MDJ com os limites do projeto.",
});

export const sse = (...events: object[]) =>
  events.map((e) => `event: file\ndata: ${JSON.stringify(e)}\n\n`).join("");
