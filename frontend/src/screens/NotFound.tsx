import { ButtonLink, EmptyState } from "../components/ui";
import { Screen } from "./Screen";

export function NotFoundScreen() {
  return (
    <Screen title="Página não encontrada">
      <EmptyState title="Este endereço não existe" action={<ButtonLink to="/">Ir para o painel</ButtonLink>} />
    </Screen>
  );
}
