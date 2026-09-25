/** Screens D, E and F: empty until later phases, with their real preconditions. */

import { useActiveProject } from "../app/activeProject";
import { useFicha, useFiles, useProject } from "../api/queries";
import { EmptyState } from "../components/ui";
import { Checklist, NoProject } from "./common";
import { Screen } from "./Screen";

function useReadiness(projectId: string | undefined) {
  const { data: ficha } = useFicha(projectId);
  const { data: files = [] } = useFiles(projectId);
  const confirmed = ficha?.revisions.some((r) => r.status === "confirmed") ?? false;
  return { confirmed, files };
}

export function EditorScreen() {
  const projectId = useActiveProject();
  const { data: project } = useProject(projectId);
  const { confirmed } = useReadiness(projectId);
  return (
    <Screen
      crumb={project ? `${project.code} · Documentos` : "Documentos"}
      title="Editor assistido"
      description="O MDJ e o CTE são montados secção a secção a partir da ficha-base confirmada, com a origem de cada frase."
    >
      {!projectId ? (
        <NoProject screen="os documentos" />
      ) : (
        <EmptyState
          title="Ainda não há documentos"
          action={
            <Checklist
              items={[
                { done: confirmed, text: "Ficha-base confirmada por um técnico responsável" },
                { done: false, text: "Biblioteca de blocos aprovada pelo curador (Fase 3)" },
                { done: false, text: "Montagem e redação dos blocos (Fase 4)" },
              ]}
            />
          }
          next="Aqui vai aparecer cada secção com o seu estado (por fazer, gerada, revista), o modo do bloco (fixo, paramétrico ou adaptativo) e as fontes usadas."
        >
          Os documentos só podem ser montados depois de a ficha-base estar confirmada.
        </EmptyState>
      )}
    </Screen>
  );
}

export function ValidationScreen() {
  const projectId = useActiveProject();
  const { data: project } = useProject(projectId);
  const { confirmed } = useReadiness(projectId);
  return (
    <Screen
      crumb={project ? `${project.code} · Validação` : "Validação"}
      title="Validação"
      description="Verificação cruzada de todas as peças do projeto, com a ficha-base como referência."
    >
      {!projectId ? (
        <NoProject screen="a validação" />
      ) : (
        <EmptyState
          title="A validação fica disponível quando houver ficha-base confirmada e peças do projeto"
          action={
            <Checklist
              items={[
                { done: confirmed, text: "Ficha-base confirmada" },
                { done: false, text: "MDJ e CTE montados (Fase 4)" },
              ]}
            />
          }
          next="Vão correr as regras da secção 9 da SPEC (referências, coerência, tipologia, peças desenhadas, cálculo, contratação, conteúdo e fichas técnicas) e a matriz de coerência do projeto. As verificações da CAL-01 sobre a Tabela de Cálculo já aparecem na ficha do projeto."
        >
          Cada alerta vai mostrar o que foi encontrado, a evidência e a leitura provável. Nenhuma
          correção é aplicada sem uma ação humana.
        </EmptyState>
      )}
    </Screen>
  );
}

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
