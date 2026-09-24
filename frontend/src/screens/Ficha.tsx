/** Screen C: the ficha-base of the project, built only from the uploaded files. */

import { useState } from "react";

import { useActiveProject } from "../app/activeProject";
import {
  revealValue,
  useConfirmRevision,
  useFicha,
  useMe,
  useProject,
  useResolveConflict,
} from "../api/queries";
import type { Candidate, Circuit, Ficha, FichaValue } from "../api/types";
import {
  Button,
  ButtonLink,
  Buttons,
  Card,
  DataTable,
  EmptyState,
  ErrorNote,
  MaskedValue,
  OriginTag,
  Pill,
  Timeline,
} from "../components/ui";
import { formatDateTime, formatValue, ORIGIN_LABELS } from "../lib/format";
import { Loading, NoProject } from "./common";
import s from "./Ficha.module.css";
import { Screen } from "./Screen";

const detail = (file: string | null, ref: string | null) => [file, ref].filter(Boolean).join(" · ");

function Value({ value, revealed, onReveal }: { value: FichaValue; revealed?: unknown; onReveal: () => void }) {
  const shown = revealed !== undefined ? revealed : value.value;
  const text = `${formatValue(shown)}${value.unit && shown !== null ? ` ${value.unit}` : ""}`;
  if (value.status === "conflict") return <Pill tone="warn">Conflito</Pill>;
  return <MaskedValue masked={value.masked && revealed === undefined} value={text} onReveal={onReveal} />;
}

function Groups({ ficha }: { ficha: Ficha }) {
  const [revealed, setRevealed] = useState<Record<string, unknown>>({});
  const [error, setError] = useState<string | null>(null);
  const reveal = async (id: string) => {
    try {
      const value = await revealValue(id);
      setRevealed((r) => ({ ...r, [id]: value.value }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível mostrar o valor.");
    }
  };
  const groups = ficha.groups.filter((g) => g.values.length > 0);
  return (
    <>
      {error ? <ErrorNote>{error}</ErrorNote> : null}
      <div className={s.groups}>
        {groups.map((group) => (
          <Card key={group.name} title={group.name}>
            <dl className={s.kv}>
              {group.values.map((v) => (
                <div key={v.id}>
                  <dt>{v.label}</dt>
                  <dd>
                    <Value value={v} revealed={revealed[v.id]} onReveal={() => void reveal(v.id)} />
                    {v.status !== "conflict" ? (
                      <OriginTag source={v.source_type} detail={detail(v.source_file, v.source_ref)} />
                    ) : null}
                  </dd>
                </div>
              ))}
            </dl>
          </Card>
        ))}
      </div>
    </>
  );
}

function candidateText(c: Candidate, unit: string | null): string {
  return `${formatValue(c.value)}${unit && c.value !== "•••" ? ` ${unit}` : ""}`;
}

function ConflictBox({ projectId, value, canResolve }: { projectId: string; value: FichaValue; canResolve: boolean }) {
  const conflict = value.conflict;
  const [choice, setChoice] = useState<number | "manual" | null>(null);
  const [manual, setManual] = useState("");
  const [note, setNote] = useState("");
  const resolve = useResolveConflict(projectId);
  if (!conflict) return null;
  const idBase = `conflict-${conflict.id}`;
  const submit = () => {
    if (choice === null) return;
    resolve.mutate({
      conflictId: conflict.id,
      candidate: choice === "manual" ? undefined : choice,
      manual: choice === "manual" ? manualValue(manual) : undefined,
      note,
    });
  };
  return (
    <section className={s.conflict} aria-labelledby={`${idBase}-title`}>
      <h3 id={`${idBase}-title`} className={s.conflictTitle}>
        {value.label}: as fontes não coincidem
      </h3>
      <p>O agente não escolhe por maioria nem pela data: é preciso uma pessoa confirmar.</p>
      <div className={s.pick} role="group" aria-label={`Candidatos para ${value.label}`}>
        {conflict.candidates.map((c, i) => (
          <button
            key={i}
            type="button"
            aria-pressed={choice === i}
            disabled={!canResolve}
            onClick={() => setChoice(i)}
          >
            <b>{candidateText(c, value.unit)}</b>
            <span>
              {ORIGIN_LABELS[c.source_type]} · {detail(c.source_file, c.source_ref)}
              {c.file_date ? ` · ${formatDateTime(c.file_date)}` : ""}
            </span>
          </button>
        ))}
      </div>
      {canResolve ? (
        <div className={s.resolve}>
          <label className={s.inline}>
            <input type="radio" checked={choice === "manual"} onChange={() => setChoice("manual")} /> Outro valor
          </label>
          {choice === "manual" ? (
            <input
              aria-label="Outro valor"
              value={manual}
              onChange={(e) => setManual(e.target.value)}
              className={s.input}
            />
          ) : null}
          <label htmlFor={`${idBase}-note`}>Justificação (fica registada)</label>
          <textarea
            id={`${idBase}-note`}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            className={s.input}
          />
          {resolve.error ? <ErrorNote>{resolve.error.message}</ErrorNote> : null}
          <Buttons>
            <Button
              variant="primary"
              onClick={submit}
              disabled={choice === null || note.trim().length < 3 || resolve.isPending}
            >
              Confirmar escolha
            </Button>
          </Buttons>
        </div>
      ) : (
        <p className={s.muted}>Só um técnico responsável pode resolver conflitos.</p>
      )}
    </section>
  );
}

/** A manual value keeps its type: numbers typed as "34,5" are sent as numbers. */
function manualValue(text: string): unknown {
  const trimmed = text.trim();
  const number = Number(trimmed.replace(/\s/g, "").replace(",", "."));
  return trimmed !== "" && Number.isFinite(number) && /^[\d\s.,-]+$/.test(trimmed) ? number : trimmed;
}

function Cell({ value, fail, label }: { value: string | null; fail: boolean; label: string }) {
  return (
    <td className={fail ? s.fail : s.num}>
      {formatValue(value)}
      {fail ? <span className="visually-hidden">{` (não cumpre ${label})`}</span> : null}
    </td>
  );
}

function Circuits({ circuits, note }: { circuits: Circuit[]; note: string }) {
  if (circuits.length === 0) {
    return (
      <EmptyState title="Sem troços" next="Os troços vêm da Tabela de Cálculo, uma linha por troço.">
        Ainda não foi lida nenhuma Tabela de Cálculo.
      </EmptyState>
    );
  }
  const fails = circuits.filter((c) => c.cal01.ib_in_iz === "fail" || c.cal01.i2_iz145 === "fail").length;
  return (
    <>
      <div className={s.circuitsHead}>
        <h2 className={s.h2}>Quadros e troços</h2>
        {fails > 0 ? (
          <Pill tone="warn">{`CAL-01: ${fails} troço${fails > 1 ? "s" : ""} a confirmar na folha`}</Pill>
        ) : (
          <Pill tone="ok">CAL-01: sem falhas nas comparações feitas</Pill>
        )}
      </div>
      <DataTable caption="Troços da Tabela de Cálculo">
        <thead>
          <tr>
            <th scope="col">Troço</th>
            <th scope="col">kVA</th>
            <th scope="col">IB (A)</th>
            <th scope="col">In (A)</th>
            <th scope="col">Iz (A)</th>
            <th scope="col">I2 (A)</th>
            <th scope="col">1,45·Iz (A)</th>
            <th scope="col">Cabo</th>
            <th scope="col">L (m)</th>
            <th scope="col">QDT (%)</th>
            <th scope="col">Origem</th>
          </tr>
        </thead>
        <tbody>
          {circuits.map((c) => {
            const a = c.cal01.ib_in_iz === "fail";
            const b = c.cal01.i2_iz145 === "fail";
            return (
              <tr key={c.id}>
                <th scope="row" className={s.rowHead}>
                  {c.origin} → {c.destination}
                  {c.section ? <span className={s.muted}>{c.section}</span> : null}
                </th>
                <td className={s.num}>{formatValue(c.kva)}</td>
                <Cell value={c.ib_a} fail={a} label="IB ≤ In ≤ Iz" />
                <Cell value={c.in_a} fail={a} label="IB ≤ In ≤ Iz" />
                <Cell value={c.iz_a} fail={a} label="IB ≤ In ≤ Iz" />
                <Cell value={c.i2_a} fail={b} label="I2 ≤ 1,45·Iz" />
                <Cell value={c.iz145_a} fail={b} label="I2 ≤ 1,45·Iz" />
                <td className={s.cable}>{c.cable_raw ?? "—"}</td>
                <td className={s.num}>{formatValue(c.length_m)}</td>
                <td className={s.num}>{formatValue(c.vd_total_pct)}</td>
                <td>
                  <OriginTag source="calc" detail={c.source_ref} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </DataTable>
      <p className={s.muted}>
        A CAL-01 compara valores que já estão na Tabela de Cálculo (IB ≤ In ≤ Iz e I2 ≤ 1,45·Iz) e não
        recalcula nada: um troço destacado pede confirmação na folha. {note}
      </p>
    </>
  );
}

export function FichaScreen() {
  const projectId = useActiveProject();
  const { data: project } = useProject(projectId);
  const { data: ficha, isLoading, error } = useFicha(projectId);
  const { data: me } = useMe();
  const confirm = useConfirmRevision(projectId ?? "");
  const isTecnico = me?.roles.some((r) => r.id === "tecnico") ?? false;

  if (!projectId) {
    return (
      <Screen title="Ficha do projeto">
        <NoProject screen="a ficha-base" />
      </Screen>
    );
  }
  const revision = ficha?.revision;
  const conflicts = ficha?.groups.flatMap((g) => g.values).filter((v) => v.conflict) ?? [];
  const confirmReason = !revision
    ? "Ainda não há ficha-base."
    : revision.status !== "draft"
      ? "Esta revisão já está confirmada."
      : ficha && ficha.open_conflicts > 0
        ? "Resolva primeiro os conflitos."
        : !isTecnico
          ? "Só um técnico responsável pode confirmar."
          : null;

  return (
    <Screen
      crumb={project ? `${project.code} · ${project.name}` : "Projeto"}
      title={revision ? `Ficha-base · rev. ${revision.label}` : "Ficha do projeto"}
      description="Os dados principais do projeto num único sítio, com a origem de cada valor. É a fonte de verdade para redigir e comparar as peças."
      actions={<ButtonLink to={`/projetos/${projectId}/ficheiros`}>Carregar ficheiros</ButtonLink>}
    >
      {isLoading ? <Loading /> : null}
      {error ? <ErrorNote>Não foi possível carregar a ficha-base: {error.message}</ErrorNote> : null}
      {ficha && !revision ? (
        <EmptyState
          title="Ainda não há ficha-base"
          action={
            <ButtonLink to={`/projetos/${projectId}/ficheiros`} variant="primary">
              Carregar ficheiros
            </ButtonLink>
          }
          next="Cada valor vai mostrar a origem (ficheiro, folha e célula ou linha). Quando as fontes divergirem, o valor fica em aberto até uma pessoa o confirmar."
        >
          Carregue a ficha eletrotécnica e a Tabela de Cálculo para criar a ficha-base.
        </EmptyState>
      ) : null}
      {ficha && revision ? (
        <div className={s.main}>
          <div className={s.content}>
            {conflicts.map((v) => (
              <ConflictBox key={v.id} projectId={projectId} value={v} canResolve={isTecnico} />
            ))}
            <Groups ficha={ficha} />
            <Circuits circuits={ficha.circuits} note={ficha.cal01_note} />
          </div>
          <aside className={s.side}>
            <Card title="Estado">
              {revision.status === "confirmed" ? (
                <Pill tone="ok">Confirmada</Pill>
              ) : ficha.open_conflicts > 0 ? (
                <Pill tone="warn">{`${ficha.open_conflicts} conflito${ficha.open_conflicts > 1 ? "s" : ""} por resolver`}</Pill>
              ) : (
                <Pill tone="info">Por confirmar</Pill>
              )}
              <Buttons>
                <Button
                  variant="dark"
                  disabled={!ficha.can_confirm || !isTecnico || confirm.isPending}
                  onClick={() => confirm.mutate(revision.id)}
                >
                  Confirmar revisão {revision.label}
                </Button>
              </Buttons>
              {confirmReason ? <p className={s.muted}>{confirmReason}</p> : null}
              {confirm.error ? <ErrorNote>{confirm.error.message}</ErrorNote> : null}
            </Card>
            <Card title="Revisões">
              <Timeline
                items={[...ficha.revisions].reverse().map((r) => ({
                  id: r.id,
                  time: formatDateTime(r.confirmed_at ?? r.created_at),
                  who: `rev. ${r.label}`,
                  what:
                    r.status === "confirmed"
                      ? "confirmada"
                      : r.status === "superseded"
                        ? "substituída"
                        : "em rascunho",
                  human: r.status === "confirmed",
                }))}
              />
            </Card>
          </aside>
        </div>
      ) : null}
    </Screen>
  );
}
