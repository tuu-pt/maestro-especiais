import { createBrowserRouter, type RouteObject } from "react-router";

import { DashboardScreen } from "../screens/Dashboard";
import { NotFoundScreen } from "../screens/NotFound";
import {
  EditorScreen,
  EquipmentScreen,
  KnowledgeScreen,
  ValidationScreen,
} from "../screens/Pending";
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
      ...scoped("documentos", <EditorScreen />),
      ...scoped("validacao", <ValidationScreen />),
      ...scoped("equipamentos", <EquipmentScreen />),
      { path: "conhecimento", element: <KnowledgeScreen /> },
      { path: "definicoes", element: <SettingsScreen /> },
      { path: "*", element: <NotFoundScreen /> },
    ],
  },
];

export const createRouter = () => createBrowserRouter(routes);
