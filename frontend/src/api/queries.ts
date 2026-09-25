import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, postJson, request } from "./client";
import type {
  AuditEntry,
  BomItem,
  Cables,
  CircuitSheet,
  DevUser,
  Ficha,
  FichaValue,
  KnowledgeKind,
  Project,
  ProjectFile,
  ProjectIn,
  Reviewed,
  Revision,
  Typology,
  UploadResult,
  User,
} from "./types";

export const keys = {
  me: ["me"] as const,
  devUsers: ["dev-users"] as const,
  projects: ["projects"] as const,
  project: (id: string) => ["projects", id] as const,
  files: (id: string) => ["projects", id, "files"] as const,
  ficha: (id: string) => ["projects", id, "ficha"] as const,
  audit: (id: string) => ["projects", id, "audit"] as const,
  activity: ["activity"] as const,
  cables: ["knowledge", "cables"] as const,
  typologies: ["knowledge", "typologies"] as const,
};

export const useMe = () => useQuery({ queryKey: keys.me, queryFn: () => request<User>("/me") });

export const useDevUsers = () =>
  useQuery({
    queryKey: keys.devUsers,
    queryFn: async () => {
      try {
        return await request<DevUser[]>("/dev/users");
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return [];
        throw error;
      }
    },
    staleTime: Infinity,
  });

export const useProjects = () =>
  useQuery({ queryKey: keys.projects, queryFn: () => request<Project[]>("/projects") });

export const useProject = (id: string | undefined) =>
  useQuery({
    queryKey: keys.project(id ?? ""),
    queryFn: () => request<Project>(`/projects/${id}`),
    enabled: Boolean(id),
  });

export const useFiles = (id: string | undefined) =>
  useQuery({
    queryKey: keys.files(id ?? ""),
    queryFn: () => request<ProjectFile[]>(`/projects/${id}/files`),
    enabled: Boolean(id),
  });

export const useFicha = (id: string | undefined) =>
  useQuery({
    queryKey: keys.ficha(id ?? ""),
    queryFn: () => request<Ficha>(`/projects/${id}/ficha`),
    enabled: Boolean(id),
  });

export const useAudit = (id: string | undefined) =>
  useQuery({
    queryKey: keys.audit(id ?? ""),
    queryFn: () => request<AuditEntry[]>(`/projects/${id}/audit`),
    enabled: Boolean(id),
  });

export const useActivity = () =>
  useQuery({ queryKey: keys.activity, queryFn: () => request<AuditEntry[]>("/activity?limit=12") });

export function useCreateProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: ProjectIn) => postJson<Project>("/projects", body),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.projects }),
  });
}

export async function uploadFile(projectId: string, file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  return request<UploadResult>(`/projects/${projectId}/files`, { method: "POST", body: form });
}

/** Refresh everything that depends on a project's files and ficha-base. */
export function useRefreshProject() {
  const client = useQueryClient();
  return (projectId: string) => {
    for (const key of [keys.files(projectId), keys.ficha(projectId), keys.audit(projectId)]) {
      void client.invalidateQueries({ queryKey: key });
    }
    void client.invalidateQueries({ queryKey: keys.projects });
    void client.invalidateQueries({ queryKey: keys.activity });
  };
}

export function useResolveConflict(projectId: string) {
  const refresh = useRefreshProject();
  return useMutation({
    mutationFn: (args: { conflictId: string; candidate?: number; manual?: unknown; note: string }) =>
      postJson<FichaValue>(`/ficha/conflicts/${args.conflictId}/resolve`, {
        candidate: args.candidate ?? null,
        manual_value: args.manual ?? null,
        note: args.note,
      }),
    onSuccess: () => refresh(projectId),
  });
}

export function useConfirmRevision(projectId: string) {
  const refresh = useRefreshProject();
  return useMutation({
    mutationFn: (revisionId: string) => postJson<Revision>(`/ficha/revisions/${revisionId}/confirm`),
    onSuccess: () => refresh(projectId),
  });
}

export function useLinkSheet(projectId: string) {
  const refresh = useRefreshProject();
  return useMutation({
    mutationFn: (args: { sheetId: string; circuitIds: string[] }) =>
      postJson<CircuitSheet>(`/circuit-sheets/${args.sheetId}/link`, { circuit_ids: args.circuitIds }),
    onSuccess: () => refresh(projectId),
  });
}

export function useLinkBomItem(projectId: string) {
  const refresh = useRefreshProject();
  return useMutation({
    mutationFn: (args: { itemId: string; key: string | null }) =>
      postJson<BomItem>(`/bom-items/${args.itemId}/link`, { key: args.key }),
    onSuccess: () => refresh(projectId),
  });
}

export const revealValue = (valueId: string) =>
  postJson<FichaValue>(`/ficha/values/${valueId}/reveal`);

export const useCables = () =>
  useQuery({ queryKey: keys.cables, queryFn: () => request<Cables>("/knowledge/cables") });

export const useTypologies = () =>
  useQuery({ queryKey: keys.typologies, queryFn: () => request<Typology[]>("/knowledge/typologies") });

/** A curator's decision on something of the knowledge base (audited by the backend). */
export function useReview() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (args: { kind: KnowledgeKind; id: string; decision: "approved" | "rejected"; note: string }) =>
      postJson<Reviewed>(`/knowledge/${args.kind}/${args.id}/review`, { decision: args.decision, note: args.note }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["knowledge"] });
      void client.invalidateQueries({ queryKey: keys.activity });
    },
  });
}
