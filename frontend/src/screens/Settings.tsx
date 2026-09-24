import { useEffect, useState } from "react";

import { fetchHealth, type HealthResponse } from "../api/health";
import { useMe } from "../api/queries";
import { Card, Pill } from "../components/ui";
import c from "./common.module.css";
import { Screen } from "./Screen";

const SERVICE_LABELS: Record<string, string> = {
  database: "Base de dados",
  pgvector: "Pesquisa vetorial (pgvector)",
  redis: "Fila de trabalhos (Redis)",
  storage: "Armazenamento de ficheiros (S3)",
};

type HealthState = { kind: "loading" } | { kind: "loaded"; health: HealthResponse } | { kind: "unavailable" };

export function ServicesCard() {
  const [state, setState] = useState<HealthState>({ kind: "loading" });
  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal)
      .then((health) => setState({ kind: "loaded", health }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setState({ kind: "unavailable" });
      });
    return () => controller.abort();
  }, []);
  return (
    <Card title="Estado dos serviços">
      {state.kind === "loading" ? <p>A verificar…</p> : null}
      {state.kind === "unavailable" ? <Pill tone="crit">API indisponível</Pill> : null}
      {state.kind === "loaded" ? (
        <ul className={c.checklist}>
          {Object.entries(state.health.services).map(([name, service]) => (
            <li key={name} className={service.status === "ok" ? c.done : c.missing}>
              <span>
                {SERVICE_LABELS[name] ?? name} ·{" "}
                {service.status === "ok" ? (
                  <Pill tone="ok">Operacional</Pill>
                ) : (
                  <Pill tone="crit">Com falhas</Pill>
                )}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}

export function SettingsScreen() {
  const { data: me } = useMe();
  return (
    <Screen
      title="Definições"
      description="Utilizadores, modelos .docx/.xlsm, regras de validação e integrações ficam aqui (administrador)."
    >
      <div className={c.grid2}>
        <ServicesCard />
        <Card title="Utilizador atual">
          {me ? (
            <p>
              {me.name} · {me.roles.map((r) => r.label).join(", ")}
            </p>
          ) : (
            <p>—</p>
          )}
          <p className={c.loading}>
            Em desenvolvimento, o utilizador escolhe-se na barra superior. O início de sessão da
            empresa (OIDC) fica para a decisão D6.
          </p>
        </Card>
      </div>
    </Screen>
  );
}
