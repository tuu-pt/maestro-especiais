/** Base components (SPEC 13). Colours and fonts come only from tokens.css. */

import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link } from "react-router";

import type { SourceType } from "../api/types";
import { ORIGIN_LABELS } from "../lib/format";
import s from "./ui.module.css";

const cx = (...names: (string | false | undefined | null)[]) => names.filter(Boolean).join(" ");

export type Tone = "ok" | "warn" | "crit" | "info" | "mute";

export function Pill({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <span className={cx(s.pill, s[tone])}>{children}</span>;
}

export function Chip({ children }: { children: ReactNode }) {
  return <span className={s.chip}>{children}</span>;
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "primary" | "dark";
  small?: boolean;
};

export function Button({ variant = "default", small, className, ...props }: ButtonProps) {
  return (
    <button
      type="button"
      {...props}
      className={cx(s.btn, variant !== "default" && s[variant], small && s.sm, className)}
    />
  );
}

export function ButtonLink({
  to,
  variant = "default",
  children,
}: {
  to: string;
  variant?: "default" | "primary" | "dark";
  children: ReactNode;
}) {
  return (
    <Link to={to} className={cx(s.btn, variant !== "default" && s[variant])}>
      {children}
    </Link>
  );
}

export function Buttons({ children }: { children: ReactNode }) {
  return <div className={s.btns}>{children}</div>;
}

/** Where a value came from; the detail (file, sheet, cell or line) shows on hover and focus. */
export function OriginTag({ source, detail }: { source: SourceType; detail?: string | null }) {
  const label = ORIGIN_LABELS[source];
  return (
    <abbr
      className={cx(s.origin, s[`origin_${source}`])}
      title={detail ?? label}
      aria-label={detail ? `${label}: ${detail}` : label}
      tabIndex={0}
    >
      {label}
    </abbr>
  );
}

export function Card({
  title,
  children,
  className,
}: {
  title?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cx(s.card, className)}>
      {title ? <h4 className={s.cardTitle}>{title}</h4> : null}
      {children}
    </section>
  );
}

export function Label({ children }: { children: ReactNode }) {
  return <span className={s.label}>{children}</span>;
}

export type DotStatus = "ok" | "generated" | "todo" | "warn" | "crit";

export function StatusDot({ status, label }: { status: DotStatus; label: string }) {
  return <span className={cx(s.dot, s[`dot_${status}`])} role="img" aria-label={label} />;
}

const MODE_LABELS = { fixed: "fixo", parametric: "paramétrico", adaptive: "adaptativo" } as const;

export function BlockModeBadge({ mode }: { mode: keyof typeof MODE_LABELS }) {
  return <span className={s.mode}>{MODE_LABELS[mode]}</span>;
}

export function DataTable({ caption, children }: { caption: string; children: ReactNode }) {
  return (
    <div className={s.tbl} role="region" aria-label={caption} tabIndex={0}>
      <table>
        <caption className="visually-hidden">{caption}</caption>
        {children}
      </table>
    </div>
  );
}

/** Empty state: what is missing, the next action, and what the screen will do (SPEC 10). */
export function EmptyState({
  title,
  children,
  action,
  next,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  next?: ReactNode;
}) {
  return (
    <div className={s.empty}>
      <h3 className={s.emptyTitle}>{title}</h3>
      {children ? <p className={s.emptyText}>{children}</p> : null}
      {action}
      {next ? <p className={s.emptyNext}>{next}</p> : null}
    </div>
  );
}

/** Personal data stays masked until someone asks for it (the request is audited). */
export function MaskedValue({
  masked,
  value,
  onReveal,
  pending,
}: {
  masked: boolean;
  value: ReactNode;
  onReveal: () => void;
  pending?: boolean;
}) {
  if (!masked) return <>{value}</>;
  return (
    <span className={s.masked}>
      <span className={s.maskedValue} aria-label="Dado pessoal mascarado">
        •••
      </span>
      <button type="button" className={s.link} onClick={onReveal} disabled={pending}>
        Mostrar
      </button>
    </span>
  );
}

export type TimelineItem = { id: string; time: string; who: string; what: string; human: boolean };

export function Timeline({ items }: { items: TimelineItem[] }) {
  return (
    <ul className={s.timeline}>
      {items.map((item) => (
        <li key={item.id} className={item.human ? s.human : undefined}>
          <time>{item.time}</time>
          <i aria-hidden="true" />
          <span>
            <b>{item.who}</b> {item.what}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function Toast({ message }: { message: string | null }) {
  return (
    <div role="status" aria-live="polite">
      {message ? <div className={s.toast}>{message}</div> : null}
    </div>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className={s.error}>
      {children}
    </p>
  );
}
