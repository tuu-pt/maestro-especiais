/** Screen F: empty until Phase 7, with its real preconditions. */

import { useActiveProject } from "../app/activeProject";
import { useProject } from "../api/queries";
import { EmptyState } from "../components/ui";
import { NoProject } from "./common";
import { Screen } from "./Screen";

export function EquipmentScreen() {
  const projectId = useActiveProject();
  const { data: project } = useProject(projectId);
  return (
    <Screen
      crumb={project ? `${project.code} · Equipamentos` : "Equipamentos"}
      title="Equipamentos e fichas técnicas"
      description="Equipamentos de referência do CTE comparados com as fichas técnicas dos fabricantes."
    >
      {!projectId ? (
        <NoProject screen="os equipamentos" />
      ) : (
        <EmptyState
          title="Ainda não há equipamentos de referência"
          next="Na Fase 7: parâmetro a parâmetro, exigido pelo CTE contra o valor da ficha (com a página), e alternativas da biblioteca quando um modelo não cumpre. Com “ou equivalente”, só se exigem os requisitos mínimos."
        >
          Os equipamentos vêm dos blocos do CTE e da biblioteca de equipamentos da TUU.
        </EmptyState>
      )}
    </Screen>
  );
}
