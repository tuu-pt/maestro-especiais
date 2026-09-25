/** Screen G · Corpus regulamentar: the references of Annex D, confirmed one by one by the curator. */

import { useId, useState } from "react";

import { useCitable, useMe, useRegulations, useReviewRegulation } from "../api/queries";
import type { Regulation, RegulationStatus } from "../api/types";
import { Button, Buttons, Chip, EmptyState, ErrorNote, Pill, type Tone } from "../components/ui";
import { formatDateTime } from "../lib/format";
import s from "./Corpus.module.css";
import { Loading } from "./common";

const REVIEW: Record<Regulation["review_status"], { label: string; tone: Tone }> = {
  proposed: { label: "A confirmar", tone: "warn" },
  confirmed: { label: "Confirmado", tone: "ok" },
  rejected: { label: "Rejeitado", tone: "mute" },
};
const LEGAL: Record<RegulationStatus, string> = {
  in_force: "Em vigor",
  revoked: "Revogado",
  reference_only: "Só referência",
};
const KIND: Record<Regulation["kind"], string> = {
  diploma: "Diploma",
  guia: "Guia técnico",
  especificacao: "Especificação",
  norma: "Norma",
};

export function CorpusPanel() {
  const { data, isPending, error } = useRegulations();
  if (isPending) return <Loading />;
  if (error) return <ErrorNote>{error.message}</ErrorNote>;
  if (data.length === 0) {
    return (
      <EmptyState
        title="Ainda não há documentos no corpus"
        next="Diplomas e normas com o estado (em vigor, revogado, só referência). Só se cita o que um curador marcar como citável; das normas com direitos de autor guarda-se só o título e o âmbito."
      >
        O corpus começa pela lista do Anexo D da especificação, com tudo por confirmar. As propostas são geradas com o
        comando make seed-library, corrido pela equipa.
      </EmptyState>
    );
  }
  const citable = data.filter((r) => r.citable).length;
  return (
    <div className={s.stack}>
      <p className={s.lead}>
        {data.length} referência{data.length === 1 ? "" : "s"} dos projetos de referência · {citable} citáve
        {citable === 1 ? "l" : "is"}. O curador confirma a edição em vigor de cada uma antes de a marcar como citável;
        das normas com direitos de autor guarda-se só o título e o âmbito. A pesquisa no texto integral fica para mais
        tarde.
      </p>
      <ul className={s.list}>
        {data.map((r) => (
          <RegulationCard key={r.id} doc={r} />
        ))}
      </ul>
    </div>
  );
}

function RegulationCard({ doc: r }: { doc: Regulation }) {
  const titleId = useId();
  return (
    <li className={s.card} aria-labelledby={titleId}>
      <div className={s.head}>
        <h3 id={titleId} className={s.title}>
          {r.title}
        </h3>
        <div className={s.meta}>
          <Chip>{KIND[r.kind]}</Chip>
          {r.issuer ? <Chip>{r.issuer}</Chip> : null}
          <Pill tone={REVIEW[r.review_status].tone}>{REVIEW[r.review_status].label}</Pill>
          {r.status ? <Pill tone={r.status === "in_force" ? "ok" : "mute"}>{LEGAL[r.status]}</Pill> : null}
          <Pill tone={r.citable ? "ok" : "mute"}>{r.citable ? "Citável" : "Não citável"}</Pill>
        </div>
      </div>
      <p className={s.scope}>{r.scope}</p>
      {r.license_note ? <p className={s.muted}>{r.license_note}</p> : null}
      <p className={s.muted}>
        {r.edition ? `Edição: ${r.edition}. ` : ""}
        {r.last_checked_at ? `Verificado em ${formatDateTime(r.last_checked_at)}.` : "Ainda não verificado."}
        {r.review_note ? ` “${r.review_note}”` : ""}
      </p>
      {r.found_count > 0 ? (
        <details className={s.found}>
          <summary>
            Citado {r.found_count} vez{r.found_count === 1 ? "" : "es"} nos projetos de referência
          </summary>
          <ul>
            {r.found_in.map((f, i) => (
              <li key={i}>
                <span>{f.text}</span>
                <span className={s.muted}>
                  {f.project} · {f.source} · {f.file} · {f.locator}
                </span>
              </li>
            ))}
          </ul>
        </details>
      ) : (
        <p className={s.muted}>Não aparece nos documentos de referência (R1, R2).</p>
      )}
      <CuratorControls doc={r} />
    </li>
  );
}

function CuratorControls({ doc: r }: { doc: Regulation }) {
  const { data: me } = useMe();
  const curator = me?.roles.some((role) => role.id === "curador") ?? false;
  const review = useReviewRegulation(r.id);
  const citable = useCitable(r.id);
  const [legal, setLegal] = useState<RegulationStatus | "">(r.status ?? "");
  const [edition, setEdition] = useState(r.edition ?? "");
  const [note, setNote] = useState("");
  const base = useId();
  if (!curator) return <p className={s.muted}>Só um curador pode confirmar, rejeitar ou marcar como citável.</p>;
  const error = review.error ?? citable.error;
  return (
    <div className={s.controls}>
      <div className={s.fields}>
        <label htmlFor={`${base}-legal`} className={s.label}>
          Estado do documento
        </label>
        <select
          id={`${base}-legal`}
          value={legal}
          onChange={(e) => setLegal(e.target.value as RegulationStatus | "")}
          className={s.input}
        >
          <option value="">Por decidir</option>
          {(Object.keys(LEGAL) as RegulationStatus[]).map((k) => (
            <option key={k} value={k}>
              {LEGAL[k]}
            </option>
          ))}
        </select>
        <label htmlFor={`${base}-edition`} className={s.label}>
          Edição em vigor
        </label>
        <input
          id={`${base}-edition`}
          value={edition}
          onChange={(e) => setEdition(e.target.value)}
          className={s.input}
          placeholder="ex.: na redação atual"
        />
        <label htmlFor={`${base}-note`} className={s.label}>
          Nota (opcional, fica registada)
        </label>
        <textarea
          id={`${base}-note`}
          rows={2}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          className={s.input}
        />
      </div>
      {error ? <ErrorNote>{error.message}</ErrorNote> : null}
      <Buttons>
        <Button
          variant="primary"
          small
          disabled={review.isPending || legal === ""}
          onClick={() => review.mutate({ decision: "confirmed", status: legal || undefined, edition, note })}
          aria-label={`Confirmar ${r.title}`}
        >
          Confirmar
        </Button>
        <Button
          small
          disabled={review.isPending || r.review_status === "rejected"}
          onClick={() => review.mutate({ decision: "rejected", note })}
          aria-label={`Rejeitar ${r.title}`}
        >
          Rejeitar
        </Button>
        <Button
          small
          disabled={citable.isPending || (!r.citable && (r.review_status !== "confirmed" || r.status !== "in_force"))}
          onClick={() => citable.mutate({ citable: !r.citable, note })}
          aria-label={`${r.citable ? "Deixar de citar" : "Marcar como citável"} ${r.title}`}
        >
          {r.citable ? "Deixar de citar" : "Marcar como citável"}
        </Button>
      </Buttons>
    </div>
  );
}
