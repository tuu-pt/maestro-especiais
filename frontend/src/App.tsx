import { useEffect, useState } from "react";

import { fetchHealth, type HealthResponse } from "./api/health";
import styles from "./App.module.css";

const SERVICE_LABELS: Record<string, string> = {
  database: "Base de dados",
  pgvector: "Pesquisa vetorial (pgvector)",
  redis: "Fila de trabalhos (Redis)",
  storage: "Armazenamento de ficheiros (S3)",
};

type HealthState =
  | { kind: "loading" }
  | { kind: "loaded"; health: HealthResponse }
  | { kind: "unavailable" };

export default function App() {
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
    <>
      <header className={styles.band}>
        <div className={styles.logo}>
          <i aria-hidden="true" />
          TUU <span>Building Design Management</span>
        </div>
      </header>
      <main className={styles.main}>
        <p className={styles.eyebrow}>Agente de IA · Instalações Elétricas</p>
        <h1 className={styles.title}>Maestro Especiais</h1>
        <p className={styles.lead}>
          Montagem, redação e validação do processo de projeto de instalações elétricas: MDJ, CTE,
          mapa de quantidades e formulários de licenciamento.
        </p>
        <section className={styles.card} aria-labelledby="health-title">
          <h2 id="health-title" className={styles.cardTitle}>
            Estado dos serviços
          </h2>
          <HealthView state={state} />
        </section>
      </main>
    </>
  );
}

function HealthView({ state }: { state: HealthState }) {
  if (state.kind === "loading") {
    return <p className={styles.note}>A verificar…</p>;
  }
  if (state.kind === "unavailable") {
    return (
      <p className={styles.note}>
        <span className={`${styles.pill} ${styles.crit}`}>API indisponível</span>
      </p>
    );
  }
  return (
    <ul className={styles.list}>
      {Object.entries(state.health.services).map(([name, service]) => (
        <li key={name} className={styles.row}>
          <span>{SERVICE_LABELS[name] ?? name}</span>
          {service.status === "ok" ? (
            <span className={`${styles.pill} ${styles.ok}`}>Operacional</span>
          ) : (
            <span className={`${styles.pill} ${styles.crit}`}>Com falhas</span>
          )}
        </li>
      ))}
    </ul>
  );
}
