import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, postJson, request } from "./client";
import type {
  ApproveAllResult,
  AuditEntry,
  BlockDetail,
  BlockEdit,
  BlockPreview,
  BlockSummary,
  BomItem,
  Cables,
  DocSection,
  CircuitSheet,
  DevUser,
  Ficha,
  FichaValue,
  LlmSettings,
  KnowledgeKind,
  Project,
  ProjectFile,
  Approval,
  DocumentDiff,
  EquipmentCategory,
  EquipmentDetail,
  EquipmentParamInfo,
  EquipmentSlotDetail,
  EquipmentSummary,
  ProjectExport,
  ProjectDocument,
  ProjectEquipment,
  ProjectForm,
  ProjectIn,
  Regulation,
  RegulationStatus,
  Reviewed,
  Revision,
  SectionContent,
  SectionVersion,
  Typology,
  UploadResult,
  User,
  Validation,
  ValidationIssue,
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
  regulations: ["knowledge", "regulations"] as const,
  blocks: ["library", "blocks"] as const,
  block: (id: string) => ["library", "blocks", id] as const,
  blockPreview: (id: string, projectId: string) => ["library", "blocks", id, "preview", projectId] as const,
  blockHistory: (id: string) => ["library", "blocks", id, "history"] as const,
  documents: (projectId: string) => ["projects", projectId, "documents"] as const,
  document: (id: string) => ["documents", id] as const,
  versions: (sectionId: string) => ["sections", sectionId, "versions"] as const,
  validation: (projectId: string) => ["projects", projectId, "validation"] as const,
};

export const useMe = () =>
  useQuery({
    queryKey: keys.me,
    queryFn: () => request<User>("/me"),
    // not signed in: straight to the login page, no retry
    retry: (count, error) => !(error instanceof ApiError && error.status === 401) && count < 1,
  });

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

export function useAddManualValue(projectId: string) {
  const refresh = useRefreshProject();
  return useMutation({
    mutationFn: (body: { key: string; value: string; note: string }) =>
      postJson<FichaValue>(`/projects/${projectId}/ficha/values`, body),
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

export const useBlocks = () =>
  useQuery({ queryKey: keys.blocks, queryFn: () => request<BlockSummary[]>("/library/blocks") });

export const useBlock = (id: string | undefined) =>
  useQuery({
    queryKey: keys.block(id ?? ""),
    queryFn: () => request<BlockDetail>(`/library/blocks/${id}`),
    enabled: Boolean(id),
  });

export const useBlockPreview = (id: string | undefined, projectId: string | undefined) =>
  useQuery({
    queryKey: keys.blockPreview(id ?? "", projectId ?? ""),
    queryFn: () => request<BlockPreview>(`/library/blocks/${id}/preview?project_id=${projectId}`),
    enabled: Boolean(id && projectId),
  });

export const useBlockHistory = (id: string | undefined) =>
  useQuery({
    queryKey: keys.blockHistory(id ?? ""),
    queryFn: () => request<AuditEntry[]>(`/library/blocks/${id}/history`),
    enabled: Boolean(id),
  });

/** Approve, reject or edit a block (curator only; audited by the backend). */
export function useBlockAction(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (action: { decision: "approved" | "rejected"; note: string } | { edit: BlockEdit }) =>
      "edit" in action
        ? request<BlockSummary>(`/library/blocks/${id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(action.edit),
          })
        : postJson<BlockSummary>(`/library/blocks/${id}/review`, action),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["library"] });
      void client.invalidateQueries({ queryKey: keys.activity });
    },
  });
}

/** «Aprovar todas as propostas»: one decision of the curator, with a reason (audited). */
export function useApproveAllBlocks() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { reason: string; doc_type: "MDJ" | "CTE" | null }) =>
      postJson<ApproveAllResult>("/library/blocks/approve-all", body),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["library"] });
      void client.invalidateQueries({ queryKey: keys.activity });
    },
  });
}

export const useRegulations = () =>
  useQuery({ queryKey: keys.regulations, queryFn: () => request<Regulation[]>("/knowledge/regulations") });

function useRefreshKnowledge() {
  const client = useQueryClient();
  return () => {
    void client.invalidateQueries({ queryKey: ["knowledge"] });
    void client.invalidateQueries({ queryKey: keys.activity });
  };
}

/** Confirm (with the legal status) or reject a reference of the corpus (curator only). */
export function useReviewRegulation(id: string) {
  const refresh = useRefreshKnowledge();
  return useMutation({
    mutationFn: (body: { decision: "confirmed" | "rejected"; status?: RegulationStatus; edition?: string; note: string }) =>
      postJson<Regulation>(`/knowledge/regulations/${id}/review`, body),
    onSuccess: refresh,
  });
}

export function useCitable(id: string) {
  const refresh = useRefreshKnowledge();
  return useMutation({
    mutationFn: (body: { citable: boolean; note: string }) =>
      postJson<Regulation>(`/knowledge/regulations/${id}/citable`, body),
    onSuccess: refresh,
  });
}

// ---------------------------------------------------------------- documents and the editor

export const useForms = (projectId: string, enabled: boolean) =>
  useQuery({
    queryKey: ["projects", projectId, "forms"],
    queryFn: () => request<ProjectForm[]>(`/projects/${projectId}/forms`),
    enabled,
  });

export const useDocumentDiff = (documentId: string | undefined, base: number | null, against: number | null) =>
  useQuery({
    queryKey: ["documents", documentId, "diff", base, against],
    queryFn: () =>
      request<DocumentDiff>(
        `/documents/${documentId}/diff?base=${base}${against === null ? "" : `&against=${against}`}`,
      ),
    enabled: Boolean(documentId) && base !== null,
  });

// ---------------------------------------------------------------- review and export (Phase 6)

export const useApproval = (documentId: string | undefined) =>
  useQuery({
    queryKey: ["documents", documentId, "approval"],
    queryFn: () => request<Approval>(`/documents/${documentId}/approval`),
    enabled: Boolean(documentId),
  });

function patchJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function useApprovalActions(documentId: string, projectId: string) {
  const client = useQueryClient();
  const onSuccess = (data: Approval) => {
    client.setQueryData(["documents", documentId, "approval"], data);
    void client.invalidateQueries({ queryKey: keys.documents(projectId) });
    void client.invalidateQueries({ queryKey: keys.document(documentId) });
    void client.invalidateQueries({ queryKey: keys.audit(projectId) });
  };
  return {
    approve: useMutation({ mutationFn: () => postJson<Approval>(`/documents/${documentId}/approve`), onSuccess }),
    reopen: useMutation({
      mutationFn: (reason: string) => postJson<Approval>(`/documents/${documentId}/reopen`, { reason }),
      onSuccess,
    }),
    assign: useMutation({
      mutationFn: (body: { user_id: string; reason: string }) =>
        patchJson<Approval>(`/documents/${documentId}/responsible`, body),
      onSuccess,
    }),
    header: useMutation({
      mutationFn: (header_date: string | null) =>
        patchJson<Approval>(`/documents/${documentId}/header`, { header_date }),
      onSuccess,
    }),
  };
}

export const useExports = (projectId: string | undefined) =>
  useQuery({
    queryKey: ["projects", projectId, "exports"],
    queryFn: () => request<ProjectExport[]>(`/projects/${projectId}/exports`),
    enabled: Boolean(projectId),
    // follow an export while the worker builds it
    refetchInterval: (query) =>
      (query.state.data ?? []).some((e) => e.status === "queued" || e.status === "running") ? 1500 : false,
  });

export function useCreateExport(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { kind: "draft" | "official"; pdf: boolean }) =>
      postJson<ProjectExport>(`/projects/${projectId}/exports`, body),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["projects", projectId, "exports"] });
      void client.invalidateQueries({ queryKey: keys.audit(projectId) });
    },
  });
}

export const useDocuments = (projectId: string | undefined) =>
  useQuery({
    queryKey: keys.documents(projectId ?? ""),
    queryFn: () => request<ProjectDocument[]>(`/projects/${projectId}/documents`),
    enabled: Boolean(projectId),
  });

export const useDocument = (id: string | undefined) =>
  useQuery({
    queryKey: keys.document(id ?? ""),
    queryFn: () => request<ProjectDocument>(`/documents/${id}`),
    enabled: Boolean(id),
  });

export const useVersions = (sectionId: string | undefined) =>
  useQuery({
    queryKey: keys.versions(sectionId ?? ""),
    queryFn: () => request<SectionVersion[]>(`/sections/${sectionId}/versions`),
    enabled: Boolean(sectionId),
  });

export function useRefreshDocument(documentId: string | undefined, projectId: string | undefined) {
  const client = useQueryClient();
  return () => {
    if (documentId) void client.invalidateQueries({ queryKey: keys.document(documentId) });
    if (projectId) void client.invalidateQueries({ queryKey: keys.documents(projectId) });
    void client.invalidateQueries({ queryKey: ["sections"] });
    if (projectId) void client.invalidateQueries({ queryKey: keys.audit(projectId) });
  };
}

export function useAssemble(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (type: "MDJ" | "CTE") => postJson<ProjectDocument>(`/projects/${projectId}/documents`, { type }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.documents(projectId) });
      void client.invalidateQueries({ queryKey: keys.audit(projectId) });
    },
  });
}

function put<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** Every action of the editor on one section; each one refreshes the document. */
export function useSectionActions(section: DocSection | undefined, documentId: string, projectId: string) {
  const refresh = useRefreshDocument(documentId, projectId);
  const id = section?.id ?? "";
  const options = { onSuccess: refresh };
  return {
    generate: useMutation({ mutationFn: () => postJson(`/sections/${id}/generate`), ...options }),
    ask: useMutation({ mutationFn: (text: string) => postJson(`/sections/${id}/requests`, { text }), ...options }),
    unlock: useMutation({ mutationFn: (reason: string) => postJson(`/sections/${id}/unlock`, { reason }), ...options }),
    activation: useMutation({
      mutationFn: (args: { active: boolean; reason: string }) => postJson(`/sections/${id}/activation`, args),
      ...options,
    }),
    review: useMutation({ mutationFn: () => postJson(`/sections/${id}/review`, {}), ...options }),
    edit: useMutation({
      mutationFn: (args: { content: SectionContent; confirm_values: boolean }) =>
        put(`/sections/${id}/content`, args),
      ...options,
    }),
    decide: useMutation({
      mutationFn: (args: { versionId: string; decision: "accept" | "reject" }) =>
        postJson(`/versions/${args.versionId}/${args.decision}`, {}),
      ...options,
    }),
  };
}

export function useGenerateDocument(documentId: string, projectId: string) {
  const refresh = useRefreshDocument(documentId, projectId);
  return useMutation({
    mutationFn: () => postJson<{ queued: number }>(`/documents/${documentId}/generate`),
    onSuccess: refresh,
  });
}

// ---------------------------------------------------------------- validation (screen E)

export const useValidation = (projectId: string | undefined) =>
  useQuery({
    queryKey: keys.validation(projectId ?? ""),
    queryFn: () => request<Validation>(`/projects/${projectId}/validation`),
    enabled: Boolean(projectId),
    refetchInterval: (query) =>
      query.state.data?.current && ["queued", "running"].includes(query.state.data.current.status) ? 2000 : false,
  });

function useRefreshValidation(projectId: string) {
  const client = useQueryClient();
  return () => {
    void client.invalidateQueries({ queryKey: keys.validation(projectId) });
    void client.invalidateQueries({ queryKey: keys.projects });
    void client.invalidateQueries({ queryKey: keys.audit(projectId) });
  };
}

export { useRefreshValidation };

export function useRunValidation(projectId: string) {
  const refresh = useRefreshValidation(projectId);
  return useMutation({
    mutationFn: () => postJson(`/projects/${projectId}/validation`, { trigger: "full" }),
    onSuccess: refresh,
  });
}

export function useIgnoreIssue(projectId: string) {
  const refresh = useRefreshValidation(projectId);
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      postJson<ValidationIssue>(`/validation/issues/${id}/ignore`, { reason }),
    onSuccess: refresh,
  });
}

export function useReopenIssue(projectId: string) {
  const refresh = useRefreshValidation(projectId);
  return useMutation({
    mutationFn: (id: string) => postJson<ValidationIssue>(`/validation/issues/${id}/reopen`, {}),
    onSuccess: refresh,
  });
}

export function useRequestReview(projectId: string) {
  const refresh = useRefreshValidation(projectId);
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => postJson<{ sent: number }>(`/projects/${projectId}/review-request`, {}),
    onSuccess: () => {
      refresh();
      void client.invalidateQueries({ queryKey: keys.documents(projectId) });
    },
  });
}

// ---------------------------------------------------------------- equipment (Phase 7)

export const useProjectEquipment = (projectId: string | undefined) =>
  useQuery({
    queryKey: ["projects", projectId, "equipment"],
    queryFn: () => request<ProjectEquipment>(`/projects/${projectId}/equipment`),
    enabled: Boolean(projectId),
  });

export const useEquipmentSlot = (slotId: string | undefined) =>
  useQuery({
    queryKey: ["project-equipment", slotId],
    queryFn: () => request<EquipmentSlotDetail>(`/project-equipment/${slotId}`),
    enabled: Boolean(slotId),
  });

export function useChooseEquipment(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ slotId, equipmentId, reason }: { slotId: string; equipmentId: string; reason?: string }) =>
      put<EquipmentSlotDetail>(`/project-equipment/${slotId}`, { equipment_id: equipmentId, reason }),
    onSuccess: (data) => {
      client.setQueryData(["project-equipment", data.id], data);
      void client.invalidateQueries({ queryKey: ["projects", projectId, "equipment"] });
      void client.invalidateQueries({ queryKey: keys.audit(projectId) });
    },
  });
}

export const useEquipmentLibrary = (category?: string) =>
  useQuery({
    queryKey: ["library", "equipment", category ?? "all"],
    queryFn: () =>
      request<EquipmentSummary[]>(`/equipment${category ? `?category=${encodeURIComponent(category)}` : ""}`),
  });

export const useEquipmentCategories = () =>
  useQuery({ queryKey: ["library", "equipment-categories"], queryFn: () => request<EquipmentCategory[]>("/equipment/categories") });

export const useEquipmentParams = () =>
  useQuery({ queryKey: ["library", "equipment-params"], queryFn: () => request<EquipmentParamInfo[]>("/equipment/params") });

export const useEquipment = (id: string | undefined) =>
  useQuery({
    queryKey: ["library", "equipment", "item", id],
    queryFn: () => request<EquipmentDetail>(`/equipment/${id}`),
    enabled: Boolean(id),
  });

/** What the curator does with an item of the library; every action refreshes it and the lists. */
export function useEquipmentActions(id: string) {
  const client = useQueryClient();
  const onSuccess = (data: EquipmentDetail) => {
    client.setQueryData(["library", "equipment", "item", id], data);
    void client.invalidateQueries({ queryKey: ["library", "equipment"] });
    void client.invalidateQueries({ queryKey: ["projects"] });
    void client.invalidateQueries({ queryKey: keys.activity });
  };
  return {
    upload: useMutation({
      mutationFn: (file: File) => {
        const form = new FormData();
        form.append("file", file);
        return request<EquipmentDetail>(`/equipment/${id}/datasheets`, { method: "POST", body: form });
      },
      onSuccess,
    }),
    reviewParam: useMutation({
      mutationFn: ({ paramId, value, page }: { paramId: string; value?: string; page?: number }) =>
        patchJson<EquipmentDetail>(`/equipment/params/${paramId}`, { value: value || null, page: page ?? null }),
      onSuccess,
    }),
    addParam: useMutation({
      mutationFn: (body: { name: string; value: string; page?: number }) =>
        postJson<EquipmentDetail>(`/equipment/${id}/params`, body),
      onSuccess,
    }),
    issueDate: useMutation({
      mutationFn: ({ datasheetId, date }: { datasheetId: string; date: string }) =>
        patchJson<EquipmentDetail>(`/equipment/datasheets/${datasheetId}`, { issue_date: date }),
      onSuccess,
    }),
    review: useMutation({
      mutationFn: (body: { decision: "approved" | "rejected"; note: string }) =>
        postJson<EquipmentDetail>(`/equipment/${id}/review`, body),
      onSuccess,
    }),
  };
}

// ---------------------------------------------------------------- LLM providers (screen Definições)

export const useLlmSettings = () =>
  useQuery({ queryKey: ["settings", "llm"], queryFn: () => request<LlmSettings>("/settings/llm") });

export function useSetPrimaryLlm() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { primary: string; reason: string }) => put<LlmSettings>("/settings/llm", body),
    onSuccess: (data) => {
      client.setQueryData(["settings", "llm"], data);
      void client.invalidateQueries({ queryKey: keys.activity });
    },
  });
}

// ---------------------------------------------------------------- signing in (until D6)

export function useLogin() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) => postJson<User>("/auth/login", body),
    onSuccess: () => client.clear(),
  });
}

export function useLogout() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => postJson<{ ended: boolean }>("/auth/logout"),
    onSuccess: () => client.clear(),
  });
}
