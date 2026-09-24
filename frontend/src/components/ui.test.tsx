import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { EmptyState, MaskedValue, OriginTag, Pill, StatusDot, Timeline } from "./ui";

describe("base components", () => {
  it("OriginTag names the origin and gives the detail on hover and to screen readers", () => {
    render(<OriginTag source="ficha_eletrotecnica" detail="FE.xlsm · Ficha Eletrotecnica!R29" />);
    const tag = screen.getByText("FICHA ELE");
    expect(tag).toHaveAttribute("title", "FE.xlsm · Ficha Eletrotecnica!R29");
    expect(tag).toHaveAccessibleName("FICHA ELE: FE.xlsm · Ficha Eletrotecnica!R29");
    expect(tag).toHaveAttribute("tabindex", "0");
  });

  it.each([
    ["calc", "CÁLCULO"],
    ["mqt", "MQT"],
    ["drawing", "DES"],
    ["manual", "MANUAL"],
  ] as const)("OriginTag %s is labelled %s", (source, label) => {
    render(<OriginTag source={source} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("MaskedValue hides personal data until asked", async () => {
    const onReveal = vi.fn();
    const { rerender } = render(<MaskedValue masked value="Nome real" onReveal={onReveal} />);
    expect(screen.queryByText("Nome real")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Dado pessoal mascarado")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Mostrar" }));
    expect(onReveal).toHaveBeenCalledOnce();

    rerender(<MaskedValue masked={false} value="Nome real" onReveal={onReveal} />);
    expect(screen.getByText("Nome real")).toBeInTheDocument();
  });

  it("EmptyState explains what is missing and offers the next action", () => {
    render(
      <MemoryRouter>
        <EmptyState title="Ainda não há projetos" action={<button type="button">Criar projeto</button>} next="Depois…">
          Tudo vem dos documentos.
        </EmptyState>
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "Ainda não há projetos" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Criar projeto" })).toBeInTheDocument();
    expect(screen.getByText("Depois…")).toBeInTheDocument();
  });

  it("Pill, StatusDot and Timeline render their content", () => {
    render(
      <>
        <Pill tone="warn">1 conflito</Pill>
        <StatusDot status="generated" label="Gerada, por rever" />
        <Timeline items={[{ id: "1", time: "09:15", who: "Sistema", what: "leu a ficha", human: false }]} />
      </>,
    );
    expect(screen.getByText("1 conflito")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Gerada, por rever" })).toBeInTheDocument();
    expect(screen.getByText("leu a ficha")).toBeInTheDocument();
  });
});
