/** Sign in with the TUU account (email and password; until D6), as in the Registo de Temas Estratégicos. */

import { type FormEvent, useId, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router";

import { ApiError } from "../api/client";
import { useLogin, useMe } from "../api/queries";
import { Button } from "../components/ui";
import { backTo } from "../lib/backTo";
import s from "./Login.module.css";

export function LoginScreen() {
  const [params] = useSearchParams();
  const next = backTo(params.get("volta"));
  const navigate = useNavigate();
  const { data: me } = useMe();
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const id = useId();

  if (me?.session === "account") return <Navigate to={next} replace />;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    login.mutate({ email, password }, { onSuccess: () => navigate(next, { replace: true }) });
  };
  const error = login.error;
  const message =
    error instanceof ApiError && error.status === 401
      ? "Email ou password inválidos. Tente novamente."
      : error?.message;

  return (
    <main className={s.wrap} id="conteudo">
      <form className={s.card} onSubmit={submit} aria-labelledby={`${id}-title`}>
        <p className={s.eyebrow}>
          <i aria-hidden="true" />
          TUU · Building Design Management
        </p>
        <h1 id={`${id}-title`} className={s.title}>
          Maestro Especiais
        </h1>
        <p className={s.sub}>Inicie sessão com a sua conta TUU para aceder aos projetos.</p>
        {message ? (
          <p role="alert" className={s.error}>
            {message}
          </p>
        ) : null}
        <label className={s.field}>
          <span>Email</span>
          <input
            type="email"
            name="email"
            autoComplete="username"
            placeholder="nome@tuu.pt"
            required
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label className={s.field}>
          <span>Password</span>
          <input
            type="password"
            name="password"
            autoComplete="current-password"
            placeholder="••••••••"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <Button type="submit" variant="primary" className={s.submit} disabled={login.isPending}>
          {login.isPending ? "A entrar…" : "Entrar"}
        </Button>
        <p className={s.note}>
          Sem conta ainda? Peça ao administrador para a criar com <code>make create-user</code>.
        </p>
      </form>
    </main>
  );
}
