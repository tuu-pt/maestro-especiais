import type { ReactNode } from "react";

import s from "./Screen.module.css";

/** Page frame: breadcrumb, title, description and actions, as in the mock-up. */
export function Screen({
  crumb,
  title,
  description,
  actions,
  children,
}: {
  crumb?: ReactNode;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className={s.screen}>
      <div className={s.head}>
        <div>
          {crumb ? <div className={s.crumb}>{crumb}</div> : null}
          <h1 className={s.title}>{title}</h1>
          {description ? <p className={s.description}>{description}</p> : null}
        </div>
        {actions ? <div className={s.actions}>{actions}</div> : null}
      </div>
      {children}
    </div>
  );
}
