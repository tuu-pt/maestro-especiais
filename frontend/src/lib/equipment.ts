/** How screens F and G say the results of the equipment checks (Phase 7). */

import type { CheckResult, Datasheet, EquipmentVerdict } from "../api/types";
import type { Tone } from "../components/ui";

export const VERDICT: Record<EquipmentVerdict, { label: string; tone: Tone }> = {
  ok: { label: "Cumpre", tone: "ok" },
  fails: { label: "Não cumpre", tone: "crit" },
  to_confirm: { label: "Por confirmar", tone: "warn" },
  no_datasheet: { label: "Sem ficha", tone: "mute" },
  no_requirements: { label: "Sem requisitos", tone: "info" },
  no_equipment: { label: "Sem equipamento", tone: "mute" },
};

export const RESULT: Record<CheckResult, { mark: string; label: string; tone: Tone }> = {
  ok: { mark: "✓", label: "cumpre", tone: "ok" },
  fails: { mark: "✗", label: "não cumpre", tone: "crit" },
  unconfirmed_ok: { mark: "✓?", label: "cumpre, por confirmar", tone: "warn" },
  unconfirmed_fails: { mark: "✗?", label: "não cumpre, por confirmar", tone: "warn" },
  missing: { mark: "—", label: "a ficha não diz", tone: "mute" },
  not_comparable: { mark: "?", label: "não comparável", tone: "mute" },
  no_datasheet: { mark: "—", label: "sem ficha técnica", tone: "mute" },
};

export const OPERATOR: Record<string, string> = { ">=": "≥", "<=": "≤", "=": "=", ">=class": "≥", info: "" };

const MONTH = new Intl.DateTimeFormat("pt-PT", { month: "short", year: "numeric" });

export const sheetDate = (d: Datasheet | null) =>
  d?.issue_date ? MONTH.format(new Date(`${d.issue_date}T00:00:00`)) : d ? "sem data" : "—";

export const itemModel = (item: { manufacturer: string; model: string | null; reference: string | null }) =>
  [item.manufacturer, item.model, item.reference].filter(Boolean).join(" · ");
