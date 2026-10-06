/** Screen D · Editor assistido: the MDJ and the CTE assembled from the ficha-base, section by section. */

import { useId, useState } from "react";
import { useSearchParams } from "react-router";

import { ApiError, download } from "../api/client";
import { useProjectEvents } from "../api/events";
import {
  useAssemble,
  useDocument,
  useDocuments,
  useFicha,
  useForms,
  useGenerateDocument,
  useMe,
  useProject,
  useRefreshDocument,
  useSectionActions,
  useVersions,
} from "../api/queries";
import type { DocSection, ProjectDocument, SectionContent, SectionEvent } from "../api/types";
import { useActiveProject } from "../app/activeProject";
import { DiffView } from "../components/DiffView";
import { BlockModeBadge, Button, Buttons, Chip, EmptyState, ErrorNote, Pill, type Tone } from "../components/ui";
import { generatedParagraphs, hasPending } from "../lib/content";
import { Checklist, Loading, NoProject } from "./common";
import s from "./Editor.module.css";
import { Screen } from "./Screen";
import { SectionEditor } from "./SectionEditor";

const STATUS: Record<DocSection["status"], { label: string; tone: Tone }> = {
  todo: { label: "Por fazer", tone: "warn" },
  generated: { label: "Gerada, por rever", tone: "info" },
  reviewed: { label: "Revista", tone: "ok" },
  alert: { label: "Com alerta", tone: "crit" },
};

function sectionState(section: DocSection): { label: string; tone: Tone } {
  if (!section.active) return { label: "Desativada", tone: "mute" };
  if (section.status === "todo" && section.status_note?.startsWith("Falta dado"))
    return { label: "Faltam dados", tone: "warn" };
  return STATUS[section.status];
}

export function EditorScreen() {
  const projectId = useActiveProject();
  const { data: project } = useProject(projectId);
  return (
    <Screen
      crumb={project ? `${project.code} · Documentos` : "Documentos"}
      title="Editor assistido"
      description="O MDJ e o CTE são montados secção a secção a partir da ficha-base confirmada, com a origem de cada frase. O texto do agente chega como proposta: aceita-se ou rejeita-se."
    >
      {projectId ? <ProjectEditor projectId={projectId} /> : <NoProject screen="os documentos" />}
    </Screen>
  );
}

function useCanWrite(doc?: ProjectDocument): boolean {
  const { data: me } = useMe();
  if (doc?.origin === "existing") return false; // a piece made by hand is only audited here
  if (doc?.status === "approved") return false; // reopened in screen H, as the next revision
  return me?.roles.some((r) => r.id === "redator" || r.id === "tecnico") ?? false;
}

function ProjectEditor({ projectId }: { projectId: string }) {
  const { data: ficha } = useFicha(projectId);
  const { data: documents = [], isPending } = useDocuments(projectId);
  const [params, setParams] = useSearchParams();
  const canWrite = useCanWrite();
  const assemble = useAssemble(projectId);
  const confirmed = ficha?.revisions.some((r) => r.status === "confirmed") ?? false;
  const type = params.get("doc") === "CTE" ? "CTE" : "MDJ";
  const ofType = documents.filter((d) => d.type === type);
  const existing = ofType.find((d) => d.origin === "existing");
  const assembled = ofType.find((d) => d.origin === "assembled");
  // Without a choice: the assembled piece when there is one, else the existing one. Choosing
  // "montado" shows the assembled piece, or the way to assemble it when there is none yet.
  const chosen = params.get("origem");
  const origin =
    chosen === "existente" && existing
      ? "existing"
      : chosen === "montado" || assembled || !existing
        ? "assembled"
        : "existing";
  const document = origin === "existing" ? existing : assembled;

  if (isPending) return <Loading />;
  if (!confirmed) {
    return (
      <EmptyState
        title="Ainda não há documentos"
        action={
          <Checklist
            items={[
              { done: confirmed, text: "Ficha-base confirmada por um técnico responsável" },
              { done: false, text: "Montagem do MDJ e do CTE a partir da biblioteca de blocos" },
            ]}
          />
        }
        next="Aqui vai aparecer cada secção com o seu estado (por fazer, gerada, revista), o modo do bloco (fixo, paramétrico ou adaptativo) e as fontes usadas."
      >
        Os documentos só podem ser montados depois de a ficha-base estar confirmada.
      </EmptyState>
    );
  }
  return (
    <div className={s.stack}>
      <div className={s.docTabs} role="group" aria-label="Documento">
        {(["MDJ", "CTE"] as const).map((t) => (
          <button
            key={t}
            type="button"
            aria-pressed={t === type}
            onClick={() => setParams({ doc: t }, { replace: true })}
          >
            {t === "MDJ" ? "Memória descritiva (MDJ)" : "Condições técnicas (CTE)"}
          </button>
        ))}
      </div>
      {existing ? (
        <div className={s.docTabs} role="group" aria-label="Origem do documento">
          <button
            type="button"
            aria-pressed={origin === "assembled"}
            onClick={() => setParams({ doc: type, origem: "montado" }, { replace: true })}
          >
            Montado pela ferramenta
          </button>
          <button
            type="button"
            aria-pressed={origin === "existing"}
            onClick={() => setParams({ doc: type, origem: "existente" }, { replace: true })}
          >
            Existente (auditoria, só leitura)
          </button>
        </div>
      ) : null}
      {document ? (
        <DocumentEditor documentId={document.id} projectId={projectId} />
      ) : (
        <EmptyState
          title={`O ${type} ainda não foi montado`}
          action={
            canWrite ? (
              <Buttons>
                <Button variant="primary" disabled={assemble.isPending} onClick={() => assemble.mutate(type)}>
                  Montar o {type}
                </Button>
              </Buttons>
            ) : undefined
          }
          next="A montagem avalia as regras de ativação sobre a ficha-base, copia os blocos fixos com o OOXML original, preenche os paramétricos com os valores da ficha e deixa os adaptativos para o agente redigir."
        >
          {assemble.error ? <ErrorNote>{assemble.error.message}</ErrorNote> : null}
          {canWrite ? null : "Só um redator ou um técnico responsável pode montar documentos."}
        </EmptyState>
      )}
      {canWrite ? <FormsPanel projectId={projectId} /> : null}
    </div>
  );
}

function DownloadButton({ path, filename, children }: { path: string; filename: string; children: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <>
      <Button
        small
        disabled={busy}
        onClick={() => {
          setBusy(true);
          setError(null);
          download(path, filename)
            .catch((e: unknown) => setError(e instanceof Error ? e.message : "Erro ao descarregar."))
            .finally(() => setBusy(false));
        }}
      >
        {children}
      </Button>
      {error ? <ErrorNote>{error}</ErrorNote> : null}
    </>
  );
}

/** The DGEG forms, filled from the ficha-base and the technician's profile (SPEC 8.5). */
function FormsPanel({ projectId }: { projectId: string }) {
  const { data: forms = [], error } = useForms(projectId, true);
  return (
    <section className={s.forms} aria-labelledby="forms-title">
      <h3 id="forms-title" className={s.h4}>
        Formulários pré-preenchidos
      </h3>
      <p className={s.muted}>
        Preenchidos com a ficha-base confirmada e o perfil do técnico responsável. Saem sem data nem assinatura: o
        técnico data e assina.
      </p>
      {error ? <ErrorNote>{error.message}</ErrorNote> : null}
      <ul className={s.plain}>
        {forms.map((f) => (
          <li key={f.kind} className={s.formItem}>
            <DownloadButton path={`/projects/${projectId}/forms/${f.kind}`} filename={f.filename}>
              {f.title}
            </DownloadButton>
            <span className={s.muted}>Por preencher: {f.by_hand.join("; ")}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function DocumentEditor({ documentId, projectId }: { documentId: string; projectId: string }) {
  const { data: doc, isPending, error } = useDocument(documentId);
  const [params, setParams] = useSearchParams();
  const [queue, setQueue] = useState<Record<string, SectionEvent>>({});
  const refresh = useRefreshDocument(documentId, projectId);
  const generate = useGenerateDocument(documentId, projectId);
  const canWrite = useCanWrite(doc);

  useProjectEvents(projectId, (event) => {
    if (event.type !== "section" || event.document_id !== documentId) return;
    setQueue((q) => ({ ...q, [event.section_id]: event }));
    if (["generated", "failed", "paused"].includes(event.status)) refresh();
  });

  if (isPending) return <Loading />;
  if (error) return <ErrorNote>{error.message}</ErrorNote>;
  const sections = doc.sections ?? [];
  const selected = sections.find((x) => x.id === params.get("seccao")) ?? sections.find((x) => x.active);
  const select = (id: string) =>
    setParams(
      { doc: doc.type, ...(doc.origin === "existing" ? { origem: "existente" } : {}), seccao: id },
      { replace: true },
    );
  const toDraft = sections.filter((x) => x.active && hasPending(x.content)).length;

  return (
    <div className={s.layout}>
      <nav className={s.sections} aria-label={`Secções do ${doc.type}`}>
        <Summary doc={doc} />
        <ol className={s.list}>
          {sections.map((x) => {
            const state = sectionState(x);
            return (
              <li key={x.id}>
                <button
                  type="button"
                  className={`${s.item} ${x.active ? "" : s.inactive}`}
                  aria-current={x.id === selected?.id ? "true" : undefined}
                  onClick={() => select(x.id)}
                >
                  <span className={s.itemTitle}>
                    <span className={s.order}>{x.order}.</span> {x.level === 2 ? "↳ " : ""}
                    {x.title}
                  </span>
                  <span className={s.meta}>
                    <BlockModeBadge mode={x.mode} />
                    <Pill tone={state.tone}>{state.label}</Pill>
                    {x.block_approved ? null : <Chip>não aprovado</Chip>}
                    {queue[x.id] && ["queued", "generating"].includes(queue[x.id]!.status) ? (
                      <Chip>{queue[x.id]!.status === "queued" ? "em fila" : "a gerar…"}</Chip>
                    ) : null}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      </nav>
      <div className={s.main}>
        <div className={s.toolbar}>
          {canWrite && toDraft ? (
            <Button variant="primary" disabled={generate.isPending} onClick={() => generate.mutate()}>
              Gerar texto adaptativo ({toDraft} {toDraft === 1 ? "secção" : "secções"})
            </Button>
          ) : null}
          <DownloadButton path={`/documents/${doc.id}/draft.docx`} filename={`${doc.type}_RASCUNHO-nao-aprovado.docx`}>
            Rascunho .docx
          </DownloadButton>
          {generate.error ? <ErrorNote>{generate.error.message}</ErrorNote> : null}
        </div>
        {selected ? (
          <SectionPane
            key={selected.id}
            section={selected}
            doc={doc}
            projectId={projectId}
            event={queue[selected.id]}
          />
        ) : (
          <EmptyState title="Escolha uma secção">O documento não tem secções ativas.</EmptyState>
        )}
      </div>
    </div>
  );
}

function Summary({ doc }: { doc: ProjectDocument }) {
  const c = doc.counts;
  return (
    <p className={s.muted}>
      {doc.origin === "existing" ? (
        <>
          <strong>Peça existente, carregada para auditoria: só leitura.</strong> Os dados pessoais aparecem
          mascarados; a validação compara-os no servidor.{" "}
        </>
      ) : null}
      {doc.status === "approved" ? (
        <>
          <strong>Aprovada (rev. {doc.revision_label ?? "A"}): só leitura.</strong> Para alterar, reabra-a no ecrã de
          revisão (cria a revisão seguinte).{" "}
        </>
      ) : null}
      {doc.type} · ficha-base rev. {doc.ficha_revision} · {c.sections ?? 0} secções: {c.reviewed ?? 0} revistas,{" "}
      {c.generated ?? 0} por rever, {c.todo ?? 0} por fazer, {c.inactive ?? 0} desativadas · {c.not_approved ?? 0} com
      bloco não aprovado
    </p>
  );
}

function ReasonForm({
  label,
  action,
  onSubmit,
  pending,
}: {
  label: string;
  action: string;
  onSubmit: (reason: string) => void;
  pending: boolean;
}) {
  const [reason, setReason] = useState("");
  const id = useId();
  return (
    <div className={s.reason}>
      <label htmlFor={id} className={s.label}>
        {label}
      </label>
      <textarea id={id} rows={2} value={reason} onChange={(e) => setReason(e.target.value)} className={s.input} />
      <Buttons>
        <Button small disabled={pending || reason.trim().length < 3} onClick={() => onSubmit(reason.trim())}>
          {action}
        </Button>
      </Buttons>
    </div>
  );
}

function SectionPane({
  section: x,
  doc,
  projectId,
  event,
}: {
  section: DocSection;
  doc: ProjectDocument;
  projectId: string;
  event?: SectionEvent;
}) {
  const actions = useSectionActions(x, doc.id, projectId);
  const canWrite = useCanWrite(doc);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<SectionContent | null>(null);
  const [confirmValues, setConfirmValues] = useState(false);
  const titleId = useId();
  const reviewed = x.status === "reviewed";

  const save = (confirm: boolean) =>
    actions.edit.mutate(
      { content: draft ?? x.content, confirm_values: confirm },
      {
        onSuccess: () => {
          setEditing(false);
          setDraft(null);
          setConfirmValues(false);
        },
        onError: (err) => {
          if (err instanceof ApiError && err.status === 409 && err.message.startsWith("Confirme"))
            setConfirmValues(true);
        },
      },
    );
  const error = [actions.edit, actions.review, actions.unlock, actions.activation, actions.generate].find(
    (m) => m.error,
  )?.error;

  return (
    <div className={s.pane}>
      <article className={s.section} aria-labelledby={titleId}>
        <header className={s.head}>
          <h3 id={titleId} className={s.title}>
            {x.title}
          </h3>
          <div className={s.meta}>
            <BlockModeBadge mode={x.mode} />
            <Pill tone={sectionState(x).tone}>{sectionState(x).label}</Pill>
            <span className={s.muted}>versão {x.current_version}</span>
          </div>
        </header>
        {x.block_approved ? null : (
          <p className={s.warnBanner}>
            Bloco não aprovado pelo curador: pode ser usado em desenvolvimento, mas não na exportação oficial.
          </p>
        )}
        {!x.active ? (
          <div className={s.inactiveBanner}>
            <p>
              <b>Desativada pela regra de ativação.</b> {x.active_reason}
            </p>
            {canWrite ? (
              <ReasonForm
                label="Justificação para ativar (fica registada)"
                action="Ativar com justificação"
                pending={actions.activation.isPending}
                onSubmit={(reason) => actions.activation.mutate({ active: true, reason })}
              />
            ) : null}
          </div>
        ) : null}
        {x.activation_override ? (
          <p className={s.muted}>
            {x.activation_override.active ? "Ativada" : "Desativada"} à mão: «{x.activation_override.reason}».
          </p>
        ) : null}
        {x.status_note ? <p className={s.note}>{x.status_note}</p> : null}
        {x.locked && !x.unlocked ? (
          <p className={s.lockBanner}>Bloco fixo: copiado com o OOXML original e protegido.</p>
        ) : null}
        {x.unlocked ? <p className={s.muted}>Desbloqueado: «{x.unlocked.reason}».</p> : null}
        <SectionEditor
          content={x.content}
          editable={editing}
          unlocked={Boolean(x.unlocked)}
          reviewed={reviewed}
          label={`Texto de ${x.title}`}
          onChange={setDraft}
        />
        {error ? <ErrorNote>{error.message}</ErrorNote> : null}
        {confirmValues ? (
          <div className={s.confirm} role="alertdialog" aria-labelledby={`${titleId}-confirm`}>
            <p id={`${titleId}-confirm`}>
              Alterou valores que vêm da ficha-base. Confirma? A alteração fica registada e marcada para a verificação
              de coerência (COE-01).
            </p>
            <Buttons>
              <Button variant="primary" small onClick={() => save(true)}>
                Confirmar a alteração dos valores
              </Button>
              <Button small onClick={() => setConfirmValues(false)}>
                Voltar
              </Button>
            </Buttons>
          </div>
        ) : null}
        {canWrite && x.active ? (
          <Buttons>
            {editing ? (
              <>
                <Button variant="primary" disabled={actions.edit.isPending} onClick={() => save(false)}>
                  Guardar
                </Button>
                <Button
                  onClick={() => {
                    setEditing(false);
                    setDraft(null);
                    setConfirmValues(false);
                  }}
                >
                  Cancelar
                </Button>
              </>
            ) : (
              <>
                <Button onClick={() => setEditing(true)}>Editar</Button>
                <Button
                  variant="dark"
                  disabled={reviewed || actions.review.isPending || hasPending(x.content)}
                  onClick={() => actions.review.mutate()}
                >
                  ✓ Marcar como revista
                </Button>
              </>
            )}
          </Buttons>
        ) : null}
        {canWrite && x.locked && !x.unlocked && x.active ? (
          <ReasonForm
            label="Justificação para desbloquear o bloco fixo (fica registada)"
            action="Desbloquear"
            pending={actions.unlock.isPending}
            onSubmit={(reason) => actions.unlock.mutate(reason)}
          />
        ) : null}
      </article>
      <aside className={s.side} aria-label="Fontes e pedidos ao agente">
        <SidePanel section={x} doc={doc} projectId={projectId} event={event} />
      </aside>
    </div>
  );
}

function SidePanel({
  section: x,
  doc,
  projectId,
  event,
}: {
  section: DocSection;
  doc: ProjectDocument;
  projectId: string;
  event?: SectionEvent;
}) {
  const { data: versions = [] } = useVersions(x.id);
  const actions = useSectionActions(x, doc.id, projectId);
  const canWrite = useCanWrite(doc);
  const [request, setRequest] = useState("");
  const requestId = useId();
  const proposal = [...versions].reverse().find((v) => v.status === "proposed");
  const current = versions.find((v) => v.status === "current");

  return (
    <div className={s.sideStack}>
      {event && ["queued", "generating", "paused", "failed"].includes(event.status) ? (
        <p className={s.note} role="status">
          {event.status === "queued"
            ? `Em fila${event.wait_s ? `: aguarda ${Math.ceil(event.wait_s)} s pela quota` : ""}.`
            : event.status === "generating"
              ? "O agente está a redigir esta secção…"
              : event.message}
        </p>
      ) : null}
      <section>
        <h4 className={s.h4}>Fontes desta secção</h4>
        {x.citations.length ? (
          <ul className={`${s.plain} ${s.sources}`}>
            {[...new Set(x.citations.map((c) => c.target))].map((t) => (
              <li key={t}>
                <Chip>{t.startsWith("arc:") ? `Arquivo TUU · ${t.slice(4)}` : t}</Chip>
              </li>
            ))}
          </ul>
        ) : (
          <p className={s.muted}>
            {x.mode === "adaptive"
              ? "Ainda sem texto do agente."
              : "Biblioteca de blocos e ficha-base (valores sublinhados)."}
          </p>
        )}
      </section>
      {x.missing_data.length || x.missing_keys.length ? (
        <section>
          <h4 className={s.h4}>Faltam dados</h4>
          <ul className={s.plain}>
            {[...new Set([...x.missing_keys, ...x.missing_data])].map((k) => (
              <li key={k} className={s.mono}>
                {k}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {x.assumptions.length ? (
        <section>
          <h4 className={s.h4}>Suposições do agente</h4>
          <ul className={s.plain}>
            {x.assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </section>
      ) : null}
      {x.issues.length ? (
        <section>
          <h4 className={s.h4}>Alertas</h4>
          <ul className={s.plain}>
            {x.issues.map((i, n) => (
              <li key={n}>
                <b>{i.rule}</b> {i.message} {i.snippet ? <q>{i.snippet}</q> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {proposal ? (
        <section aria-label="Proposta do agente">
          <h4 className={s.h4}>
            Proposta do agente · versão {proposal.number}
            {proposal.request ? <span className={s.muted}> · «{proposal.request}»</span> : null}
          </h4>
          <DiffView
            before={current ? generatedParagraphs(current.content).join("\n") : ""}
            after={generatedParagraphs(proposal.content).join("\n")}
            beforeLabel={current ? `versão ${current.number}` : "sem texto"}
            afterLabel={`proposta (versão ${proposal.number})`}
            label="Diferenças entre o texto atual e a proposta"
          />
          {proposal.issues.length ? (
            <p className={s.note}>
              {proposal.issues.length} alerta(s): {[...new Set(proposal.issues.map((i) => i.rule))].join(", ")}.
            </p>
          ) : null}
          {proposal.missing_data.length ? <p className={s.muted}>Faltam: {proposal.missing_data.join(", ")}.</p> : null}
          {canWrite ? (
            <Buttons>
              <Button
                variant="primary"
                small
                disabled={actions.decide.isPending}
                onClick={() => actions.decide.mutate({ versionId: proposal.id, decision: "accept" })}
              >
                Aceitar proposta
              </Button>
              <Button
                small
                disabled={actions.decide.isPending}
                onClick={() => actions.decide.mutate({ versionId: proposal.id, decision: "reject" })}
              >
                Rejeitar
              </Button>
            </Buttons>
          ) : null}
        </section>
      ) : null}
      {canWrite && x.active && x.has_adaptive ? (
        <section>
          <h4 className={s.h4}>Pedir ao agente</h4>
          {hasPending(x.content) ? (
            <Buttons>
              <Button small disabled={actions.generate.isPending} onClick={() => actions.generate.mutate()}>
                Gerar esta secção
              </Button>
            </Buttons>
          ) : null}
          <label htmlFor={requestId} className={s.label}>
            Pedido em linguagem natural (ex.: «reescreve para concurso público»)
          </label>
          <textarea
            id={requestId}
            rows={3}
            value={request}
            onChange={(e) => setRequest(e.target.value)}
            className={s.input}
          />
          {actions.ask.error ? <ErrorNote>{actions.ask.error.message}</ErrorNote> : null}
          <Buttons>
            <Button
              small
              disabled={actions.ask.isPending || request.trim().length < 3}
              onClick={() => actions.ask.mutate(request.trim(), { onSuccess: () => setRequest("") })}
            >
              Enviar pedido
            </Button>
          </Buttons>
          <p className={s.muted}>A resposta chega como proposta: aceita-se ou rejeita-se no diff.</p>
        </section>
      ) : null}
    </div>
  );
}
