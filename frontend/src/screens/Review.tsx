/**
 * Screen H (SPEC 10.H, Phase 6): review and export.
 *
 * Per piece (MDJ, CTE): what changed (a revision against now, or the agent's proposal against the
 * técnico's edit), the técnico responsável, the approval card with the real conditions (each with
 * why it fails and a link to resolve it), the header date (P8: only when the técnico writes it),
 * approving and reopening, and the history of revisions. Then the exports of the set: a draft is
 * always possible; the official set only with every piece approved. The audit log closes the page.
 */

import { useId, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { useActiveProject } from "../app/activeProject";
import {
  useApproval,
  useApprovalActions,
  useAudit,
  useCreateExport,
  useDocument,
  useDocumentDiff,
  useDocuments,
  useExports,
  useMe,
  useProject,
  useVersions,
} from "../api/queries";
import type { Approval, ProjectDocument, ProjectExport, SectionContent } from "../api/types";
import { DiffView } from "../components/DiffView";
import { DownloadButton } from "../components/DownloadButton";
import { Button, ButtonLink, Buttons, Card, EmptyState, ErrorNote, Pill, Timeline, type Tone } from "../components/ui";
import { fileSize, formatDateTime } from "../lib/format";
import { nodeText } from "../lib/content";
import { Loading, NoProject } from "./common";
import c from "./common.module.css";
import s from "./Review.module.css";
import { Screen } from "./Screen";

const STATUS: Record<Approval["status"], { label: string; tone: Tone }> = {
  draft: { label: "Rascunho", tone: "mute" },
  in_review: { label: "Em revisão", tone: "info" },
  approved: { label: "Aprovada", tone: "ok" },
};
const EXPORT_STATUS: Record<ProjectExport["status"], { label: string; tone: Tone }> = {
  queued: { label: "Em fila", tone: "info" },
  running: { label: "A exportar…", tone: "info" },
  done: { label: "Pronta", tone: "ok" },
  failed: { label: "Falhou", tone: "crit" },
};

function useRoles() {
  const { data: me } = useMe();
  const roles = new Set(me?.roles.map((r) => r.id) ?? []);
  return {
    tecnico: roles.has("tecnico"),
    writer: roles.has("redator") || roles.has("tecnico"),
    assigner: roles.has("tecnico") || roles.has("admin"),
  };
}

/** The pieces of the set: the latest MDJ and CTE assembled by the tool. */
function piecesOf(documents: ProjectDocument[]): ProjectDocument[] {
  const found = new Map<string, ProjectDocument>();
  for (const d of [...documents].sort((a, b) => b.created_at.localeCompare(a.created_at))) {
    if (d.origin === "assembled" && !found.has(d.type)) found.set(d.type, d);
  }
  return (["MDJ", "CTE"] as const).flatMap((t) => (found.has(t) ? [found.get(t)!] : []));
}

export function ReviewScreen() {
  const projectId = useActiveProject();
  const { data: project } = useProject(projectId);
  const { data: documents = [], isPending } = useDocuments(projectId);
  const [params, setParams] = useSearchParams();
  const pieces = piecesOf(documents);
  const existing = documents.some((d) => d.origin === "existing");
  const chosen = pieces.find((d) => d.type === params.get("doc")) ?? pieces[0];

  return (
    <Screen
      crumb={project ? `${project.code} · Revisão` : "Revisão"}
      title="Revisão e exportação"
      description="O técnico vê o que mudou, aprova e exporta o conjunto do projeto no modelo TUU. Fica tudo registado."
    >
      {!projectId ? (
        <NoProject screen="a revisão" />
      ) : isPending ? (
        <Loading />
      ) : (
        <>
          {pieces.length === 0 ? (
            <EmptyState
              title="Ainda não há peças para rever"
              action={
                <ButtonLink to={`/projetos/${projectId}/documentos`} variant="primary">
                  Abrir o editor
                </ButtonLink>
              }
              next="Aqui vai aparecer o que mudou em cada peça, o cartão de aprovação com as condições e a exportação do conjunto (MDJ, CTE, ficha eletrotécnica, identificação e termo)."
            >
              Monte o MDJ e o CTE no editor a partir da ficha-base confirmada.
              {existing
                ? " As peças existentes, carregadas para auditoria, só se validam: não se aprovam nem exportam."
                : ""}
            </EmptyState>
          ) : (
            <>
              <div className={s.tabs} role="group" aria-label="Peça">
                {pieces.map((d) => (
                  <button
                    key={d.id}
                    type="button"
                    aria-pressed={d.id === chosen?.id}
                    onClick={() => setParams({ doc: d.type }, { replace: true })}
                  >
                    {d.type === "MDJ" ? "Memória descritiva (MDJ)" : "Condições técnicas (CTE)"}
                  </button>
                ))}
              </div>
              {chosen ? <PieceReview key={chosen.id} document={chosen} projectId={projectId} /> : null}
              <Exports projectId={projectId} pieces={pieces} />
            </>
          )}
          <AuditCard projectId={projectId} />
        </>
      )}
    </Screen>
  );
}

function PieceReview({ document, projectId }: { document: ProjectDocument; projectId: string }) {
  const { data: approval, error } = useApproval(document.id);
  if (error) return <ErrorNote>Não foi possível carregar a aprovação: {error.message}</ErrorNote>;
  if (!approval) return <Loading />;
  return (
    <div className={s.layout}>
      <div className={s.main}>
        <DiffCard document={document} approval={approval} />
      </div>
      <aside className={s.side} aria-label={`Aprovação do ${approval.type}`}>
        <ApprovalCard approval={approval} projectId={projectId} />
        <ResponsibleCard approval={approval} projectId={projectId} />
        <RevisionsCard approval={approval} />
      </aside>
    </div>
  );
}

// ---------------------------------------------------------------- diff

function contentText(content: SectionContent | undefined): string {
  return (content?.content ?? [])
    .map((n) => (n.type === "pending" ? "[texto adaptativo por gerar]" : nodeText(n)))
    .filter((t) => t.trim())
    .join("\n");
}

function DiffCard({ document, approval }: { document: ProjectDocument; approval: Approval }) {
  const last = approval.revisions.at(-1);
  const [mode, setMode] = useState<string>(last ? `rev:${last.number}` : "proposal");
  const id = useId();
  return (
    <Card title="Diferenças">
      <label htmlFor={`${id}-mode`} className={s.label}>
        Comparar
      </label>
      <select id={`${id}-mode`} value={mode} onChange={(e) => setMode(e.target.value)} className={s.input}>
        {approval.revisions.map((r) => (
          <option key={r.number} value={`rev:${r.number}`}>
            rev. {r.label} ({r.file_version}) → atual
          </option>
        ))}
        <option value="proposal">Proposta do agente → edição do técnico</option>
      </select>
      {mode.startsWith("rev:") ? (
        <RevisionDiff documentId={document.id} base={Number(mode.slice(4))} />
      ) : (
        <ProposalDiff documentId={document.id} />
      )}
    </Card>
  );
}

function RevisionDiff({ documentId, base }: { documentId: string; base: number }) {
  const { data, error } = useDocumentDiff(documentId, base, null);
  const [chosen, setChosen] = useState<string | null>(null);
  if (error) return <ErrorNote>{error.message}</ErrorNote>;
  if (!data) return <Loading />;
  const changed = data.sections.filter((x) => x.changed);
  if (!changed.length) return <p className={s.muted}>Sem alterações desde a rev. {data.from_label}.</p>;
  const section = changed.find((x) => x.section_id === chosen) ?? changed[0]!;
  return (
    <>
      <nav aria-label="Secções alteradas" className={s.changed}>
        <p className={s.muted}>
          {changed.length} {changed.length === 1 ? "secção alterada" : "secções alteradas"} desde a rev.{" "}
          {data.from_label}:
        </p>
        <ul>
          {changed.map((x) => (
            <li key={x.section_id}>
              <button
                type="button"
                aria-current={x.section_id === section.section_id}
                onClick={() => setChosen(x.section_id)}
              >
                {x.order}. {x.title}
                {x.active_before !== null && x.active_before !== x.active_after
                  ? x.active_after
                    ? " (ativada)"
                    : " (desativada)"
                  : ""}
              </button>
            </li>
          ))}
        </ul>
      </nav>
      <h3 className={s.h4}>
        {section.order}. {section.title}
      </h3>
      <DiffView
        before={section.before}
        after={section.after}
        beforeLabel={`rev. ${data.from_label}`}
        afterLabel="atual"
        label={`Diferenças em «${section.title}»`}
      />
    </>
  );
}

/** The last text of the agent in a section against the first edit of the técnico after it. */
function ProposalDiff({ documentId }: { documentId: string }) {
  const { data: doc } = useDocument(documentId);
  const sections = (doc?.sections ?? []).filter((x) => x.active && x.has_adaptive);
  const [chosen, setChosen] = useState<string>("");
  const id = useId();
  const sectionId = chosen || sections[0]?.id;
  const { data: versions = [] } = useVersions(sectionId);
  const agent = [...versions].reverse().find((v) => v.author_type === "agent");
  const edit = agent
    ? versions.filter((v) => v.author_type === "user" && v.number > agent.number).sort((a, b) => a.number - b.number)[0]
    : undefined;
  if (!sections.length) return <p className={s.muted}>Esta peça não tem secções com texto do agente.</p>;
  return (
    <>
      <label htmlFor={`${id}-section`} className={s.label}>
        Secção
      </label>
      <select id={`${id}-section`} value={sectionId} onChange={(e) => setChosen(e.target.value)} className={s.input}>
        {sections.map((x) => (
          <option key={x.id} value={x.id}>
            {x.order}. {x.title}
          </option>
        ))}
      </select>
      {agent && edit ? (
        <DiffView
          before={contentText(agent.content)}
          after={contentText(edit.content)}
          beforeLabel={`proposta do agente (versão ${agent.number})`}
          afterLabel={`edição do técnico (versão ${edit.number})`}
          label="Diferenças entre a proposta do agente e a edição do técnico"
        />
      ) : (
        <p className={s.muted}>
          {agent
            ? "O técnico ainda não editou o texto do agente nesta secção."
            : "O agente ainda não escreveu nesta secção."}
        </p>
      )}
    </>
  );
}

// ---------------------------------------------------------------- approval

function ApprovalCard({ approval, projectId }: { approval: Approval; projectId: string }) {
  const roles = useRoles();
  const actions = useApprovalActions(approval.document_id, projectId);
  const [reason, setReason] = useState("");
  const [date, setDate] = useState(approval.header_date ?? "");
  const id = useId();
  const status = STATUS[approval.status];
  const approved = approval.status === "approved";
  return (
    <Card
      title={
        <>
          Aprovação · {approval.type} rev. {approval.revision_label} <Pill tone={status.tone}>{status.label}</Pill>
        </>
      }
    >
      <ul className={s.conditions} aria-label="Condições para aprovar">
        {approval.conditions.map((cond) => (
          <li key={cond.code} className={cond.ok ? s.ok : s.missing}>
            <span className="visually-hidden">{cond.ok ? "Cumprido: " : "Em falta: "}</span>
            <span>
              {cond.text}
              {cond.reason ? <span className={s.reason}> · {cond.reason}</span> : null}
              {!cond.ok && cond.link ? (
                <>
                  {" "}
                  <Link to={cond.link} className={s.fix}>
                    Resolver
                  </Link>
                </>
              ) : null}
              {!cond.ok && cond.items.length ? (
                <details className={s.items}>
                  <summary>Ver {cond.items.length === 1 ? "a secção" : `as ${cond.items.length} secções`}</summary>
                  <ul>
                    {cond.items.map((i) => (
                      <li key={i.section_id}>
                        {i.order}. {i.title} — {i.reason}
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
            </span>
          </li>
        ))}
      </ul>
      {approved ? (
        <p className={s.muted}>
          Aprovada por {approval.approved_by_name ?? "—"}
          {approval.approved_at ? ` em ${formatDateTime(approval.approved_at)}` : ""}.
        </p>
      ) : null}
      {roles.tecnico && !approved ? (
        <form
          className={s.form}
          onSubmit={(e) => {
            e.preventDefault();
            actions.header.mutate(date.trim() || null);
          }}
        >
          <label htmlFor={`${id}-date`} className={s.label}>
            Data do cabeçalho (opcional: só o técnico a escreve; vazia por omissão)
          </label>
          <span className={s.inline}>
            <input
              id={`${id}-date`}
              value={date}
              placeholder="ex.: OUTUBRO/2026"
              onChange={(e) => setDate(e.target.value)}
              className={s.input}
            />
            <Button type="submit" small disabled={actions.header.isPending}>
              Guardar data
            </Button>
          </span>
          {actions.header.error ? <ErrorNote>{actions.header.error.message}</ErrorNote> : null}
        </form>
      ) : null}
      {!approved ? (
        <>
          <Buttons>
            <Button
              variant="primary"
              disabled={!approval.can_approve || actions.approve.isPending}
              onClick={() => actions.approve.mutate()}
            >
              Aprovar {approval.type}
            </Button>
          </Buttons>
          {approval.why_not ? <p className={s.muted}>{approval.why_not}</p> : null}
          {actions.approve.error ? <ErrorNote>{actions.approve.error.message}</ErrorNote> : null}
        </>
      ) : roles.tecnico ? (
        <form
          className={s.form}
          onSubmit={(e) => {
            e.preventDefault();
            actions.reopen.mutate(reason.trim(), { onSuccess: () => setReason("") });
          }}
        >
          <label htmlFor={`${id}-reopen`} className={s.label}>
            Porque reabre (fica registado; cria a revisão seguinte)
          </label>
          <textarea
            id={`${id}-reopen`}
            rows={2}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className={s.input}
          />
          <Buttons>
            <Button type="submit" disabled={reason.trim().length < 10 || actions.reopen.isPending}>
              Reabrir {approval.type}
            </Button>
          </Buttons>
          {actions.reopen.error ? <ErrorNote>{actions.reopen.error.message}</ErrorNote> : null}
        </form>
      ) : null}
    </Card>
  );
}

function ResponsibleCard({ approval, projectId }: { approval: Approval; projectId: string }) {
  const roles = useRoles();
  const actions = useApprovalActions(approval.document_id, projectId);
  const [who, setWho] = useState(approval.responsible_id ?? "");
  const [reason, setReason] = useState("");
  const id = useId();
  return (
    <Card title="Técnico responsável">
      <p className={s.who}>
        <span className={s.avatar} aria-hidden="true">
          {(approval.responsible_name ?? "?").slice(0, 1)}
        </span>
        <span>
          <b>{approval.responsible_name ?? "Por atribuir"}</b>
          <span className={s.muted}> · só ele aprova esta peça</span>
        </span>
      </p>
      {roles.assigner && approval.status !== "approved" ? (
        <details>
          <summary>Atribuir outro técnico</summary>
          <form
            className={s.form}
            onSubmit={(e) => {
              e.preventDefault();
              actions.assign.mutate({ user_id: who, reason: reason.trim() }, { onSuccess: () => setReason("") });
            }}
          >
            <label htmlFor={`${id}-who`} className={s.label}>
              Técnico
            </label>
            <select id={`${id}-who`} value={who} onChange={(e) => setWho(e.target.value)} className={s.input}>
              {approval.tecnicos.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
            <label htmlFor={`${id}-why`} className={s.label}>
              Porquê (fica registado)
            </label>
            <textarea
              id={`${id}-why`}
              rows={2}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className={s.input}
            />
            <Buttons>
              <Button type="submit" small disabled={!who || reason.trim().length < 10 || actions.assign.isPending}>
                Atribuir
              </Button>
            </Buttons>
            {actions.assign.error ? <ErrorNote>{actions.assign.error.message}</ErrorNote> : null}
          </form>
        </details>
      ) : null}
    </Card>
  );
}

function RevisionsCard({ approval }: { approval: Approval }) {
  return (
    <Card title="Histórico de revisões">
      {approval.revisions.length === 0 ? (
        <p className={s.muted}>
          Ainda sem revisões aprovadas. A 1.ª aprovação é a rev. A (ficheiro V0, cabeçalho R00).
        </p>
      ) : (
        <Timeline
          items={[...approval.revisions].reverse().map((r) => ({
            id: String(r.number),
            time: formatDateTime(r.approved_at),
            who: `rev. ${r.label} · ${r.file_version} · ${r.header_revision}`,
            what:
              `aprovada por ${r.approved_by_name ?? "—"}` +
              (r.reopened_at ? ` · reaberta por ${r.reopened_by_name ?? "—"}: ${r.reopen_reason ?? ""}` : ""),
            human: true,
          }))}
        />
      )}
    </Card>
  );
}

// ---------------------------------------------------------------- export

function Exports({ projectId, pieces }: { projectId: string; pieces: ProjectDocument[] }) {
  const roles = useRoles();
  const { data: exports = [] } = useExports(projectId);
  const create = useCreateExport(projectId);
  const [pdf, setPdf] = useState(false);
  const id = useId();
  const allApproved = pieces.length === 2 && pieces.every((d) => d.status === "approved");
  const officialWhy =
    pieces.length < 2
      ? "O conjunto oficial precisa do MDJ e do CTE."
      : !allApproved
        ? "Só com o MDJ e o CTE aprovados pelo técnico responsável."
        : !roles.tecnico
          ? "Só um técnico exporta o conjunto oficial."
          : null;
  return (
    <Card title="Exportar o conjunto">
      <p className={s.muted}>
        MDJ e CTE (.docx), ficha eletrotécnica (.xlsm), identificação e termo (.docx), com os nomes da TUU e um
        manifesto. Os formulários saem sem data nem assinatura: o técnico data e assina. O rascunho leva a marca
        «RASCUNHO — não aprovado» em todas as páginas e no nome dos ficheiros.
      </p>
      {roles.writer ? (
        <>
          <label className={s.check} htmlFor={`${id}-pdf`}>
            <input id={`${id}-pdf`} type="checkbox" checked={pdf} onChange={(e) => setPdf(e.target.checked)} /> Incluir
            o PDF de cada peça
          </label>
          <Buttons>
            <Button disabled={create.isPending} onClick={() => create.mutate({ kind: "draft", pdf })}>
              Exportar rascunho
            </Button>
            <Button
              variant="primary"
              disabled={Boolean(officialWhy) || create.isPending}
              onClick={() => create.mutate({ kind: "official", pdf })}
            >
              Exportar conjunto oficial
            </Button>
          </Buttons>
          {officialWhy ? <p className={s.muted}>{officialWhy}</p> : null}
          {create.error ? <ErrorNote>{create.error.message}</ErrorNote> : null}
        </>
      ) : (
        <p className={s.muted}>Só um redator ou um técnico pede exportações.</p>
      )}
      <h3 className={s.h4}>Exportações anteriores</h3>
      {exports.length === 0 ? (
        <p className={s.muted}>Ainda não há exportações.</p>
      ) : (
        <ul className={s.exports} aria-label="Exportações anteriores">
          {exports.map((e) => {
            const st = EXPORT_STATUS[e.status];
            return (
              <li key={e.id}>
                <span className={s.exportHead}>
                  <Pill tone={e.kind === "official" ? "ok" : "warn"}>
                    {e.kind === "official" ? `Oficial ${e.version}` : "Rascunho"}
                  </Pill>
                  <Pill tone={st.tone}>{st.label}</Pill>
                  <span className={s.muted}>
                    {formatDateTime(e.created_at)} · {e.created_by_name ?? "—"}
                    {e.zip_size ? ` · ${e.files.length} ficheiros, ${fileSize(e.zip_size)}` : ""}
                  </span>
                </span>
                {e.status === "done" && e.zip_name ? (
                  <DownloadButton path={`/exports/${e.id}/bundle.zip`} filename={e.zip_name}>
                    {`Descarregar ${e.zip_name}`}
                  </DownloadButton>
                ) : null}
                {e.status === "failed" && e.message ? <p className={s.muted}>{e.message}</p> : null}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

function AuditCard({ projectId }: { projectId: string }) {
  const { data: audit, isLoading } = useAudit(projectId);
  return (
    <Card title="Registo de auditoria">
      {isLoading ? <Loading /> : null}
      {audit && audit.length === 0 ? <p className={c.loading}>Ainda não há registos.</p> : null}
      {audit && audit.length > 0 ? (
        <Timeline
          items={audit.map((e) => ({
            id: e.id,
            time: formatDateTime(e.at),
            who: e.actor_name,
            what: e.description,
            human: e.actor_type === "user",
          }))}
        />
      ) : null}
    </Card>
  );
}
