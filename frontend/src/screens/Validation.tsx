/** Screen E · Validação (SPEC 9, 10.E): issues with evidence and actions, and the coherence matrix. */

import { useId, useMemo, useState } from "react";

import { useActiveProject } from "../app/activeProject";
import { useProjectEvents } from "../api/events";
import {
  useDocuments,
  useFicha,
  useIgnoreIssue,
  useMe,
  useProject,
  useRefreshValidation,
  useReopenIssue,
  useRequestReview,
  useRunValidation,
  useValidation,
} from "../api/queries";
import type {
  CoherenceMatrix,
  EvidenceValue,
  PieceInfo,
  Severity,
  Validation,
  ValidationIssue,
} from "../api/types";
import { Button, ButtonLink, Buttons, Card, Chip, DataTable, EmptyState, ErrorNote, Pill, type Tone } from "../components/ui";
import { formatDateTime } from "../lib/format";
import { Checklist, Loading, NoProject } from "./common";
import { Screen } from "./Screen";
import s from "./Validation.module.css";

const SEVERITY: Record<Severity, { tone: Tone; label: string; plural: string }> = {
  critical: { tone: "crit", label: "Crítico", plural: "críticos" },
  warning: { tone: "warn", label: "Aviso", plural: "avisos" },
  info: { tone: "info", label: "Informação", plural: "informações" },
};
const STATUS_FILTERS = { open: "Abertos", ignored: "Ignorados", all: "Todos" } as const;
const MIN_REASON = 10;

function useCanWrite(): boolean {
  const { data: me } = useMe();
  return me?.roles.some((r) => r.id === "redator" || r.id === "tecnico") ?? false;
}

export function ValidationScreen() {
  const projectId = useActiveProject();
  const { data: project } = useProject(projectId);
  return (
    <Screen
      crumb={project ? `${project.code} · Validação` : "Validação"}
      title="Validação"
      description="Verificação cruzada de todas as peças do projeto, com a ficha-base como referência. A validação sinaliza; nada é corrigido sem uma ação sua."
    >
      {projectId ? <ProjectValidation projectId={projectId} /> : <NoProject screen="a validação" />}
    </Screen>
  );
}

function ProjectValidation({ projectId }: { projectId: string }) {
  const { data, isPending, error } = useValidation(projectId);
  const { data: ficha } = useFicha(projectId);
  const { data: documents = [] } = useDocuments(projectId);
  const refresh = useRefreshValidation(projectId);
  const run = useRunValidation(projectId);
  const canWrite = useCanWrite();
  const [step, setStep] = useState<string | null>(null);

  useProjectEvents(projectId, (event) => {
    if (event.type !== "validation") return;
    setStep(event.step);
    if (event.status === "done" || event.status === "failed") refresh();
  });

  if (isPending) return <Loading />;
  if (error) return <ErrorNote>Não foi possível carregar a validação: {error.message}</ErrorNote>;
  const confirmed = ficha?.revisions.some((r) => r.status === "confirmed") ?? false;
  const hasPieces = documents.length > 0;
  const busy = data.current && ["queued", "running"].includes(data.current.status);
  const validate = canWrite ? (
    <Buttons>
      <Button variant="primary" disabled={Boolean(busy) || run.isPending} onClick={() => run.mutate()}>
        {data.run ? "↻ Validar novamente" : "Validar o projeto"}
      </Button>
    </Buttons>
  ) : null;

  if (!data.ready || !hasPieces) {
    return (
      <EmptyState
        title="A validação fica disponível quando houver ficha-base confirmada e peças do projeto"
        action={
          <Checklist
            items={[
              { done: confirmed, text: "Ficha-base confirmada por um técnico responsável" },
              { done: hasPieces, text: "MDJ e CTE montados, ou carregados como peças existentes (auditoria)" },
            ]}
          />
        }
        next="Correm as regras da secção 9 da SPEC (referências, coerência, tipologia, peças desenhadas, cálculo, contratação, conteúdo e qualidade do texto) e a matriz de coerência do projeto."
      />
    );
  }
  return (
    <div className={s.stack}>
      {busy ? (
        <p className={s.progress} role="status">
          A validar… {step ?? "na fila"}
        </p>
      ) : null}
      {run.error ? <ErrorNote>{run.error.message}</ErrorNote> : null}
      {data.current?.status === "failed" ? (
        <ErrorNote>A última validação não terminou: {data.current.message}</ErrorNote>
      ) : null}
      {data.run ? (
        <>
          <Summary data={data} action={validate} />
          <ReviewGate projectId={projectId} data={data} canWrite={canWrite} />
          <Issues projectId={projectId} data={data} canWrite={canWrite} />
          <Matrix matrix={data.matrix} />
        </>
      ) : (
        <EmptyState
          title="O projeto ainda não foi validado"
          action={validate}
          next="A validação lê cada peça (MDJ, CTE, ficha eletrotécnica, Tabela de Cálculo, MQT/LPU, desenhos, identificação e termo), compara-a com a ficha-base e mostra os alertas com a evidência e a leitura provável."
        >
          {canWrite ? null : "Só um redator ou um técnico responsável pode pedir a validação."}
        </EmptyState>
      )}
    </div>
  );
}

function count(data: Validation, severity: Severity, status: "open" | "ignored" = "open"): number {
  return data.issues.filter((i) => i.severity === severity && i.status === status).length;
}

function Summary({ data, action }: { data: Validation; action: React.ReactNode }) {
  const run = data.run!;
  const ignored = data.issues.filter((i) => i.status === "ignored").length;
  const pieces = run.pieces.map((p) => p.name).join(", ");
  return (
    <Card title="Resumo">
      <div className={s.summary}>
        <div>
          <div className={s.counts} aria-label="Alertas abertos por severidade">
            {(["critical", "warning", "info"] as const).map((sev) => {
              const n = count(data, sev);
              return (
                <Pill key={sev} tone={n || sev !== "critical" ? SEVERITY[sev].tone : "ok"}>
                  {`${n} ${n === 1 ? SEVERITY[sev].label.toLowerCase() : SEVERITY[sev].plural}`}
                </Pill>
              );
            })}
            {ignored ? <Pill tone="mute">{`${ignored} ignorado${ignored > 1 ? "s" : ""}`}</Pill> : null}
          </div>
          <p className={s.muted}>
            Os críticos bloqueiam o envio para revisão. Qualquer alerta pode ser ignorado com justificação, que fica
            na auditoria.
          </p>
          <p className={s.muted}>
            Validado {run.finished_at ? formatDateTime(run.finished_at) : ""}
            {run.trigger === "changed" ? " (revalidação depois de uma edição)" : ""} · {run.pieces.length} peças:{" "}
            {pieces}
          </p>
        </div>
        {action}
      </div>
    </Card>
  );
}

function ReviewGate({ projectId, data, canWrite }: { projectId: string; data: Validation; canWrite: boolean }) {
  const send = useRequestReview(projectId);
  const critical = count(data, "critical");
  return (
    <Card title="Enviar para revisão">
      {critical ? (
        <p className={s.blocked}>
          {`${critical} alerta${critical > 1 ? "s" : ""} crítico${critical > 1 ? "s" : ""} abert${critical > 1 ? "os" : "o"}: as peças não podem ser enviadas para revisão.`}
        </p>
      ) : (
        <p className={s.muted}>Sem alertas críticos abertos: as peças podem seguir para revisão (ecrã H).</p>
      )}
      {canWrite ? (
        <Buttons>
          <Button disabled={critical > 0 || send.isPending} onClick={() => send.mutate()}>
            Enviar as peças para revisão
          </Button>
        </Buttons>
      ) : null}
      {send.error ? <ErrorNote>{send.error.message}</ErrorNote> : null}
      {send.data ? <p role="status">{`${send.data.sent} peça(s) enviada(s) para revisão.`}</p> : null}
    </Card>
  );
}

function Issues({ projectId, data, canWrite }: { projectId: string; data: Validation; canWrite: boolean }) {
  const [severities, setSeverities] = useState<Severity[]>(["critical", "warning", "info"]);
  const [status, setStatus] = useState<keyof typeof STATUS_FILTERS>("open");
  const [rule, setRule] = useState("");
  const [piece, setPiece] = useState("");
  const ids = { status: useId(), rule: useId(), piece: useId() };
  const pieces = data.run?.pieces ?? [];
  const rules = useMemo(() => [...new Set(data.issues.map((i) => i.rule_id))].sort(), [data.issues]);
  const shown = data.issues.filter(
    (i) =>
      severities.includes(i.severity) &&
      (status === "all" ? i.status !== "fixed" : i.status === status) &&
      (!rule || i.rule_id === rule) &&
      (!piece || i.location.piece === piece),
  );
  const toggle = (sev: Severity) =>
    setSeverities((now) => (now.includes(sev) ? now.filter((x) => x !== sev) : [...now, sev]));

  return (
    <section className={s.stack} aria-labelledby={`${ids.status}-title`}>
      <h2 id={`${ids.status}-title`} className={s.h2}>
        Alertas
      </h2>
      <div className={s.filters}>
        <div role="group" aria-label="Severidade" className={s.toggles}>
          {(["critical", "warning", "info"] as const).map((sev) => (
            <button key={sev} type="button" aria-pressed={severities.includes(sev)} onClick={() => toggle(sev)}>
              {SEVERITY[sev].label}
            </button>
          ))}
        </div>
        <label htmlFor={ids.status}>
          Estado
          <select id={ids.status} value={status} onChange={(e) => setStatus(e.target.value as typeof status)}>
            {Object.entries(STATUS_FILTERS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor={ids.rule}>
          Regra
          <select id={ids.rule} value={rule} onChange={(e) => setRule(e.target.value)}>
            <option value="">Todas</option>
            {rules.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor={ids.piece}>
          Peça
          <select id={ids.piece} value={piece} onChange={(e) => setPiece(e.target.value)}>
            <option value="">Todas</option>
            {pieces.map((p) => (
              <option key={p.ref} value={p.ref}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      {shown.length === 0 ? (
        <p className={s.muted}>Nenhum alerta com estes filtros.</p>
      ) : (
        <ul className={s.list} aria-label="Alertas da validação">
          {shown.map((issue) => (
            <li key={issue.id}>
              <IssueCard issue={issue} projectId={projectId} pieces={pieces} canWrite={canWrite} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function editorLink(projectId: string, issue: ValidationIssue, pieces: PieceInfo[]): string | null {
  const piece = pieces.find((p) => p.ref === issue.location.piece);
  if (!piece || !["MDJ", "CTE"].includes(piece.kind)) return null;
  const params = new URLSearchParams({ doc: piece.kind });
  if (piece.origin === "existing") params.set("origem", "existente");
  if (issue.location.section_id) params.set("seccao", String(issue.location.section_id));
  return `/projetos/${projectId}/documentos?${params.toString()}`;
}

function IssueCard({
  issue,
  projectId,
  pieces,
  canWrite,
}: {
  issue: ValidationIssue;
  projectId: string;
  pieces: PieceInfo[];
  canWrite: boolean;
}) {
  const sev = SEVERITY[issue.severity];
  const editor = issue.actions.includes("open_editor") ? editorLink(projectId, issue, pieces) : null;
  const where = [issue.rule_id, issue.rule_title, issue.location.piece_name].filter(Boolean).join(" · ");
  return (
    <details className={`${s.issue} ${s[issue.severity]} ${issue.status === "ignored" ? s.ignored : ""}`}>
      <summary>
        <span className={s.sev} aria-hidden="true" />
        <span className={s.head}>
          <span className={s.title}>{issue.message}</span>
          <span className={s.where}>{where}</span>
        </span>
        <span className={s.badges}>
          {issue.new && issue.status === "open" ? <Chip>novo</Chip> : null}
          {issue.status === "ignored" ? <Pill tone="mute">Ignorado</Pill> : <Pill tone={sev.tone}>{sev.label}</Pill>}
        </span>
      </summary>
      <div className={s.body}>
        <Evidence issue={issue} />
        {issue.likely_reading ? (
          <p>
            <b>Leitura provável:</b> {issue.likely_reading}
          </p>
        ) : null}
        {issue.suggested_fix ? <p className={s.muted}>{issue.suggested_fix}</p> : null}
        {issue.status === "ignored" ? (
          <Ignored issue={issue} projectId={projectId} canWrite={canWrite} />
        ) : (
          <div className={s.actions}>
            <Buttons>
              {editor ? <ButtonLink to={editor}>Abrir no editor</ButtonLink> : null}
              {issue.actions.includes("open_ficha") || issue.actions.includes("confirm_sheet") ? (
                <ButtonLink to={`/projetos/${projectId}/ficha`}>Abrir na ficha</ButtonLink>
              ) : null}
              {issue.actions.includes("ask_curator") ? (
                <ButtonLink to="/conhecimento">Pedir ao curador</ButtonLink>
              ) : null}
            </Buttons>
            {canWrite ? <IgnoreForm issue={issue} projectId={projectId} /> : null}
          </div>
        )}
      </div>
    </details>
  );
}

function Evidence({ issue }: { issue: ValidationIssue }) {
  const e = issue.evidence;
  const values = Array.isArray(e.values) ? (e.values as EvidenceValue[]) : [];
  const reference = e.reference as { label?: string; value?: string } | undefined;
  return (
    <div className={s.evidence}>
      {typeof e.excerpt === "string" ? <blockquote className={s.quote}>{e.excerpt}</blockquote> : null}
      {values.length ? (
        <DataTable caption="Evidência: valores comparados">
          <thead>
            <tr>
              <th scope="col">Peça</th>
              <th scope="col">Valor</th>
              <th scope="col">Onde</th>
            </tr>
          </thead>
          <tbody>
            {reference && typeof reference === "object" && reference.label ? (
              <tr className={s.ref}>
                <td>{reference.label}</td>
                <td>{reference.value}</td>
                <td>referência</td>
              </tr>
            ) : null}
            {values.map((v, n) => (
              <tr key={`${v.piece}-${n}`} className={v.differs ? s.differs : undefined}>
                <td>{v.piece_name}</td>
                <td>
                  {v.value === "•••" ? <span aria-label="Dado pessoal mascarado">•••</span> : v.value}
                  {v.differs ? <span className="visually-hidden"> (diverge)</span> : null}
                </td>
                <td>
                  {v.where}
                  {v.note ? <div className={s.muted}>{v.note}</div> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </DataTable>
      ) : null}
      <OtherEvidence evidence={e} />
    </div>
  );
}

const SHOWN_ELSEWHERE = new Set(["excerpt", "values", "reference", "masked", "groups", "pieces"]);
const EVIDENCE_LABELS: Record<string, string> = {
  block: "Bloco",
  rule: "Regra de ativação",
  why: "Porquê",
  circuit: "Troço",
  check: "Verificação",
  source: "Origem",
  limit_from: "Limite",
  missing_in_pdf: "Folhas em falta no PDF",
  not_in_index: "Páginas fora do índice",
  index_sheets: "Folhas no índice",
  pages: "Páginas do PDF",
  family: "Designação",
  written: "Como está escrita",
  compared_with: "Comparada com",
  equivalence: "Equivalência no dicionário",
  documents: "Documentos",
  citation: "Citação",
  document: "Documento",
  term: "Termo",
  typology: "Tipologia",
  value: "Valor",
  field: "Campo",
  element: "Elemento",
  profile_agrees_with: "O perfil do técnico coincide com",
  reason: "Motivo",
  not_comparable: "Não comparável",
  project: "Projeto do arquivo",
};

function OtherEvidence({ evidence }: { evidence: Record<string, unknown> }) {
  const rows = Object.entries(evidence).filter(
    ([k, v]) =>
      !SHOWN_ELSEWHERE.has(k) &&
      EVIDENCE_LABELS[k] &&
      v !== null &&
      v !== "" &&
      !(Array.isArray(v) && v.length === 0) &&
      (typeof v !== "object" || Array.isArray(v)),
  );
  if (!rows.length) return null;
  return (
    <dl className={s.kv}>
      {rows.map(([k, v]) => (
        <div key={k}>
          <dt>{EVIDENCE_LABELS[k]}</dt>
          <dd>{Array.isArray(v) ? v.map(String).join(", ") : String(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

function IgnoreForm({ issue, projectId }: { issue: ValidationIssue; projectId: string }) {
  const ignore = useIgnoreIssue(projectId);
  const [reason, setReason] = useState("");
  const [open, setOpen] = useState(false);
  const id = useId();
  if (!open) {
    return (
      <Button small onClick={() => setOpen(true)}>
        Ignorar com justificação
      </Button>
    );
  }
  const short = reason.trim().length < MIN_REASON;
  return (
    <div className={s.reason}>
      <label htmlFor={id}>Porque é que este alerta pode ser ignorado? (fica na auditoria)</label>
      <textarea id={id} rows={2} value={reason} onChange={(e) => setReason(e.target.value)} />
      <Buttons>
        <Button
          small
          variant="primary"
          disabled={short || ignore.isPending}
          onClick={() => ignore.mutate({ id: issue.id, reason: reason.trim() })}
        >
          Ignorar
        </Button>
        <Button small onClick={() => setOpen(false)}>
          Cancelar
        </Button>
      </Buttons>
      {short ? <p className={s.muted}>{`A justificação precisa de pelo menos ${MIN_REASON} caracteres.`}</p> : null}
      {ignore.error ? <ErrorNote>{ignore.error.message}</ErrorNote> : null}
    </div>
  );
}

function Ignored({ issue, projectId, canWrite }: { issue: ValidationIssue; projectId: string; canWrite: boolean }) {
  const reopen = useReopenIssue(projectId);
  return (
    <div className={s.ignoredNote}>
      <p>
        Ignorado{issue.resolved_at ? ` em ${formatDateTime(issue.resolved_at)}` : ""}: «{issue.ignored_reason}»
      </p>
      {canWrite ? (
        <Button small disabled={reopen.isPending} onClick={() => reopen.mutate(issue.id)}>
          Reabrir
        </Button>
      ) : null}
    </div>
  );
}

function Matrix({ matrix }: { matrix: CoherenceMatrix }) {
  const columns = matrix.columns ?? [];
  const rows = matrix.rows ?? [];
  if (!rows.length) return null;
  return (
    <section className={s.stack} aria-label="Matriz de coerência">
      <div className={s.matrixHead}>
        <h2 className={s.h2}>Matriz de coerência</h2>
        <span className={s.muted}>
          Referência: {matrix.reference} · cada peça é comparada com a ficha-base, não entre si
        </span>
      </div>
      <DataTable caption="Matriz de coerência do projeto">
        <thead>
          <tr>
            <th scope="col">Elemento</th>
            <th scope="col" className={s.refCol}>
              Ficha-base
            </th>
            {columns.map((c) => (
              <th key={c.id} scope="col">
                {c.label}
              </th>
            ))}
            <th scope="col" className={s.reading}>
              Leitura
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label}>
              <th scope="row" className={s.rowHead}>
                {r.label}
                {r.unit ? <span className={s.muted}> ({r.unit})</span> : null}
              </th>
              <td className={`${s.cell} ${s.refCol}`}>{r.reference ?? "—"}</td>
              {columns.map((c) => {
                const cell = r.cells[c.id];
                return (
                  <td
                    key={c.id}
                    className={`${s.cell} ${cell?.differs ? s.bad : ""}`}
                    title={cell ? cell.pieces.join(", ") : undefined}
                  >
                    {cell ? cell.value : "—"}
                    {cell?.differs ? <span className="visually-hidden"> (diverge)</span> : null}
                  </td>
                );
              })}
              <td>
                <Pill tone={r.state === "differs" ? (r.severity === "critical" ? "crit" : "warn") : r.state === "ok" ? "ok" : "mute"}>
                  {r.reading}
                </Pill>
              </td>
            </tr>
          ))}
        </tbody>
      </DataTable>
    </section>
  );
}
