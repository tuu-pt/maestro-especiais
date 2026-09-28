/** Shapes returned by the backend (backend/app/schemas.py and app/api/*.py). */

export type Role = { id: string; label: string };
export type User = { id: string; name: string; roles: Role[] };
export type DevUser = User & { login: string };

export type Project = {
  id: string;
  code: string;
  name: string;
  building_type: string | null;
  phase: "licenciamento" | "execucao";
  specialties: string[];
  public_procurement: boolean;
  status: string;
  created_at: string;
  created_by: string | null;
  file_count: number;
  ficha_status: "draft" | "confirmed" | "superseded" | null;
  open_conflicts: number;
};

export type ProjectIn = {
  code: string;
  name: string;
  building_type?: string | null;
  phase: "licenciamento" | "execucao";
  public_procurement: boolean;
};

export type IngestStatus = "pending" | "running" | "done" | "failed" | "skipped";

export type ProjectFile = {
  id: string;
  kind: string;
  filename: string;
  content_type: string | null;
  size_bytes: number;
  checksum: string;
  template_version: string | null;
  ingest_status: IngestStatus;
  ingest_message: string | null;
  ingest_warnings: string[];
  created_at: string;
  created_by: string | null;
};

export type UploadResult = { file: ProjectFile; duplicate: boolean; job_id: string | null };

export type FileEvent = {
  type?: "file";
  file_id: string;
  kind: string;
  status: IngestStatus;
  message: string | null;
  warnings?: string[];
  step: string | null;
  at: string;
};

export type SourceType = "ficha_eletrotecnica" | "calc" | "calc_sheet" | "mqt" | "drawing" | "manual";

export type Candidate = {
  value: unknown;
  source_type: SourceType;
  source_ref: string | null;
  source_file: string | null;
  file_date: string | null;
};

export type FichaValue = {
  id: string;
  key: string;
  label: string;
  value: unknown;
  unit: string | null;
  masked: boolean;
  personal_data: boolean;
  status: "confirmed" | "conflict" | "pending";
  source_type: SourceType;
  source_ref: string | null;
  source_file: string | null;
  conflict: { id: string; candidates: Candidate[] } | null;
};

export type Cal01Outcome = "ok" | "fail" | "na";

export type Circuit = {
  id: string;
  row_index: number;
  section: string | null;
  origin: string | null;
  destination: string | null;
  kva: string | null;
  ib_a: string | null;
  in_a: string | null;
  idn_ma: string | null;
  iz_a: string | null;
  i2_a: string | null;
  iz145_a: string | null;
  cable_raw: string | null;
  section_mm2: string | null;
  length_m: string | null;
  vd_section_pct: string | null;
  vd_total_pct: string | null;
  breaking_capacity_ka: string | null;
  installation: string | null;
  phases: number | null;
  source_ref: string | null;
  cal01: { ib_in_iz: Cal01Outcome; i2_iz145: Cal01Outcome };
  conflicts: CircuitConflict[];
};

export type CircuitConflict = { id: string; field: string; label: string; candidates: Candidate[] };

export type LinkStatus = "rule" | "manual" | "unlinked";

export type CircuitSheet = {
  id: string;
  origin_hint: string | null;
  destination_hint: string | null;
  source_file: string | null;
  template: string;
  values: Record<string, { value: number; ref: string }>;
  circuit_ids: string[];
  link_status: LinkStatus;
};

export type BomItem = {
  id: string;
  variant: "mqt" | "lpu";
  source_ref: string;
  source_file: string | null;
  code: string | null;
  level: number;
  kind: "chapter" | "subchapter" | "article" | "description" | "note" | "total";
  designation: string | null;
  unit: string | null;
  quantity: string | null;
  link_key: string | null;
  link_label: string | null;
  link_status: LinkStatus;
  link_rule: string | null;
};

export type LinkKey = { key: string; label: string; group: string };

export type DrawingsCheck = {
  index_sheets: number;
  pages: number;
  missing_in_pdf: string[];
  not_in_index: string[];
  matches: boolean;
};

export type Revision = {
  id: string;
  label: string;
  status: "draft" | "confirmed" | "superseded";
  confirmed_by: string | null;
  confirmed_at: string | null;
  created_at: string;
};

export type Ficha = {
  revision: Revision | null;
  revisions: Revision[];
  groups: { name: string; values: FichaValue[] }[];
  circuits: Circuit[];
  circuit_sheets: CircuitSheet[];
  bom_items: BomItem[];
  bom_link_keys: LinkKey[];
  drawings_check: DrawingsCheck | null;
  open_conflicts: number;
  can_confirm: boolean;
  cal01_note: string;
};

export type AuditEntry = {
  id: string;
  at: string;
  actor_type: "agent" | "user" | "system";
  actor_name: string;
  action: string;
  description: string;
  project_id: string | null;
  project_code: string | null;
};

// ---------------------------------------------------------------- knowledge base (screen G)

export type ReviewStatus = "proposed" | "approved" | "rejected";

export type Reviewed = {
  status: ReviewStatus;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_note: string | null;
};

export type CableOccurrence = {
  project_code: string;
  source: string;
  source_file: string;
  locator: string;
  raw_text: string;
  geometry: string | null;
};

export type CableDesignation = Reviewed & {
  id: string;
  canonical: string;
  aliases: string[];
  kind: "fio" | "cabo";
  flexible: boolean | null;
  occurrences: CableOccurrence[];
};

export type EquivalenceSide = { source: string; file: string; locator: string; raw_text: string };

export type EquivalenceEvidence = { project: string; geometry: string; a: EquivalenceSide; b: EquivalenceSide };

export type CableEquivalence = Reviewed & {
  id: string;
  a: string;
  b: string;
  reason: string;
  evidence: EquivalenceEvidence[];
};

export type Cables = { designations: CableDesignation[]; equivalences: CableEquivalence[] };

export type TextEvidence = { project: string; source: string; file?: string; locator: string; text: string };

export type TypologyTerm = Reviewed & { id: string; term: string; relation: string; evidence: TextEvidence[] };

export type Typology = Reviewed & { id: string; name: string; evidence: TextEvidence[]; terms: TypologyTerm[] };

export type KnowledgeKind = "cable-designations" | "cable-equivalences" | "typologies" | "typology-terms";

// ---------------------------------------------------------------- block library (screen G)

export type BlockMode = "fixed" | "parametric" | "adaptive";

export type BlockSummary = {
  id: string;
  key: string;
  doc_type: "MDJ" | "CTE";
  kind: "cover" | "index" | "block" | "signature";
  level: number;
  title: string;
  order: number;
  mode: BlockMode;
  status: ReviewStatus;
  activation_rule: string | null;
  projects: string[];
  required_keys: string[];
  notes: string[];
  version: number;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_note: string | null;
};

export type BlockEntry = {
  mode: BlockMode;
  project: string;
  units: Record<string, number[]>;
  text: string | null;
  keys: string[];
  single_source: boolean;
  note: string | null;
};

export type EvidenceUnit = { index: number; kind: string; text: string };

export type BlockDetail = BlockSummary & {
  entries: BlockEntry[];
  evidence: Record<string, EvidenceUnit[]>;
  labels: Record<string, string>;
  archive_refs: string[];
  equipment_slots: { entry: number; reasons: string[]; projects: string[] }[];
};

export type BlockPreview = {
  project_id: string;
  project_code: string;
  active: boolean | null;
  rule_error: string | null;
  paragraphs: { mode: BlockMode; text: string | null; missing: string[]; masked: string[] }[];
};

export type BlockEdit = { title?: string; mode?: BlockMode; activation_rule?: string; note: string };

// ---------------------------------------------------------------- regulation corpus (screen G)

export type RegulationStatus = "in_force" | "revoked" | "reference_only";

export type Regulation = {
  id: string;
  code: string;
  title: string;
  kind: "diploma" | "guia" | "especificacao" | "norma";
  edition: string | null;
  issuer: string | null;
  scope: string;
  status: RegulationStatus | null;
  citable: boolean;
  copyrighted: boolean;
  license_note: string | null;
  last_checked_at: string | null;
  review_status: "proposed" | "confirmed" | "rejected";
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  found_in: { project: string; source: string; file: string; locator: string; text: string }[];
  found_count: number;
};

// ---------------------------------------------------------------- documents and the editor (screen D)

export type SectionEvent = {
  type: "section";
  document_id: string;
  section_id: string;
  title: string;
  status: "queued" | "generating" | "generated" | "failed" | "paused";
  message: string | null;
  wait_s: number | null;
};

export type ProjectEvent = FileEvent | SectionEvent;

export type Mark = { type: "value" | "generated" | "citation"; attrs?: Record<string, unknown> };

export type TextNode = { type: "text"; text: string; marks?: Mark[] };

export type ContentNode = {
  type: "paragraph" | "locked" | "pending";
  attrs?: Record<string, unknown>;
  content?: (TextNode | ContentNode)[];
};

export type SectionContent = { type: "doc"; content: ContentNode[] };

export type Issue = { rule: string; paragraph?: string; source?: string; snippet?: string; message: string };

export type DocSection = {
  id: string;
  order: number;
  title: string;
  level: number;
  kind: "cover" | "index" | "block" | "signature";
  mode: BlockMode;
  block_key: string;
  block_status: ReviewStatus;
  block_approved: boolean;
  active: boolean;
  active_reason: string | null;
  status: "todo" | "generated" | "reviewed" | "alert";
  status_note: string | null;
  missing_keys: string[];
  locked: boolean;
  equipment_slots: Record<string, unknown>[];
  current_version: number;
  content: SectionContent;
  has_adaptive: boolean;
  proposals: number;
  unlocked: { by: string; at: string; reason: string } | null;
  activation_override: { by: string; at: string; reason: string; active: boolean; rule_result: boolean } | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  missing_data: string[];
  assumptions: string[];
  issues: Issue[];
  citations: { anchor: string; kind: string; target: string }[];
};

export type ProjectDocument = {
  id: string;
  project_id: string;
  type: "MDJ" | "CTE";
  status: string;
  ficha_revision: string;
  created_at: string;
  counts: Record<string, number>;
  sections: DocSection[] | null;
};

export type SectionVersion = {
  id: string;
  number: number;
  status: "current" | "proposed" | "rejected" | "superseded";
  author_type: "system" | "agent" | "user";
  request: string | null;
  missing_data: string[];
  assumptions: string[];
  issues: Issue[];
  created_at: string;
  created_by: string | null;
  content: SectionContent;
  citations: { anchor: string; kind: string; target: string }[];
};
