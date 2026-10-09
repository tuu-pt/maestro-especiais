/** «Registar problema» (Phase 8): from any screen, a short note for the pilot, with the project and screen. */

import { type FormEvent, useEffect, useId, useRef, useState } from "react";
import { useLocation } from "react-router";

import { useAddPilotNote } from "../api/queries";
import { ErrorNote } from "../components/ui";
import s from "./ProblemButton.module.css";

export function ProblemButton({ projectId }: { projectId: string | undefined }) {
  const { pathname, search } = useLocation();
  const add = useAddPilotNote();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [sent, setSent] = useState(false);
  const area = useRef<HTMLTextAreaElement>(null);
  const opener = useRef<HTMLButtonElement>(null);
  const id = useId();

  useEffect(() => {
    if (open) area.current?.focus();
  }, [open]);

  const close = () => {
    setOpen(false);
    opener.current?.focus();
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const doc = new URLSearchParams(search).get("doc");
    add.mutate(
      {
        text,
        screen: pathname.split("/").filter(Boolean).pop() ?? "",
        project_id: projectId ?? null,
        hint: doc ? doc.toLowerCase() : null,
      },
      {
        onSuccess: () => {
          setText("");
          setSent(true);
          close();
        },
      },
    );
  };

  return (
    <div className={s.wrap}>
      <button
        ref={opener}
        type="button"
        className={s.open}
        aria-expanded={open}
        aria-controls={`${id}-panel`}
        onClick={() => {
          setSent(false);
          setOpen((o) => !o);
        }}
      >
        Registar problema
      </button>
      {sent ? (
        <span role="status" className="visually-hidden">
          Problema registado.
        </span>
      ) : null}
      {open ? (
        <form
          id={`${id}-panel`}
          role="dialog"
          aria-labelledby={`${id}-title`}
          className={s.panel}
          onSubmit={submit}
          onKeyDown={(e) => {
            if (e.key === "Escape") close();
          }}
        >
          <h2 id={`${id}-title`} className={s.title}>
            Registar problema do piloto
          </h2>
          <label htmlFor={`${id}-text`} className={s.label}>
            O que está errado ou falta? (sem nomes, moradas nem contactos)
          </label>
          <textarea
            id={`${id}-text`}
            ref={area}
            rows={3}
            value={text}
            onChange={(e) => setText(e.target.value)}
            className={s.text}
          />
          <p className={s.hint}>Fica ligado a este ecrã{projectId ? " e ao projeto ativo" : ""}.</p>
          {add.error ? <ErrorNote>{add.error.message}</ErrorNote> : null}
          <div className={s.buttons}>
            <button type="submit" className={s.send} disabled={text.trim().length < 3 || add.isPending}>
              Registar
            </button>
            <button type="button" className={s.cancel} onClick={close}>
              Cancelar
            </button>
          </div>
        </form>
      ) : null}
    </div>
  );
}
