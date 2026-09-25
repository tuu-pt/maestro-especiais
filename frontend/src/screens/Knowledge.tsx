/** Screen G: the knowledge base. Everything the agent seeds is "proposto" until a curator decides. */

import { type KeyboardEvent, useId, useRef, useState } from "react";
import { useSearchParams } from "react-router";

import { useCables, useMe, useReview, useTypologies } from "../api/queries";
import type {
  CableDesignation,
  CableEquivalence,
  KnowledgeKind,
  Reviewed,
  ReviewStatus,
  TextEvidence,
  Typology,
} from "../api/types";
import { Button, Buttons, Card, Chip, DataTable, EmptyState, ErrorNote, Pill, type Tone } from "../components/ui";
import { formatDateTime } from "../lib/format";
import { BlocksPanel } from "./Blocks";
import { Loading } from "./common";
import { CorpusPanel } from "./Corpus";
import s from "./Knowledge.module.css";
import { Screen } from "./Screen";

const TABS = [
  { id: "cabos", label: "Dicionário de cabos" },
  { id: "lexico", label: "Léxico de tipologias" },
  { id: "blocos", label: "Biblioteca de blocos" },
  { id: "corpus", label: "Corpus regulamentar" },
  { id: "arquivo", label: "Arquivo TUU" },
] as const;
type TabId = (typeof TABS)[number]["id"];

const STATUS: Record<ReviewStatus, { label: string; tone: Tone }> = {
  proposed: { label: "Proposto", tone: "warn" },
  approved: { label: "Aprovado", tone: "ok" },
  rejected: { label: "Rejeitado", tone: "mute" },
};

const SEED_HINT =
  "As propostas são geradas a partir dos projetos de referência anonimizados (R1 e R2) com o comando make seed-library, corrido pela equipa.";

export function KnowledgeScreen() {
  const [params, setParams] = useSearchParams();
  const current: TabId = TABS.find((t) => t.id === params.get("separador"))?.id ?? "cabos";
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const base = useId();

  const select = (id: TabId, focus = false) => {
    setParams({ separador: id }, { replace: true });
    if (focus) refs.current[id]?.focus();
  };
  const onKey = (e: KeyboardEvent) => {
    const i = TABS.findIndex((t) => t.id === current);
    const next = {
      ArrowRight: i + 1,
      ArrowLeft: i - 1,
      Home: 0,
      End: TABS.length - 1,
    }[e.key];
    if (next === undefined) return;
    e.preventDefault();
    const tab = TABS[(next + TABS.length) % TABS.length];
    if (tab) select(tab.id, true);
  };

  return (
    <Screen
      title="Base de conhecimento"
      description="Aquilo em que o agente se apoia. Tudo o que o agente propõe fica “proposto” até um curador aprovar ou rejeitar, e cada decisão fica na auditoria."
    >
      <div role="tablist" aria-label="Secções da base de conhecimento" className={s.tabs} onKeyDown={onKey}>
        {TABS.map((t) => (
          <button
            key={t.id}
            ref={(el) => {
              refs.current[t.id] = el;
            }}
            type="button"
            role="tab"
            id={`${base}-${t.id}-tab`}
            aria-selected={t.id === current}
            aria-controls={`${base}-${t.id}-panel`}
            tabIndex={t.id === current ? 0 : -1}
            onClick={() => select(t.id)}
            className={s.tab}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`${base}-${current}-panel`}
        aria-labelledby={`${base}-${current}-tab`}
        className={s.panel}
      >
        {current === "cabos" ? <CablesPanel /> : null}
        {current === "lexico" ? <LexiconPanel /> : null}
        {current === "blocos" ? <BlocksPanel /> : null}
        {current === "corpus" ? <CorpusPanel /> : null}
        {current === "arquivo" ? (
          <EmptyState
            title="O arquivo ainda está vazio"
            next="MDJ e CTE aprovados, divididos por bloco e com os valores do projeto trocados por marcadores, usados como base dos blocos adaptativos."
          >
            O arquivo é preenchido com a biblioteca de blocos.
          </EmptyState>
        ) : null}
      </div>
    </Screen>
  );
}

// ---------------------------------------------------------------- review controls

function useIsCurator(): boolean {
  const { data: me } = useMe();
  return me?.roles.some((r) => r.id === "curador") ?? false;
}

function StatusPill({ item }: { item: Reviewed }) {
  const { label, tone } = STATUS[item.status];
  return <Pill tone={tone}>{label}</Pill>;
}

/** Approve or reject, with an optional note. Only a curator sees the buttons. */
function ReviewControls({ kind, id, item, what }: { kind: KnowledgeKind; id: string; item: Reviewed; what: string }) {
  const curator = useIsCurator();
  const review = useReview();
  const [note, setNote] = useState("");
  const noteId = useId();
  const decide = (decision: "approved" | "rejected") =>
    review.mutate({ kind, id, decision, note }, { onSuccess: () => setNote("") });

  return (
    <div className={s.review}>
      <div className={s.reviewState}>
        <StatusPill item={item} />
        {item.reviewed_at ? (
          <span className={s.muted}>
            {STATUS[item.status].label} em {formatDateTime(item.reviewed_at)}
            {item.review_note ? ` · “${item.review_note}”` : ""}
          </span>
        ) : null}
      </div>
      {curator ? (
        <>
          <label htmlFor={noteId} className={s.noteLabel}>
            Nota do curador (opcional, fica registada)
          </label>
          <textarea id={noteId} rows={2} value={note} onChange={(e) => setNote(e.target.value)} className={s.input} />
          {review.error ? <ErrorNote>{review.error.message}</ErrorNote> : null}
          <Buttons>
            <Button
              variant="primary"
              small
              disabled={review.isPending || item.status === "approved"}
              onClick={() => decide("approved")}
              aria-label={`Aprovar ${what}`}
            >
              Aprovar
            </Button>
            <Button
              small
              disabled={review.isPending || item.status === "rejected"}
              onClick={() => decide("rejected")}
              aria-label={`Rejeitar ${what}`}
            >
              Rejeitar
            </Button>
          </Buttons>
        </>
      ) : (
        <p className={s.muted}>Só um curador pode aprovar ou rejeitar.</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- cables

function flexibleLabel(d: CableDesignation): string {
  if (d.flexible === null) return "—";
  return d.flexible ? "Flexível" : "Rígido";
}

/** "R1 · MDJ (3)": where a designation appears, counted by project and source. */
function whereFound(d: CableDesignation): string[] {
  const counts = new Map<string, number>();
  for (const o of d.occurrences) {
    const key = `${o.project_code} · ${o.source}`;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts].map(([key, n]) => `${key} (${n})`);
}

function CablesPanel() {
  const { data, isPending, error } = useCables();
  if (isPending) return <Loading />;
  if (error) return <ErrorNote>{error.message}</ErrorNote>;
  if (data.designations.length === 0) {
    return (
      <EmptyState
        title="Ainda não há designações de cabos"
        next="Cada designação vai aparecer tal como está escrita e onde (Tabela de Cálculo, 09-Folhas, MQT/LPU, MDJ, CTE), com as equivalências propostas e a evidência de cada uma."
      >
        {SEED_HINT}
      </EmptyState>
    );
  }
  return (
    <div className={s.stack}>
      <Card title="Equivalências propostas">
        <p className={s.lead}>
          Só se propõe uma equivalência quando, no mesmo projeto, a mesma secção aparece com as duas designações em
          fontes diferentes. Um fio rígido (-U, -R) nunca é proposto como equivalente a um flexível (-K, -F).
        </p>
        {data.equivalences.length === 0 ? (
          <p className={s.muted}>Não há equivalências propostas.</p>
        ) : (
          <ul className={s.list}>
            {data.equivalences.map((e) => (
              <EquivalenceItem key={e.id} equivalence={e} />
            ))}
          </ul>
        )}
      </Card>
      <DataTable caption="Designações de cabos encontradas">
        <thead>
          <tr>
            <th scope="col">Designação</th>
            <th scope="col">Tipo</th>
            <th scope="col">Condutor</th>
            <th scope="col">Onde aparece</th>
            <th scope="col">Estado</th>
          </tr>
        </thead>
        <tbody>
          {data.designations.map((d) => (
            <tr key={d.id}>
              <td>
                <b className={s.mono}>{d.canonical}</b>
                {d.aliases.length ? <div className={s.muted}>Equivalente a {d.aliases.join(", ")}</div> : null}
                <details className={s.occurrences}>
                  <summary>
                    {d.occurrences.length} ocorrência
                    {d.occurrences.length === 1 ? "" : "s"}
                  </summary>
                  <ul>
                    {d.occurrences.slice(0, 30).map((o, i) => (
                      <li key={i}>
                        <span className={s.mono}>{o.raw_text}</span>
                        <span className={s.muted}>
                          {o.project_code} · {o.source} · {o.source_file} · {o.locator}
                        </span>
                      </li>
                    ))}
                    {d.occurrences.length > 30 ? (
                      <li className={s.muted}>e mais {d.occurrences.length - 30}.</li>
                    ) : null}
                  </ul>
                </details>
              </td>
              <td>{d.kind === "fio" ? "Fio" : "Cabo"}</td>
              <td>{flexibleLabel(d)}</td>
              <td>
                <div className={s.chips}>
                  {whereFound(d).map((w) => (
                    <Chip key={w}>{w}</Chip>
                  ))}
                </div>
              </td>
              <td>
                <StatusPill item={d} />
              </td>
            </tr>
          ))}
        </tbody>
      </DataTable>
    </div>
  );
}

function EquivalenceItem({ equivalence: e }: { equivalence: CableEquivalence }) {
  const title = `${e.a} ≈ ${e.b}`;
  return (
    <li className={s.item}>
      <h5 className={s.itemTitle}>
        <span className={s.mono}>{title}</span>
      </h5>
      <p className={s.muted}>{e.reason}</p>
      <ul className={s.evidenceList} aria-label={`Evidência de ${title}`}>
        {e.evidence.map((ev, i) => (
          <li key={i} className={s.sideBySide}>
            <div className={s.evidenceHead}>
              {ev.project} · secção {ev.geometry}
            </div>
            {[ev.a, ev.b].map((side, j) => (
              <div key={j} className={s.side}>
                <span className={s.mono}>{side.raw_text}</span>
                <span className={s.muted}>
                  {side.source} · {side.file} · {side.locator}
                </span>
              </div>
            ))}
          </li>
        ))}
      </ul>
      <ReviewControls kind="cable-equivalences" id={e.id} item={e} what={`a equivalência ${title}`} />
    </li>
  );
}

// ---------------------------------------------------------------- lexicon

function Evidence({ items, label }: { items: TextEvidence[]; label: string }) {
  if (items.length === 0) return <p className={s.muted}>Sem ocorrências nos documentos de referência.</p>;
  return (
    <ul className={s.evidenceList} aria-label={label}>
      {items.map((ev, i) => (
        <li key={i} className={s.side}>
          <span>{ev.text}</span>
          <span className={s.muted}>
            {ev.project} · {ev.source}
            {ev.file ? ` · ${ev.file}` : ""} · {ev.locator}
          </span>
        </li>
      ))}
    </ul>
  );
}

function LexiconPanel() {
  const { data, isPending, error } = useTypologies();
  if (isPending) return <Loading />;
  if (error) return <ErrorNote>{error.message}</ErrorNote>;
  if (data.length === 0) {
    return (
      <EmptyState
        title="Ainda não há tipologias no léxico"
        next="Cada tipologia dos projetos de referência vai aparecer com os termos incompatíveis (ex.: “apartamento” numa moradia unifamiliar) e onde foram encontrados."
      >
        {SEED_HINT}
      </EmptyState>
    );
  }
  return (
    <div className={s.stack}>
      {data.map((t) => (
        <TypologyCard key={t.id} typology={t} />
      ))}
    </div>
  );
}

function TypologyCard({ typology: t }: { typology: Typology }) {
  return (
    <Card title={`Tipologia: ${t.name}`}>
      <Evidence items={t.evidence} label={`Evidência da tipologia ${t.name}`} />
      <ReviewControls kind="typologies" id={t.id} item={t} what={`a tipologia ${t.name}`} />
      <h5 className={s.subhead}>Termos incompatíveis</h5>
      <ul className={s.list}>
        {t.terms.map((term) => (
          <li key={term.id} className={s.item}>
            <h6 className={s.itemTitle}>
              «{term.term}»
              {term.evidence.length ? (
                <Pill tone="info">
                  encontrado {term.evidence.length} vez
                  {term.evidence.length === 1 ? "" : "es"}
                </Pill>
              ) : null}
            </h6>
            <Evidence items={term.evidence} label={`Onde aparece «${term.term}»`} />
            <ReviewControls
              kind="typology-terms"
              id={term.id}
              item={term}
              what={`o termo ${term.term} para ${t.name}`}
            />
          </li>
        ))}
      </ul>
    </Card>
  );
}
