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
  file_id: string;
  kind: string;
  status: IngestStatus;
  message: string | null;
  warnings?: string[];
  step: string | null;
  at: string;
};

export type SourceType = "ficha_eletrotecnica" | "calc" | "mqt" | "drawing" | "manual";

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
  length_m: string | null;
  vd_total_pct: string | null;
  breaking_capacity_ka: string | null;
  installation: string | null;
  phases: number | null;
  source_ref: string | null;
  cal01: { ib_in_iz: Cal01Outcome; i2_iz145: Cal01Outcome };
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
