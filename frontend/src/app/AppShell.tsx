import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { Link, Navigate, NavLink, Outlet, useLocation, useNavigate } from "react-router";

import { ApiError, getDevUser, setDevUser } from "../api/client";
import { useDevUsers, useLogout, useMe, useProject } from "../api/queries";
import { useActiveProject } from "./activeProject";
import { ProblemButton } from "./ProblemButton";
import s from "./AppShell.module.css";
import { applyTheme, storedTheme, type Theme } from "./theme";
import { usePilotClock } from "./usePilotClock";

const icon = (d: ReactNode) => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
    {d}
  </svg>
);

const ICONS = {
  painel: icon(
    <>
      <rect x="2" y="2" width="5" height="5" />
      <rect x="9" y="2" width="5" height="5" />
      <rect x="2" y="9" width="5" height="5" />
      <rect x="9" y="9" width="5" height="5" />
    </>,
  ),
  ficha: icon(
    <>
      <rect x="2.5" y="1.5" width="11" height="13" rx="1" />
      <path d="M5 5h6M5 8h6M5 11h3.5" />
    </>,
  ),
  docs: icon(
    <>
      <path d="M4 1.5h5.5L12.5 4.5v10h-8.5z" />
      <path d="M6 8h4.5M6 10.5h4.5" />
    </>,
  ),
  val: icon(
    <>
      <path d="M8 1.5l5.5 2v4c0 3.3-2.4 5.8-5.5 7-3.1-1.2-5.5-3.7-5.5-7v-4z" />
      <path d="M5.5 8l1.8 1.8L10.8 6.3" />
    </>,
  ),
  equip: icon(
    <>
      <rect x="2" y="4" width="12" height="8" rx="1" />
      <circle cx="6" cy="8" r="1.6" />
      <path d="M9.5 7h2.5M9.5 9h2.5" />
    </>,
  ),
  kb: icon(<path d="M2 3h4.5c.8 0 1.5.7 1.5 1.5V14c0-.8-.7-1.5-1.5-1.5H2zM14 3H9.5C8.7 3 8 3.7 8 4.5V14c0-.8.7-1.5 1.5-1.5H14z" />),
  review: icon(
    <>
      <circle cx="8" cy="8" r="6" />
      <path d="M8 4.5V8l2.5 1.5" />
    </>,
  ),
  pilot: icon(
    <>
      <path d="M2.5 13.5h11" />
      <path d="M4 11V8M7 11V5.5M10 11V7M13 11V3.5" />
    </>,
  ),
  set: icon(
    <>
      <circle cx="8" cy="8" r="2.2" />
      <path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M3.4 12.6l1.4-1.4M11.2 4.8l1.4-1.4" />
    </>,
  ),
};

type NavItem = { label: string; icon: ReactNode; path: string; scoped: boolean };

const NAV: NavItem[] = [
  { label: "Painel", icon: ICONS.painel, path: "", scoped: false },
  { label: "Ficha do projeto", icon: ICONS.ficha, path: "ficha", scoped: true },
  { label: "Documentos", icon: ICONS.docs, path: "documentos", scoped: true },
  { label: "Validação", icon: ICONS.val, path: "validacao", scoped: true },
  { label: "Equipamentos", icon: ICONS.equip, path: "equipamentos", scoped: true },
  { label: "Revisão", icon: ICONS.review, path: "revisao", scoped: true },
  { label: "Piloto", icon: ICONS.pilot, path: "piloto", scoped: true },
  { label: "Conhecimento", icon: ICONS.kb, path: "conhecimento", scoped: false },
  { label: "Definições", icon: ICONS.set, path: "definicoes", scoped: false },
];

function href(item: NavItem, projectId: string | undefined): string {
  if (!item.path) return "/";
  return item.scoped && projectId ? `/projetos/${projectId}/${item.path}` : `/${item.path}`;
}

function DevUserSwitcher() {
  const { data: users = [] } = useDevUsers();
  const client = useQueryClient();
  const [login, setLogin] = useState(getDevUser());
  if (users.length === 0) return null;
  return (
    <label>
      Utilizador de desenvolvimento
      <select
        value={login}
        onChange={(event) => {
          setDevUser(event.target.value);
          setLogin(event.target.value);
          void client.invalidateQueries();
        }}
      >
        {users.map((u) => (
          <option key={u.login} value={u.login}>
            {u.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function ThemeSelect() {
  const [theme, setTheme] = useState<Theme>(storedTheme());
  return (
    <label>
      Tema
      <select
        value={theme}
        onChange={(event) => {
          const next = event.target.value as Theme;
          applyTheme(next);
          setTheme(next);
        }}
      >
        <option value="system">Do sistema</option>
        <option value="light">Claro</option>
        <option value="dark">Escuro</option>
      </select>
    </label>
  );
}

/** Who is signed in, and the way out (accounts with a password; until D6). */
function SessionTools() {
  const { data: me } = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  if (me?.session !== "account") return <DevUserSwitcher />;
  return (
    <>
      <span className={s.who}>{me.name}</span>
      <button
        type="button"
        className={s.out}
        disabled={logout.isPending}
        onClick={() => logout.mutate(undefined, { onSuccess: () => navigate("/entrar", { replace: true }) })}
      >
        Sair
      </button>
    </>
  );
}

export default function AppShell() {
  const projectId = useActiveProject();
  const { data: project } = useProject(projectId);
  const { error } = useMe();
  usePilotClock(project?.id);
  const location = useLocation();
  if (error instanceof ApiError && error.status === 401) {
    const back = encodeURIComponent(`${location.pathname}${location.search}`);
    return <Navigate to={`/entrar?volta=${back}`} replace />;
  }
  return (
    <>
      <header className={s.band}>
        <div className={s.bandIn}>
          <Link to="/" className={s.logo}>
            <i aria-hidden="true" />
            Maestro Especiais <span>TUU · Building Design Management</span>
          </Link>
          <div className={s.tools}>
            <ProblemButton projectId={project?.id} />
            <SessionTools />
            <ThemeSelect />
          </div>
        </div>
      </header>
      <div className={s.layout}>
        <nav className={s.side} aria-label="Navegação principal">
          {NAV.map((item) => (
            <NavLink key={item.label} to={href(item, projectId)} end={!item.path}>
              {item.icon}
              {item.label}
            </NavLink>
          ))}
          {project ? (
            <div className={s.project}>
              Projeto ativo<b>{project.code}</b>
              {project.name}
            </div>
          ) : null}
        </nav>
        <main className={s.main} id="conteudo">
          <Outlet />
        </main>
      </div>
    </>
  );
}
