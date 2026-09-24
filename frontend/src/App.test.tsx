import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import App from "./App";

function stubFetch(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status })),
  );
}

describe("App", () => {
  it("shows the product title in Portuguese", () => {
    stubFetch(200, { status: "ok", services: {} });
    render(<App />);
    expect(screen.getByRole("heading", { level: 1, name: "Maestro Especiais" })).toBeInTheDocument();
    expect(screen.getByText("A verificar…")).toBeInTheDocument();
  });

  it("lists every service as operational when health is ok", async () => {
    stubFetch(200, {
      status: "ok",
      services: {
        database: { status: "ok" },
        pgvector: { status: "ok" },
        redis: { status: "ok" },
        storage: { status: "ok" },
      },
    });
    render(<App />);
    expect(await screen.findAllByText("Operacional")).toHaveLength(4);
    expect(screen.getByText("Base de dados")).toBeInTheDocument();
    expect(screen.getByText("Armazenamento de ficheiros (S3)")).toBeInTheDocument();
  });

  it("flags the failing service when health is degraded (503)", async () => {
    stubFetch(503, {
      status: "degraded",
      services: {
        database: { status: "ok" },
        redis: { status: "error", detail: "ConnectionError" },
      },
    });
    render(<App />);
    expect(await screen.findByText("Com falhas")).toBeInTheDocument();
    expect(screen.getAllByText("Operacional")).toHaveLength(1);
  });

  it("says the API is unavailable when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<App />);
    expect(await screen.findByText("API indisponível")).toBeInTheDocument();
  });

  it("says the API is unavailable when the response is not a health payload", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("<html>502</html>", { status: 502 })),
    );
    render(<App />);
    expect(await screen.findByText("API indisponível")).toBeInTheDocument();
  });
});
