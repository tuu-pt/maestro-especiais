/** Screen Definições · the LLM providers: which ones are ready, the order, the main one (admin). */

import { useId, useState } from "react";

import { useLlmSettings, useMe, useSetPrimaryLlm } from "../api/queries";
import type { LlmProviderInfo } from "../api/types";
import { Button, Buttons, Card, ErrorNote, Pill } from "../components/ui";
import c from "./common.module.css";
import s from "./LlmSettings.module.css";

function state(p: LlmProviderInfo): { label: string; tone: "ok" | "warn" | "mute" } {
  if (p.configured) return { label: "Pronto", tone: "ok" };
  if (!p.key_set) return { label: "Sem chave no .env", tone: "mute" };
  return { label: "Sem modelo no .env", tone: "warn" };
}

export function LlmCard() {
  const { data, error } = useLlmSettings();
  const { data: me } = useMe();
  const admin = me?.roles.some((r) => r.id === "admin") ?? false;
  const save = useSetPrimaryLlm();
  const [choice, setChoice] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const base = useId();
  if (error) return <ErrorNote>{error.message}</ErrorNote>;
  if (!data) return <Card title="Modelos de linguagem (LLM)">A carregar…</Card>;
  const labels = Object.fromEntries(data.providers.map((p) => [p.name, p.label]));
  const selected = choice ?? data.primary;
  return (
    <Card title="Modelos de linguagem (LLM)">
      <p className={s.lead}>
        Cada pedido vai ao principal; se falhar (indisponível, sem ligação ou sem quota), passa ao seguinte. A guarda
        de privacidade é a mesma para todos: nenhum valor do projeto nem dado pessoal sai da aplicação.
      </p>
      <p className={s.order}>
        <b>Ordem atual:</b>{" "}
        {data.order.length ? data.order.map((n) => labels[n] ?? n).join(" → ") : "nenhum fornecedor pronto"}
      </p>
      <fieldset className={s.fieldset} disabled={!admin}>
        <legend className={s.legend}>Fornecedor principal</legend>
        <ul className={s.list}>
          {data.providers.map((p) => {
            const st = state(p);
            return (
              <li key={p.name} className={s.item}>
                <label className={s.choice}>
                  <input
                    type="radio"
                    name={`${base}-primary`}
                    value={p.name}
                    checked={selected === p.name}
                    disabled={!p.configured}
                    onChange={() => setChoice(p.name)}
                  />
                  <span className={s.name}>{p.label}</span>
                  {data.primary === p.name ? <Pill tone="info">principal</Pill> : null}
                  <Pill tone={st.tone}>{st.label}</Pill>
                </label>
                <span className={s.meta}>
                  {p.models.drafting || p.models.extraction
                    ? `Redação: ${p.models.drafting || "—"} · Extração: ${p.models.extraction || "—"}`
                    : "Sem modelo definido"}
                  {` · ${p.rpm} pedidos/min, ${p.rpd}/dia`}
                </span>
              </li>
            );
          })}
        </ul>
      </fieldset>
      {admin ? (
        <div>
          <label htmlFor={`${base}-reason`} className={s.label}>
            Porque muda (fica na auditoria)
          </label>
          <input
            id={`${base}-reason`}
            className={s.input}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          {save.error ? <ErrorNote>{save.error.message}</ErrorNote> : null}
          <Buttons>
            <Button
              variant="primary"
              small
              disabled={selected === data.primary || reason.trim().length < 3 || save.isPending}
              onClick={() =>
                save.mutate(
                  { primary: selected, reason },
                  {
                    onSuccess: () => {
                      setChoice(null);
                      setReason("");
                    },
                  },
                )
              }
            >
              Mudar o principal
            </Button>
          </Buttons>
        </div>
      ) : (
        <p className={c.loading}>Só o administrador muda o fornecedor principal. As chaves e os modelos ficam no .env.</p>
      )}
    </Card>
  );
}
