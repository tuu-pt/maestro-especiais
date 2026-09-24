import type { ReactNode } from "react";

import { ButtonLink, Buttons, EmptyState } from "../components/ui";
import s from "./common.module.css";

export function NoProject({ screen }: { screen: string }) {
  return (
    <EmptyState
      title="Nenhum projeto selecionado"
      action={
        <Buttons>
          <ButtonLink to="/">Escolher no painel</ButtonLink>
          <ButtonLink to="/projetos/novo" variant="primary">
            Criar projeto
          </ButtonLink>
        </Buttons>
      }
    >
      {`Escolha um projeto para ver ${screen}.`}
    </EmptyState>
  );
}

/** Preconditions of a screen, checked against real data (✓ met, ! missing). */
export function Checklist({ items }: { items: { done: boolean; text: ReactNode }[] }) {
  return (
    <ul className={s.checklist}>
      {items.map((item, i) => (
        <li key={i} className={item.done ? s.done : s.missing}>
          <span className="visually-hidden">{item.done ? "Cumprido: " : "Em falta: "}</span>
          {item.text}
        </li>
      ))}
    </ul>
  );
}

export function Loading() {
  return <p className={s.loading}>A carregar…</p>;
}
