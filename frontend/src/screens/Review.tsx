/** Screen H: review and export. The audit log is real; diff and export arrive in Phase 6. */

import { useActiveProject } from "../app/activeProject";
import { useAudit, useDocuments, useFicha, useProject } from "../api/queries";
import { Button, Buttons, Card, EmptyState, Timeline } from "../components/ui";
import { formatDateTime } from "../lib/format";
import { Checklist, Loading, NoProject } from "./common";
import c from "./common.module.css";
import { Screen } from "./Screen";

export function ReviewScreen() {
  const projectId = useActiveProject();
  const { data: project } = useProject(projectId);
  const { data: ficha } = useFicha(projectId);
  const { data: audit, isLoading } = useAudit(projectId);
  const { data: documents = [] } = useDocuments(projectId);
  const confirmed = ficha?.revisions.some((r) => r.status === "confirmed") ?? false;
  const validation = project?.validation;
  const critical = validation?.open_critical ?? 0;
  const validated = Boolean(validation?.finished_at);
  const sections = documents.reduce((n, d) => n + (d.counts.sections ?? 0), 0);
  const reviewed = documents.reduce((n, d) => n + (d.counts.reviewed ?? 0), 0);

  return (
    <Screen
      crumb={project ? `${project.code} · Revisão` : "Revisão"}
      title="Revisão e exportação"
      description="O técnico vê o que mudou, aprova e exporta o conjunto do projeto no modelo TUU. Fica tudo registado."
    >
      {!projectId ? (
        <NoProject screen="a revisão" />
      ) : (
        <>
          <div className={c.grid2}>
            <Card title="Diferenças">
              <EmptyState
                title="Ainda não há propostas para rever"
                next="Na Fase 6: a proposta do agente lado a lado com a edição do técnico."
              />
            </Card>
            <Card title="Aprovação">
              <Checklist
                items={[
                  { done: confirmed, text: "Ficha-base confirmada" },
                  {
                    done: sections > 0 && reviewed === sections,
                    text: sections
                      ? `Todas as secções revistas (${reviewed} de ${sections})`
                      : "Todas as secções revistas (ainda não há documentos)",
                  },
                  {
                    done: validated && critical === 0,
                    text: !validated
                      ? "Validação sem alertas críticos (ainda não corrida)"
                      : critical
                        ? `Validação sem alertas críticos (${critical} abertos)`
                        : "Validação sem alertas críticos",
                  },
                ]}
              />
              <Buttons>
                <Button variant="primary" disabled title="Só fica ativo com todas as condições cumpridas">
                  Aprovar
                </Button>
              </Buttons>
            </Card>
            <Card title="Exportar">
              <Buttons>
                <Button disabled>MDJ e CTE (.docx)</Button>
                <Button disabled>Ficha eletrotécnica (.xlsm)</Button>
                <Button disabled>Identificação e termo (.docx)</Button>
              </Buttons>
              <p className={c.loading}>
                A exportação chega na Fase 6. Os formulários saem sempre sem data nem assinatura.
              </p>
            </Card>
          </div>
          <Card title="Registo de auditoria">
            {isLoading ? <Loading /> : null}
            {audit && audit.length === 0 ? <p className={c.loading}>Ainda não há registos.</p> : null}
            {audit && audit.length > 0 ? (
              <Timeline
                items={audit.map((e) => ({
                  id: e.id,
                  time: formatDateTime(e.at),
                  who: e.actor_name,
                  what: e.description,
                  human: e.actor_type === "user",
                }))}
              />
            ) : null}
          </Card>
        </>
      )}
    </Screen>
  );
}
