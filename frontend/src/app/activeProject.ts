import { useEffect } from "react";
import { useParams } from "react-router";

const KEY = "maestro.activeProject";

function read(): string | undefined {
  try {
    return localStorage.getItem(KEY) ?? undefined;
  } catch {
    return undefined;
  }
}

/** The project in the URL, remembered so that the navigation can come back to it. */
export function useActiveProject(): string | undefined {
  const { projectId } = useParams();
  useEffect(() => {
    if (!projectId) return;
    try {
      localStorage.setItem(KEY, projectId);
    } catch {
      // private mode: nothing to remember
    }
  }, [projectId]);
  return projectId ?? read();
}

export function forgetActiveProject(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // nothing stored
  }
}
