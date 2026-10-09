/**
 * The pilot's clock (Phase 8): while someone works on a project, the time of each step is sent to
 * the backend, which adds it up. A beat every 30 s, only with the tab visible and an interaction
 * (pointer, keyboard, scroll) in the last 2 minutes [A CONFIRMAR]. Inside the editor, the part in
 * use (MDJ, CTE, forms) comes from the closest `data-pilot-step` of the last interaction.
 */

import { useEffect, useRef } from "react";
import { useLocation } from "react-router";

import { beacon } from "../api/client";

export const BEAT_MS = 30_000;
export const IDLE_MS = 120_000;
const EVENTS = ["pointerdown", "keydown", "wheel", "scroll"] as const;

export function usePilotClock(projectId: string | undefined) {
  const { pathname, search } = useLocation();
  const last = useRef<{ at: number; hint: string | null }>({ at: 0, hint: null });

  useEffect(() => {
    const seen = (event: Event) => {
      const marked = event.target instanceof Element ? event.target.closest("[data-pilot-step]") : null;
      last.current = { at: Date.now(), hint: marked?.getAttribute("data-pilot-step") ?? null };
    };
    for (const name of EVENTS) window.addEventListener(name, seen, { capture: true, passive: true });
    return () => {
      for (const name of EVENTS) window.removeEventListener(name, seen, { capture: true });
    };
  }, []);

  useEffect(() => {
    last.current = { ...last.current, hint: null }; // a new screen: the old part no longer applies
  }, [pathname]);

  useEffect(() => {
    if (!projectId) return undefined;
    const timer = window.setInterval(() => {
      if (document.visibilityState !== "visible") return;
      if (Date.now() - last.current.at > IDLE_MS) return;
      const screen = pathname.split("/").filter(Boolean).pop() ?? "";
      const doc = new URLSearchParams(search).get("doc");
      const hint = last.current.hint ?? (doc ? doc.toLowerCase() : null);
      void beacon(`/projects/${projectId}/pilot/heartbeat`, { screen, hint, seconds: BEAT_MS / 1000 });
    }, BEAT_MS);
    return () => window.clearInterval(timer);
  }, [projectId, pathname, search]);
}
