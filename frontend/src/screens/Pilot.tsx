/**
 * Screen «Piloto» (Phase 8): the time measured in the application per step, against the
 * technician's estimate of the manual process; the incoherences left at each approval; the goal
 * of the SPEC; the problems written during the pilot. Without a project: every project of the pilot.
 */

import { type FormEvent, useId, useState } from "react";
import { Link } from "react-router";

import { useActiveProject } from "../app/activeProject";
import { useMe, usePilot, usePilotSummary, useSaveBaseline, useSetPilotNote } from "../api/queries";
import type { PilotBaseline, PilotNote, PilotProject, PilotStep } from "../api/types";
import { Button, Buttons, Card, DataTable, EmptyState, ErrorNote, Pill } from "../components/ui";
import { duration, formatDateTime, percent } from "../lib/format";
import { Loading } from "./common";
import s from "./Pilot.module.css";
import { Screen } from "./Screen";

const GROUPS = [
  ["identificacao", "Identificação"],
  ["potencia", "Potência"],
  ["cabos", "Cabos"],
] as const;

function useRoles() {
  const { data: me } = useMe();
  const roles = new Set(me?.roles.map((r) => r.id) ?? []);
  return { estimator: roles.has("tecnico") || roles.has("admin"), triager: roles.has("admin") || roles.has("curador") };
}

export function PilotScreen() {
  const projectId = useActiveProject();
  return (
    <Screen
      title="Piloto"
      description="O tempo de cada passo medido na aplicação, comparado com a estimativa do processo manual, e as incoerências que ficam na aprovação. É a medição da Fase 8."
    >
      {projectId ? <ProjectPilot projectId={projectId} /> : <Summary />}
    </Screen>
  );
}

function Summary() {
  const { data: projects, isPending, error } = usePilotSummary();
  if (isPending) return <Loading />;
  if (error) return <ErrorNote>{error.message}</ErrorNote>;
  if (projects.length === 0) {
    return (
      <EmptyState
        title="Ainda não há projetos no piloto"
        next="Aqui vai aparecer cada projeto com o tempo na aplicação, a estimativa do processo manual e se cumpre a meta (≥ 40 % e zero incoerências)."
      >
        Um projeto entra no piloto quando se trabalha nele (o tempo conta sozinho) ou quando o técnico escreve a
        estimativa do processo manual.
      </EmptyState>
    );
  }
  return (
    <DataTable caption="Projetos do piloto">
      <thead>
        <tr>
          <th scope="col">Projeto</th>
          <th scope="col">Na aplicação</th>
          <th scope="col">Estimativa manual</th>
          <th scope="col">Redução (MDJ, CTE, formulários)</th>
          <th scope="col">Meta</th>
        </tr>
      </thead>
      <tbody>
        {projects.map((p) => (
          <tr key={p.project_id}>
            <td>
              <Link to={`/projetos/${p.project_id}/piloto`}>{p.code}</Link>
              {p.typology ? <span className={s.muted}> · {p.typology}</span> : null}
            </td>
            <td>{duration(p.seconds)}</td>
            <td>{duration(p.estimate_seconds)}</td>
            <td>{percent(p.goal.reduction)}</td>
            <td>
              <GoalPill met={p.goal.met} approved={p.goal.approved} />
            </td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}

function GoalPill({ met, approved }: { met: boolean; approved: boolean }) {
  if (met) return <Pill tone="ok">Cumprida</Pill>;
  return <Pill tone={approved ? "warn" : "mute"}>{approved ? "Por cumprir" : "Sem peças aprovadas"}</Pill>;
}

function ProjectPilot({ projectId }: { projectId: string }) {
  const { data, isPending, error } = usePilot(projectId);
  if (isPending) return <Loading />;
  if (error) return <ErrorNote>{error.message}</ErrorNote>;
  const goal = data.goal;
  return (
    <div className={s.stack}>
      <div className={s.pills} aria-label="Meta do piloto">
        <Pill tone={goal.reduction === null ? "mute" : goal.time_ok ? "ok" : "warn"}>
          {`Tempo: ${percent(goal.reduction)} de redução (meta ≥ 40 %)`}
        </Pill>
        <Pill tone={!goal.approved ? "mute" : goal.coherent ? "ok" : "warn"}>
          {!goal.approved
            ? "Coerência: sem peças aprovadas"
            : goal.coherent
              ? "Coerência: zero incoerências na aprovação"
              : "Coerência: há incoerências na aprovação"}
        </Pill>
        <GoalPill met={goal.met} approved={goal.approved} />
      </div>
      <Times data={data} />
      <Approvals data={data} />
      <Estimate key={projectId} projectId={projectId} steps={data.steps} baseline={data.baseline} />
      <Notes notes={data.notes} />
    </div>
  );
}

function Times({ data }: { data: PilotProject }) {
  return (
    <Card title="Tempo por passo">
      {data.seconds === 0 ? (
        <p className={s.muted}>
          Ainda não há tempo medido: conta sozinho enquanto se trabalha no projeto (separador visível, sem pausas de
          mais de 2 minutos).
        </p>
      ) : null}
      <DataTable caption="Tempo por passo">
        <thead>
          <tr>
            <th scope="col">Passo</th>
            <th scope="col">Na aplicação</th>
            <th scope="col">Processo manual (estimativa)</th>
          </tr>
        </thead>
        <tbody>
          {data.steps.map((r) => (
            <tr key={r.step}>
              <th scope="row">{r.label}</th>
              <td>{duration(r.seconds)}</td>
              <td>{r.estimate_min ? `${r.estimate_min[0]}–${r.estimate_min[1]} min` : "—"}</td>
            </tr>
          ))}
          <tr>
            <th scope="row">Total</th>
            <td>{duration(data.seconds)}</td>
            <td>{data.estimate_seconds === null ? "—" : `${duration(data.estimate_seconds)} (meio do intervalo, passos com estimativa)`}</td>
          </tr>
        </tbody>
      </DataTable>
      <p className={s.muted}>
        O tempo fora da aplicação (telefonemas, deslocações) não conta. Se for importante, registe-o como problema.
      </p>
    </Card>
  );
}

function Approvals({ data }: { data: PilotProject }) {
  return (
    <Card title="Incoerências na aprovação">
      {data.approvals.length === 0 ? (
        <p className={s.muted}>
          Contam-se quando o técnico aprova uma peça: as de identificação, potência e cabos encontradas durante o
          projeto e as que ainda estavam abertas ou ignoradas.
        </p>
      ) : (
        <DataTable caption="Incoerências na aprovação">
          <thead>
            <tr>
              <th scope="col">Peça</th>
              {GROUPS.map(([, label]) => (
                <th key={label} scope="col">
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.approvals.map((a) => (
              <tr key={`${a.document}-${a.revision}`}>
                <th scope="row">
                  {a.document} · rev. {a.revision}
                  <span className={s.muted}> · {formatDateTime(a.approved_at)}</span>
                </th>
                {GROUPS.map(([key]) => {
                  const g = a.groups[key];
                  return (
                    <td key={key}>
                      {`${g.found} encontradas · ${g.open} abertas · ${g.ignored} ignoradas`}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </DataTable>
      )}
    </Card>
  );
}

type Range = { low: string; high: string };

function Estimate({
  projectId,
  steps,
  baseline,
}: {
  projectId: string;
  steps: PilotStep[];
  baseline: PilotBaseline | null;
}) {
  const { estimator } = useRoles();
  const save = useSaveBaseline(projectId);
  const base = useId();
  const [ranges, setRanges] = useState<Record<string, Range>>(() =>
    Object.fromEntries(
      steps.map((r) => {
        const v = baseline?.steps[r.step];
        return [r.step, { low: v ? String(v[0]) : "", high: v ? String(v[1]) : "" }];
      }),
    ),
  );
  const [rounds, setRounds] = useState(baseline?.rounds === null || !baseline ? "" : String(baseline.rounds));
  const [errors, setErrors] = useState(baseline?.errors ?? "");
  const [typology, setTypology] = useState(baseline?.typology ?? "");
  const filled = Object.entries(ranges).filter(([, r]) => r.low !== "" || r.high !== "");
  const invalid = filled.some(([, r]) => r.low === "" || r.high === "" || Number(r.low) > Number(r.high));

  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate({
      steps: Object.fromEntries(filled.map(([k, r]) => [k, [Number(r.low), Number(r.high)]])),
      rounds: rounds === "" ? null : Number(rounds),
      errors: errors || null,
      typology: typology || null,
    });
  };

  return (
    <Card title="Estimativa do processo manual">
      <p className={s.muted}>
        Quanto tempo levaria este projeto feito à mão, passo a passo, em minutos (de… a…). Escreva-a de preferência
        antes de começar, para não ser influenciada pelo tempo na aplicação.
        {baseline?.updated_at ? ` Última alteração: ${formatDateTime(baseline.updated_at)}.` : ""}
      </p>
      <form onSubmit={submit} className={s.form}>
        <fieldset disabled={!estimator} className={s.fieldset}>
          <legend className="visually-hidden">Minutos por passo</legend>
          {steps.map((r) => (
            <div key={r.step} className={s.range}>
              <span id={`${base}-${r.step}`} className={s.rangeLabel}>
                {r.label}
              </span>
              <input
                type="number"
                min={0}
                inputMode="numeric"
                aria-label={`${r.label}: mínimo (min)`}
                value={ranges[r.step]?.low ?? ""}
                onChange={(e) => setRanges((v) => ({ ...v, [r.step]: { ...v[r.step]!, low: e.target.value } }))}
                className={s.input}
              />
              <span aria-hidden="true">a</span>
              <input
                type="number"
                min={0}
                inputMode="numeric"
                aria-label={`${r.label}: máximo (min)`}
                value={ranges[r.step]?.high ?? ""}
                onChange={(e) => setRanges((v) => ({ ...v, [r.step]: { ...v[r.step]!, high: e.target.value } }))}
                className={s.input}
              />
            </div>
          ))}
          <label className={s.label}>
            Voltas de correção habituais
            <input
              type="number"
              min={0}
              max={50}
              value={rounds}
              onChange={(e) => setRounds(e.target.value)}
              className={s.input}
            />
          </label>
          <label className={s.label}>
            Tipologia (ex.: habitação unifamiliar, comércio)
            <input value={typology} onChange={(e) => setTypology(e.target.value)} className={s.wide} />
          </label>
          <label className={s.label}>
            Erros que aparecem mais vezes
            <textarea rows={2} value={errors} onChange={(e) => setErrors(e.target.value)} className={s.wide} />
          </label>
        </fieldset>
        {invalid ? <p className={s.muted}>Em cada passo, escreva o mínimo e o máximo (mínimo ≤ máximo).</p> : null}
        {save.error ? <ErrorNote>{save.error.message}</ErrorNote> : null}
        {estimator ? (
          <Buttons>
            <Button type="submit" variant="primary" small disabled={invalid || save.isPending}>
              Guardar estimativa
            </Button>
            {save.isSuccess ? (
              <span role="status" className={s.muted}>
                Guardada.
              </span>
            ) : null}
          </Buttons>
        ) : (
          <p className={s.muted}>Só o técnico responsável ou o administrador escreve a estimativa.</p>
        )}
      </form>
    </Card>
  );
}

function Notes({ notes }: { notes: PilotNote[] }) {
  const { triager } = useRoles();
  const set = useSetPilotNote();
  return (
    <Card title={`Problemas registados (${notes.length})`}>
      {notes.length === 0 ? (
        <p className={s.muted}>
          Ainda não há problemas. Use «Registar problema», no topo de qualquer ecrã, quando algo estiver errado ou
          faltar (um bloco a corrigir, um alerta que não faz sentido).
        </p>
      ) : (
        <ul className={s.notes}>
          {notes.map((n) => (
            <li key={n.id} className={s.note}>
              <div>
                <Pill tone={n.status === "open" ? "warn" : "ok"}>{n.status === "open" ? "Aberto" : "Resolvido"}</Pill>{" "}
                <span className={s.muted}>
                  {n.step ?? n.screen ?? "—"} · {formatDateTime(n.created_at)}
                </span>
              </div>
              <p className={s.noteText}>{n.text}</p>
              {triager ? (
                <Button
                  small
                  disabled={set.isPending}
                  onClick={() => set.mutate({ id: n.id, status: n.status === "open" ? "resolved" : "open" })}
                >
                  {n.status === "open" ? "Marcar como resolvido" : "Reabrir"}
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
