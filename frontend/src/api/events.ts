import { useEffect, useRef } from "react";

import { authHeaders } from "./client";
import type { ProjectEvent } from "./types";

/**
 * Parse a text/event-stream body. EventSource cannot send the X-Dev-User header, so the
 * stream is read with fetch.
 */
export async function readEvents(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: ProjectEvent) => void,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const data = block
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      if (data) {
        try {
          onEvent(JSON.parse(data) as ProjectEvent);
        } catch {
          // keep-alive or malformed message: ignore it
        }
      }
      boundary = buffer.indexOf("\n\n");
    }
  }
}

/** Follow the progress of a project (ingestion, drafting) while the component is mounted. */
export function useProjectEvents(
  projectId: string | undefined,
  onEvent: (event: ProjectEvent) => void,
): void {
  const handler = useRef(onEvent);
  useEffect(() => {
    handler.current = onEvent;
  });
  useEffect(() => {
    if (!projectId) return;
    const controller = new AbortController();
    fetch(`/api/projects/${projectId}/events`, {
      headers: { Accept: "text/event-stream", ...authHeaders() },
      signal: controller.signal,
    })
      .then((response) => {
        if (response.ok && response.body) {
          return readEvents(response.body, (event) => handler.current(event));
        }
        return undefined;
      })
      .catch(() => undefined); // aborted or offline: the lists still refresh on their own
    return () => controller.abort();
  }, [projectId]);
}
