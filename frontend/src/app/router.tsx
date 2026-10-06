import { createBrowserRouter, type RouteObject } from "react-router";

import { DashboardScreen } from "../screens/Dashboard";
import { FichaScreen } from "../screens/Ficha";
import { NewProjectScreen, ProjectFilesScreen } from "../screens/NewProject";
import { NotFoundScreen } from "../screens/NotFound";
import { KnowledgeScreen } from "../screens/Knowledge";
import { EditorScreen } from "../screens/Editor";
import { EquipmentScreen } from "../screens/Equipment";
import { ReviewScreen } from "../screens/Review";
import { ValidationScreen } from "../screens/Validation";
import { SettingsScreen } from "../screens/Settings";
import AppShell from "./AppShell";

/** Project screens exist with and without a project in the URL (then they ask for one). */
const scoped = (path: string, element: JSX.Element): RouteObject[] => [
  { path: `projetos/:projectId/${path}`, element },
  { path, element },
];

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <DashboardScreen /> },
      { path: "projetos/novo", element: <NewProjectScreen /> },
      { path: "projetos/:projectId/ficheiros", element: <ProjectFilesScreen /> },
      ...scoped("ficha", <FichaScreen />),
      ...scoped("documentos", <EditorScreen />),
      ...scoped("validacao", <ValidationScreen />),
      ...scoped("equipamentos", <EquipmentScreen />),
      ...scoped("revisao", <ReviewScreen />),
      { path: "conhecimento", element: <KnowledgeScreen /> },
      { path: "definicoes", element: <SettingsScreen /> },
      { path: "*", element: <NotFoundScreen /> },
    ],
  },
];

export const createRouter = () => createBrowserRouter(routes);
