import { Link } from "react-router";

import { useActivity, useProjects } from "../api/queries";
import type { Project } from "../api/types";
import { ButtonLink, Card, DataTable, EmptyState, ErrorNote, Pill } from "../components/ui";
import { formatDateTime } from "../lib/format";
import { Loading } from "./common";
import s from "./Dashboard.module.css";
import { Screen } from "./Screen";

export function FichaStatus({ project }: { project: Project }) {
  if (project.open_conflicts > 0) {
    const n = project.open_conflicts;
    return <Pill tone="warn">{`${n} conflito${n > 1 ? "s" : ""} por resolver`}</Pill>;
  }
  switch (project.ficha_status) {
    case "confirmed":
      return <Pill tone="ok">Ficha-base confirmada</Pill>;
    case "draft":
      return <Pill tone="info">Ficha-base por confirmar</Pill>;
    default:
      return <Pill tone="mute">Sem ficha-base</Pill>;
  }
}

const PHASES = { licenciamento: "Licenciamento", execucao: "Execução" } as const;

function Activity() {
  const { data: events = [] } = useActivity();
  return (
    <Card title="Atividade recente">
      {events.length === 0 ? (
        <p className={s.muted}>Ainda não há atividade.</p>
      ) : (
        <ul className={s.feed}>
          {events.map((e) => (
            <li key={e.id} className={e.actor_type === "user" ? s.human : undefined}>
              <div>
                {e.project_code ? <b>{e.project_code} · </b> : null}
                {e.description}
                <time dateTime={e.at}>
                  {formatDateTime(e.at)} · {e.actor_name}
                </time>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function DashboardScreen() {
  const { data: projects, isLoading, error } = useProjects();
  const list = projects ?? [];
  const drafts = list.filter((p) => p.ficha_status === "draft").length;
  const conflicts = list.reduce((sum, p) => sum + p.open_conflicts, 0);
  const files = list.reduce((sum, p) => sum + p.file_count, 0);
  return (
    <Screen
      crumb="Instalações elétricas"
      title="Painel"
      description="Os projetos, o estado da ficha-base de cada um e o que aconteceu desde a última visita."
      actions={
        list.length > 0 ? (
          <ButtonLink to="/projetos/novo" variant="primary">
            + Novo projeto
          </ButtonLink>
        ) : null
      }
    >
      {isLoading ? <Loading /> : null}
      {error ? <ErrorNote>Não foi possível carregar os projetos: {error.message}</ErrorNote> : null}
      {projects && list.length === 0 ? (
        <EmptyState
          title="Ainda não há projetos"
          action={
            <ButtonLink to="/projetos/novo" variant="primary">
              Criar projeto
            </ButtonLink>
          }
          next="Depois de criar o projeto, carregue a ficha eletrotécnica e a Tabela de Cálculo para criar a ficha-base."
        >
          Tudo o que aparece no Maestro Especiais vem dos documentos que carregar.
        </EmptyState>
      ) : null}
      {list.length > 0 ? (
        <>
          <div className={s.stats}>
            <Stat label="Projetos" value={list.length} />
            <Stat label="Fichas por confirmar" value={drafts} />
            <Stat label="Conflitos por resolver" value={conflicts} tone={conflicts ? "warn" : undefined} />
            <Stat label="Ficheiros carregados" value={files} />
          </div>
          <div className={s.dash}>
            <DataTable caption="Projetos">
              <thead>
                <tr>
                  <th scope="col">Projeto</th>
                  <th scope="col">Fase</th>
                  <th scope="col">Ficheiros</th>
                  <th scope="col">Ficha-base</th>
                  <th scope="col">Criado</th>
                </tr>
              </thead>
              <tbody>
                {list.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <Link to={`/projetos/${p.id}/ficha`} className={s.project}>
                        {p.code}
                      </Link>
                      <div className={s.muted}>
                        {p.name}
                        {p.building_type ? ` · ${p.building_type}` : ""}
                      </div>
                    </td>
                    <td>{PHASES[p.phase]}</td>
                    <td className={s.num}>{p.file_count}</td>
                    <td>
                      <FichaStatus project={p} />
                    </td>
                    <td className={s.muted}>{formatDateTime(p.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
            <Activity />
          </div>
        </>
      ) : null}
    </Screen>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: "warn" }) {
  return (
    <div className={s.stat}>
      <div className={s.statLabel}>{label}</div>
      <div className={tone ? `${s.statValue} ${s.warn}` : s.statValue}>{value}</div>
    </div>
  );
}
