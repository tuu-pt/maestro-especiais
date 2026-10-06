/**
 * DiffView (SPEC 13): word-level differences between two texts, e.g. the agent's proposal and
 * the técnico's edit, or a section in revision A and now.
 *
 * Readable in both themes (tokens), and by keyboard and screen reader: "Alteração anterior /
 * seguinte" move the focus to each change, and each change says whether it was inserted or removed.
 */

import { diffWords } from "diff";
import { useMemo, useRef, useState } from "react";

import s from "./DiffView.module.css";
import { Button } from "./ui";

type Props = {
  before: string;
  after: string;
  beforeLabel?: string;
  afterLabel?: string;
  /** accessible name of the text with the changes */
  label: string;
};

export function DiffView({ before, after, beforeLabel, afterLabel, label }: Props) {
  const parts = useMemo(() => {
    let change = -1;
    return diffWords(before, after).map((p) => ({ ...p, change: p.added || p.removed ? ++change : -1 }));
  }, [before, after]);
  const changes = parts.filter((p) => p.change >= 0).length;
  const body = useRef<HTMLDivElement>(null);
  const [current, setCurrent] = useState(-1);

  const go = (step: number) => {
    const marks = body.current?.querySelectorAll<HTMLElement>("[data-change]") ?? [];
    if (!marks.length) return;
    const n = marks.length;
    const next = current < 0 ? (step > 0 ? 0 : n - 1) : (current + step + n) % n;
    setCurrent(next);
    marks[next]?.focus();
  };

  return (
    <div className={s.diff}>
      <div className={s.head}>
        <span>
          {beforeLabel && afterLabel ? (
            <>
              {beforeLabel} <span aria-hidden="true">→</span>
              <span className="visually-hidden"> comparado com </span> {afterLabel}
            </>
          ) : null}
        </span>
        <span className={s.count} role="status">
          {changes === 0 ? "Sem alterações" : `${changes} ${changes === 1 ? "alteração" : "alterações"}`}
        </span>
        {changes > 0 ? (
          <span className={s.nav}>
            <Button small onClick={() => go(-1)}>
              Alteração anterior
            </Button>
            <Button small onClick={() => go(1)}>
              Alteração seguinte
            </Button>
          </span>
        ) : null}
      </div>
      <div ref={body} className={s.text} aria-label={label} role="region">
        {parts.map((p, i) => {
          if (p.change < 0) return <span key={i}>{p.value}</span>;
          const Tag = p.added ? "ins" : "del";
          return (
            <Tag key={i} data-change={p.change} tabIndex={-1} className={p.change === current ? s.focus : undefined}>
              <span className="visually-hidden">{p.added ? "inserido: " : "removido: "}</span>
              {p.value}
            </Tag>
          );
        })}
      </div>
    </div>
  );
}
