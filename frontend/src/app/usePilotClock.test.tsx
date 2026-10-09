import { fireEvent, render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BEAT_MS, IDLE_MS, usePilotClock } from "./usePilotClock";

const beacon = vi.hoisted(() => vi.fn(() => Promise.resolve()));
vi.mock("../api/client", async (original) => ({ ...(await original<object>()), beacon }));

function Page() {
  usePilotClock("p1");
  return (
    <div data-pilot-step="mdj">
      <button type="button">no texto</button>
      <section data-pilot-step="formularios">
        <button type="button">formulário</button>
      </section>
    </div>
  );
}

function renderAt(path: string) {
  const router = createMemoryRouter([{ path: "*", element: <Page /> }], { initialEntries: [path] });
  return render(<RouterProvider router={router} />);
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  vi.useRealTimers();
  beacon.mockClear();
});

describe("pilot clock", () => {
  it("beats every 30 s while someone works, with the part of the editor in use", () => {
    const { getByText } = renderAt("/projetos/p1/documentos?doc=MDJ");

    fireEvent.pointerDown(getByText("formulário"));
    vi.advanceTimersByTime(BEAT_MS);

    expect(beacon).toHaveBeenCalledWith("/projects/p1/pilot/heartbeat", {
      screen: "documentos",
      hint: "formularios",
      seconds: 30,
    });
  });

  it("stops counting after two minutes without interaction", () => {
    const { getByText } = renderAt("/projetos/p1/ficha");

    fireEvent.keyDown(getByText("no texto"));
    vi.advanceTimersByTime(IDLE_MS + BEAT_MS);
    const beats = beacon.mock.calls.length;
    vi.advanceTimersByTime(BEAT_MS * 4);

    expect(beats).toBeGreaterThan(0);
    expect(beacon.mock.calls.length).toBe(beats);
  });

  it("does not count before anyone interacts", () => {
    renderAt("/projetos/p1/validacao");
    vi.advanceTimersByTime(BEAT_MS * 3);
    expect(beacon).not.toHaveBeenCalled();
  });

  it("without a marker, the editor says which document from the address", () => {
    const { container } = renderAt("/projetos/p1/documentos?doc=CTE");

    fireEvent.pointerDown(container);
    vi.advanceTimersByTime(BEAT_MS);

    expect(beacon).toHaveBeenCalledWith("/projects/p1/pilot/heartbeat", {
      screen: "documentos",
      hint: "cte",
      seconds: 30,
    });
  });
});
