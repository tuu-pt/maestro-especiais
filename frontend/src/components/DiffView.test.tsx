import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { DiffView } from "./DiffView";

describe("DiffView", () => {
  it("marks what was inserted and removed, in words a screen reader also says", () => {
    render(
      <DiffView
        before="A entrada é monofásica."
        after="A entrada é trifásica."
        beforeLabel="rev. A"
        afterLabel="atual"
        label="Diferenças da secção"
      />,
    );
    const text = screen.getByRole("region", { name: "Diferenças da secção" });

    expect(text.querySelector("del")).toHaveTextContent("removido: monofásica");
    expect(text.querySelector("ins")).toHaveTextContent("inserido: trifásica");
    expect(screen.getByRole("status")).toHaveTextContent("2 alterações");
    expect(screen.getByText(/rev\. A/)).toBeInTheDocument();
  });

  it("moves the focus from change to change with the keyboard", async () => {
    render(<DiffView before="um dois três" after="um 2 três quatro" label="Diferenças" />);
    const changes = screen.getByRole("region", { name: "Diferenças" }).querySelectorAll("[data-change]");

    await userEvent.click(screen.getByRole("button", { name: "Alteração seguinte" }));
    expect(changes[0]).toHaveFocus();
    await userEvent.click(screen.getByRole("button", { name: "Alteração seguinte" }));
    expect(changes[1]).toHaveFocus();
    await userEvent.click(screen.getByRole("button", { name: "Alteração anterior" }));
    expect(changes[0]).toHaveFocus();
  });

  it("says when nothing changed", () => {
    render(<DiffView before="igual" after="igual" label="Diferenças" />);
    expect(screen.getByRole("status")).toHaveTextContent("Sem alterações");
    expect(screen.queryByRole("button", { name: "Alteração seguinte" })).not.toBeInTheDocument();
  });
});
