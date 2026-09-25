/** Screen G · Biblioteca de blocos: what the agent proposed from the reference MDJ/CTE, for the curator. */

import { Fragment, useId, useState } from "react";
import { useSearchParams } from "react-router";

import {
  useBlock,
  useBlockAction,
  useBlockHistory,
  useBlockPreview,
  useBlocks,
  useMe,
  useProjects,
} from "../api/queries";
import type { BlockDetail, BlockEntry, BlockMode, BlockSummary, ReviewStatus } from "../api/types";
import {
  BlockModeBadge,
  Button,
  Buttons,
  Chip,
  EmptyState,
  ErrorNote,
  Pill,
  Timeline,
  type Tone,
} from "../components/ui";
import { formatDateTime } from "../lib/format";
import s from "./Blocks.module.css";
import { Loading } from "./common";

const STATUS: Record<ReviewStatus, { label: string; tone: Tone }> = {
  proposed: { label: "Proposto", tone: "warn" },
  approved: { label: "Aprovado", tone: "ok" },
  rejected: { label: "Rejeitado", tone: "mute" },
};
const KIND: Record<BlockSummary["kind"], string> = {
  cover: "Capa",
  index: "Índice",
  block: "",
  signature: "Assinatura",
};
const MODES: BlockMode[] = ["fixed", "parametric", "adaptive"];
const MODE_TEXT: Record<BlockMode, string> = {
  fixed: "copiado com o OOXML original",
  parametric: "preenchido com valores da ficha",
  adaptive: "adaptado a cada projeto (Fase 4)",
};
const PLACEHOLDER = /\{\{v:([a-z0-9_.]+)\}\}/g;

/** Text with each {{v:key}} shown as a highlighted label (the key on hover). */
export function WithPlaceholders({ text, labels }: { text: string; labels: Record<string, string> }) {
  const parts: (string | { key: string })[] = [];
  let last = 0;
  for (const m of text.matchAll(PLACEHOLDER)) {
    parts.push(text.slice(last, m.index), { key: m[1]! });
    last = (m.index ?? 0) + m[0].length;
  }
  parts.push(text.slice(last));
  return (
    <>
      {parts.map((p, i) =>
        typeof p === "string" ? (
          <Fragment key={i}>{p}</Fragment>
        ) : (
          <mark key={i} className={s.placeholder} title={`{{v:${p.key}}}`}>
            {labels[p.key] ?? p.key}
          </mark>
        ),
      )}
    </>
  );
}

function StatusPill({ status }: { status: ReviewStatus }) {
  return <Pill tone={STATUS[status].tone}>{STATUS[status].label}</Pill>;
}

export function BlocksPanel() {
  const { data: blocks, isPending, error } = useBlocks();
  const [params, setParams] = useSearchParams();
  const docType = params.get("doc") === "CTE" ? "CTE" : "MDJ";
  const selected = params.get("bloco") ?? undefined;
  const update = (next: Record<string, string>) =>
    setParams(
      { separador: "blocos", doc: docType, ...(selected ? { bloco: selected } : {}), ...next },
      { replace: true },
    );

  if (isPending) return <Loading />;
  if (error) return <ErrorNote>{error.message}</ErrorNote>;
  if (blocks.length === 0) {
    return (
      <EmptyState
        title="Ainda não há blocos propostos"
        next="Aqui vão aparecer os blocos do MDJ e do CTE com o modo (fixo, paramétrico, adaptativo), a regra de ativação, a evidência de R1 e R2 e a pré-visualização."
      >
        A biblioteca é extraída das MDJ e dos CTE dos projetos de referência. As propostas são geradas a partir dos
        projetos de referência anonimizados (R1 e R2) com o comando make seed-library, corrido pela equipa.
      </EmptyState>
    );
  }
  const shown = blocks.filter((b) => b.doc_type === docType);
  const counts = (st: ReviewStatus) => shown.filter((b) => b.status === st).length;
  return (
    <div className={s.layout}>
      <div className={s.listPane}>
        <div className={s.filters} role="group" aria-label="Documento">
          {(["MDJ", "CTE"] as const).map((d) => (
            <button key={d} type="button" aria-pressed={docType === d} onClick={() => update({ doc: d, bloco: "" })}>
              {d === "MDJ" ? "Memória descritiva (MDJ)" : "Condições técnicas (CTE)"}
            </button>
          ))}
        </div>
        <p className={s.muted}>
          {shown.length} blocos · {counts("proposed")} propostos · {counts("approved")} aprovados · {counts("rejected")}{" "}
          rejeitados
        </p>
        {shown.length === 0 ? (
          <p className={s.muted}>Ainda não há blocos deste documento.</p>
        ) : (
          <ol className={s.list} aria-label={`Blocos do ${docType}`}>
            {shown.map((b) => (
              <li key={b.id}>
                <button
                  type="button"
                  className={s.item}
                  aria-current={b.id === selected ? "true" : undefined}
                  onClick={() => update({ bloco: b.id })}
                >
                  <span className={s.itemTitle}>
                    <span className={s.order}>{b.order}.</span>
                    {b.level === 2 ? <span aria-hidden="true">↳ </span> : null}
                    {KIND[b.kind] || b.title}
                  </span>
                  <span className={s.itemMeta}>
                    <BlockModeBadge mode={b.mode} />
                    <StatusPill status={b.status} />
                    {b.projects.length === 1 ? <Chip>só {b.projects[0]}</Chip> : null}
                    {b.projects.length === 0 ? <Chip>esqueleto</Chip> : null}
                  </span>
                </button>
              </li>
            ))}
          </ol>
        )}
      </div>
      <div className={s.detailPane}>
        {selected && shown.some((b) => b.id === selected) ? (
          <BlockView id={selected} />
        ) : (
          <EmptyState
            title="Escolha um bloco"
            next="Vai ver os parágrafos, a evidência de R1 e R2, a regra e a pré-visualização."
          >
            Cada bloco foi proposto pelo agente e fica «proposto» até um curador o aprovar, editar ou rejeitar.
          </EmptyState>
        )}
      </div>
    </div>
  );
}

function BlockView({ id }: { id: string }) {
  const { data: b, isPending, error } = useBlock(id);
  if (isPending) return <Loading />;
  if (error) return <ErrorNote>{error.message}</ErrorNote>;
  const titleId = `block-${b.id}`;
  return (
    <article className={s.detail} aria-labelledby={titleId}>
      <header className={s.head}>
        <h3 id={titleId} className={s.title}>
          {b.title}
        </h3>
        <p className={s.key}>{b.key}</p>
        <div className={s.itemMeta}>
          <BlockModeBadge mode={b.mode} />
          <StatusPill status={b.status} />
          {b.projects.map((p) => (
            <Chip key={p}>{p}</Chip>
          ))}
        </div>
        <p className={s.muted}>
          Modo {b.mode === "fixed" ? "fixo" : b.mode === "parametric" ? "paramétrico" : "adaptativo"}:{" "}
          {MODE_TEXT[b.mode]}.{b.reviewed_at ? ` ${STATUS[b.status].label} em ${formatDateTime(b.reviewed_at)}.` : ""}
          {b.review_note ? ` “${b.review_note}”` : ""}
        </p>
      </header>
      {b.notes.length ? (
        <ul className={s.notes} aria-label="Notas para o curador">
          {b.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      ) : null}
      <section aria-labelledby={`${titleId}-rule`}>
        <h4 id={`${titleId}-rule`} className={s.h4}>
          Regra de ativação
        </h4>
        <code className={s.rule}>{b.activation_rule ?? "true"}</code>
      </section>
      <Preview block={b} />
      <section aria-labelledby={`${titleId}-body`}>
        <h4 id={`${titleId}-body`} className={s.h4}>
          Parágrafos e evidência
        </h4>
        {b.entries.length === 0 ? (
          <p className={s.muted}>Sem texto: nenhum projeto de referência tem este bloco.</p>
        ) : (
          <ol className={s.entries}>
            {b.entries.map((e, i) => (
              <EntryView key={i} entry={e} block={b} slot={b.equipment_slots.find((x) => x.entry === i)} />
            ))}
          </ol>
        )}
      </section>
      <Actions block={b} />
      <History id={b.id} />
    </article>
  );
}

function unitOf(b: BlockDetail, project: string, index: number) {
  return b.evidence[project]?.find((u) => u.index === index);
}

function EntryView({
  entry: e,
  block: b,
  slot,
}: {
  entry: BlockEntry;
  block: BlockDetail;
  slot?: BlockDetail["equipment_slots"][number];
}) {
  const projects = Object.keys(e.units);
  const empty =
    e.mode === "fixed" && !e.text && projects.every((p) => e.units[p]!.every((i) => !unitOf(b, p, i)?.text));
  if (empty) return null; // an empty paragraph (layout)
  return (
    <li className={s.entry}>
      <div className={s.entryHead}>
        <BlockModeBadge mode={e.mode} />
        {e.single_source ? <Chip>evidência de um só projeto</Chip> : null}
        {slot ? <Chip>equipamento de referência ({slot.reasons.join(", ")})</Chip> : null}
        {e.note ? <span className={s.muted}>{e.note}</span> : null}
      </div>
      {e.text ? (
        <p className={s.template}>
          <WithPlaceholders text={e.text} labels={b.labels} />
        </p>
      ) : e.mode === "adaptive" ? (
        <p className={s.muted}>
          O texto é adaptado a cada projeto na Fase 4, a partir do arquivo ({b.archive_refs.join(", ")}).
        </p>
      ) : null}
      {e.mode !== "fixed" || e.note ? (
        <div className={s.sides} aria-label="Evidência lado a lado">
          {projects.map((p) => (
            <div key={p} className={s.side}>
              <span className={s.sideHead}>{p}</span>
              {e.units[p]!.map((i) => {
                const unit = unitOf(b, p, i);
                return unit?.text ? (
                  <p key={i}>
                    <WithPlaceholders text={unit.text} labels={b.labels} />
                  </p>
                ) : null;
              })}
            </div>
          ))}
        </div>
      ) : null}
    </li>
  );
}

function Preview({ block }: { block: BlockDetail }) {
  const { data: projects = [] } = useProjects();
  const [projectId, setProjectId] = useState<string>("");
  const { data: preview, error } = useBlockPreview(block.id, projectId || undefined);
  const selectId = useId();
  return (
    <section aria-labelledby={`${selectId}-h`} className={s.preview}>
      <h4 id={`${selectId}-h`} className={s.h4}>
        Pré-visualização com a ficha de um projeto
      </h4>
      {projects.length === 0 ? (
        <p className={s.muted}>
          Crie um projeto e carregue a ficha eletrotécnica para ver este bloco com os valores reais.
        </p>
      ) : (
        <>
          <label htmlFor={selectId} className={s.label}>
            Projeto
          </label>
          <select id={selectId} value={projectId} onChange={(e) => setProjectId(e.target.value)} className={s.input}>
            <option value="">Escolha um projeto…</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.code} · {p.name}
              </option>
            ))}
          </select>
        </>
      )}
      {error ? <ErrorNote>{error.message}</ErrorNote> : null}
      {preview ? (
        <div className={s.previewBody}>
          <p>
            {preview.rule_error ? (
              <Pill tone="crit">Regra inválida: {preview.rule_error}</Pill>
            ) : preview.active ? (
              <Pill tone="ok">A regra ativa este bloco em {preview.project_code}</Pill>
            ) : (
              <Pill tone="mute">A regra não ativa este bloco em {preview.project_code}</Pill>
            )}
          </p>
          {preview.paragraphs.map((p, i) =>
            p.text?.trim() ? (
              <p key={i} className={s.resolved}>
                {p.text}
              </p>
            ) : p.mode === "adaptive" ? (
              <p key={i} className={s.muted}>
                [texto adaptativo: escrito na Fase 4]
              </p>
            ) : null,
          )}
          <p className={s.muted}>Os dados pessoais aparecem mascarados (•••). Nada é gravado.</p>
        </div>
      ) : null}
    </section>
  );
}

function Actions({ block: b }: { block: BlockDetail }) {
  const { data: me } = useMe();
  const curator = me?.roles.some((r) => r.id === "curador") ?? false;
  const action = useBlockAction(b.id);
  const [note, setNote] = useState("");
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(b.title);
  const [mode, setMode] = useState<BlockMode>(b.mode);
  const [rule, setRule] = useState(b.activation_rule ?? "true");
  const base = useId();
  if (!curator) return <p className={s.muted}>Só um curador pode aprovar, editar ou rejeitar blocos.</p>;
  const decide = (decision: "approved" | "rejected") =>
    action.mutate({ decision, note }, { onSuccess: () => setNote("") });
  const save = () =>
    action.mutate(
      {
        edit: {
          note,
          ...(title !== b.title ? { title } : {}),
          ...(mode !== b.mode ? { mode } : {}),
          ...(rule !== (b.activation_rule ?? "true") ? { activation_rule: rule } : {}),
        },
      },
      {
        onSuccess: () => {
          setEditing(false);
          setNote("");
        },
      },
    );
  return (
    <section aria-labelledby={`${base}-h`} className={s.actions}>
      <h4 id={`${base}-h`} className={s.h4}>
        Decisão do curador
      </h4>
      {editing ? (
        <div className={s.form}>
          <label htmlFor={`${base}-title`} className={s.label}>
            Título
          </label>
          <input id={`${base}-title`} value={title} onChange={(e) => setTitle(e.target.value)} className={s.input} />
          <label htmlFor={`${base}-mode`} className={s.label}>
            Modo
          </label>
          <select
            id={`${base}-mode`}
            value={mode}
            onChange={(e) => setMode(e.target.value as BlockMode)}
            className={s.input}
          >
            {MODES.map((m) => (
              <option key={m} value={m}>
                {m === "fixed" ? "Fixo" : m === "parametric" ? "Paramétrico" : "Adaptativo"}
              </option>
            ))}
          </select>
          <label htmlFor={`${base}-rule`} className={s.label}>
            Regra de ativação
          </label>
          <textarea
            id={`${base}-rule`}
            value={rule}
            rows={2}
            onChange={(e) => setRule(e.target.value)}
            className={`${s.input} ${s.mono}`}
          />
        </div>
      ) : null}
      <label htmlFor={`${base}-note`} className={s.label}>
        {editing ? "Porquê (obrigatório, fica registado)" : "Nota (opcional, fica registada)"}
      </label>
      <textarea
        id={`${base}-note`}
        rows={2}
        value={note}
        onChange={(e) => setNote(e.target.value)}
        className={s.input}
      />
      {action.error ? <ErrorNote>{action.error.message}</ErrorNote> : null}
      <Buttons>
        {editing ? (
          <>
            <Button variant="primary" disabled={action.isPending || note.trim().length < 3} onClick={save}>
              Guardar alterações
            </Button>
            <Button onClick={() => setEditing(false)}>Cancelar</Button>
          </>
        ) : (
          <>
            <Button
              variant="primary"
              disabled={action.isPending || b.status === "approved"}
              onClick={() => decide("approved")}
            >
              Aprovar bloco
            </Button>
            <Button onClick={() => setEditing(true)}>Editar</Button>
            <Button disabled={action.isPending || b.status === "rejected"} onClick={() => decide("rejected")}>
              Rejeitar bloco
            </Button>
          </>
        )}
      </Buttons>
      {editing ? <p className={s.muted}>Um bloco aprovado que é editado volta a «proposto».</p> : null}
    </section>
  );
}

function History({ id }: { id: string }) {
  const { data: events = [] } = useBlockHistory(id);
  return (
    <section aria-label="Histórico do bloco">
      <h4 className={s.h4}>Histórico</h4>
      {events.length === 0 ? (
        <p className={s.muted}>Ainda sem decisões: proposto pelo agente a partir de R1 e R2.</p>
      ) : (
        <Timeline
          items={events.map((e) => ({
            id: e.id,
            time: formatDateTime(e.at),
            who: e.actor_name,
            what: e.description,
            human: e.actor_type === "user",
          }))}
        />
      )}
    </section>
  );
}
