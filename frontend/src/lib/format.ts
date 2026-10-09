/** Portuguese formatting for dates, numbers, file kinds and origins. */

import type { SourceType } from "../api/types";

/** Origin tags of the ficha-base (SPEC 10, screen C). */
export const ORIGIN_LABELS: Record<SourceType, string> = {
  ficha_eletrotecnica: "FICHA ELE",
  calc: "CÁLCULO",
  calc_sheet: "09-FOLHA",
  mqt: "MQT",
  drawing: "DES",
  manual: "MANUAL",
};

const dateTime = new Intl.DateTimeFormat("pt-PT", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});
const time = new Intl.DateTimeFormat("pt-PT", { hour: "2-digit", minute: "2-digit" });
const number = new Intl.NumberFormat("pt-PT", { maximumFractionDigits: 3 });

export const formatDateTime = (iso: string) => dateTime.format(new Date(iso));
export const formatTime = (iso: string) => time.format(new Date(iso));

/** Values of the ficha-base as people read them: 34,5 · lists joined · empty as a dash. */
export function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") return number.format(value);
  if (typeof value === "string" && /^-?\d+(\.\d+)?$/.test(value)) return number.format(Number(value));
  if (Array.isArray(value)) return value.map(formatValue).join(", ");
  return String(value);
}

export const KIND_LABELS: Record<string, string> = {
  ficha_eletrotecnica: "Ficha eletrotécnica",
  calc_summary: "Tabela de Cálculo",
  calc_circuit: "09-Folha de Cálculo",
  mqt: "Mapa de quantidades",
  lpu: "Lista de preços unitários",
  drawing_pdf: "Peças desenhadas (PDF)",
  drawing_dwg: "Peças desenhadas (DWG)",
  archive_docx: "Documento",
  mdj_docx: "MDJ existente",
  cte_docx: "CTE existente",
  identificacao_docx: "Identificação existente",
  termo_docx: "Termo existente",
  other: "Outro ficheiro",
};

export const kindLabel = (kind: string) => KIND_LABELS[kind] ?? "Outro ficheiro";

export function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${number.format(Math.round(bytes / 102.4) / 10)} KB`;
  return `${number.format(Math.round(bytes / (1024 * 102.4)) / 10)} MB`;
}

/** A time of the pilot: minutes up to 90, then hours with a decimal comma. */
export function duration(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds < 90 * 60) return `${Math.round(seconds / 60)} min`;
  return `${(seconds / 3600).toFixed(1).replace(".", ",")} h`;
}

export function percent(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 100)} %`;
}
