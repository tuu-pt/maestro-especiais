/** Screen C: the ficha-base of the project, built only from the uploaded files. */

import { useState } from "react";

import { useActiveProject } from "../app/activeProject";
import {
  revealValue,
  useConfirmRevision,
  useFicha,
  useLinkBomItem,
  useLinkSheet,
  useMe,
  useProject,
  useResolveConflict,
} from "../api/queries";
import type {
  BomItem,
  Candidate,
  CircuitSheet,
  DrawingsCheck,
  Ficha,
  FichaValue,
  LinkKey,
} from "../api/types";
import {
  Button,
  ButtonLink,
  Buttons,
  Card,
  Collapsible,
  DataTable,
  EmptyState,
  ErrorNote,
  MaskedValue,
  OriginTag,
  Pill,
  Timeline,
} from "../components/ui";
import { formatDateTime, formatValue, ORIGIN_LABELS } from "../lib/format";
import { Loading, NoProject } from "./common";
import s from "./Ficha.module.css";
import { Screen } from "./Screen";

const detail = (file: string | null, ref: string | null) => [file, ref].filter(Boolean).join(" · ");

/** Lists of records (index, sheets) are shown in their own section: here only how many. */
function listSummary(v: FichaValue): string | null {
  if (!Array.isArray(v.value) || !v.value.some((x) => typeof x === "object" && x !== null)) return null;
  const n = v.value.length;
  if (v.key === "pd.indice") return `${n} folha${n === 1 ? "" : "s"} (ver o índice abaixo)`;
  if (v.key === "pd.folhas") return `${n} página${n === 1 ? "" : "s"} com carimbadura`;
  return `${n} registos`;
}

function Value({ value, revealed, onReveal }: { value: FichaValue; revealed?: unknown; onReveal: () => void }) {
  const shown = revealed !== undefined ? revealed : value.value;
  if (value.status === "conflict") return <Pill tone="warn">Conflito</Pill>;
  const summary = listSummary(value);
  const text = summary ?? `${formatValue(shown)}${value.unit && shown !== null ? ` ${value.unit}` : ""}`;
  return <MaskedValue masked={value.masked && revealed === undefined} value={text} onReveal={onReveal} />;
}

function Groups({ ficha }: { ficha: Ficha }) {
  const [revealed, setRevealed] = useState<Record<string, unknown>>({});
  const [error, setError] = useState<string | null>(null);
  const reveal = async (id: string) => {
    try {
      const value = await revealValue(id);
      setRevealed((r) => ({ ...r, [id]: value.value }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível mostrar o valor.");
    }
  };
  const groups = ficha.groups.filter((g) => g.values.length > 0);
  return (
    <>
      {error ? <ErrorNote>{error}</ErrorNote> : null}
      <div className={s.groups}>
        {groups.map((group) => (
          <Card key={group.name} title={group.name}>
            <dl className={s.kv}>
              {group.values.map((v) => (
                <div key={v.id}>
                  <dt>{v.label}</dt>
                  <dd>
                    <Value value={v} revealed={revealed[v.id]} onReveal={() => void reveal(v.id)} />
                    {v.status !== "conflict" ? (
                      <OriginTag source={v.source_type} detail={detail(v.source_file, v.source_ref)} />
                    ) : null}
                  </dd>
                </div>
              ))}
            </dl>
          </Card>
        ))}
      </div>
    </>
  );
}

// ---------------------------------------------------------------- conflicts

function candidateText(c: Candidate, unit: string | null): string {
  return `${formatValue(c.value)}${unit && c.value !== "•••" ? ` ${unit}` : ""}`;
}

type Open = { id: string; label: string; unit: string | null; candidates: Candidate[] };

function ConflictBox({ projectId, conflict, canResolve }: { projectId: string; conflict: Open; canResolve: boolean }) {
  const [choice, setChoice] = useState<number | "manual" | null>(null);
  const [manual, setManual] = useState("");
  const [note, setNote] = useState("");
  const resolve = useResolveConflict(projectId);
  const idBase = `conflict-${conflict.id}`;
  const submit = () => {
    if (choice === null) return;
    resolve.mutate({
      conflictId: conflict.id,
      candidate: choice === "manual" ? undefined : choice,
      manual: choice === "manual" ? manualValue(manual) : undefined,
      note,
    });
  };
  return (
    <section className={s.conflict} aria-labelledby={`${idBase}-title`}>
      <h3 id={`${idBase}-title`} className={s.conflictTitle}>
        {conflict.label}: as fontes não coincidem
      </h3>
      <p>O agente não escolhe por maioria nem pela data: é preciso uma pessoa confirmar.</p>
      <div className={s.pick} role="group" aria-label={`Candidatos para ${conflict.label}`}>
        {conflict.candidates.map((c, i) => (
          <button
            key={i}
            type="button"
            aria-pressed={choice === i}
            disabled={!canResolve}
            onClick={() => setChoice(i)}
          >
            <b>{candidateText(c, conflict.unit)}</b>
            <span>
              {ORIGIN_LABELS[c.source_type] ?? c.source_type} · {detail(c.source_file, c.source_ref)}
              {c.file_date ? ` · ${formatDateTime(c.file_date)}` : ""}
            </span>
          </button>
        ))}
      </div>
      {canResolve ? (
        <div className={s.resolve}>
          <label className={s.inline}>
            <input type="radio" checked={choice === "manual"} onChange={() => setChoice("manual")} /> Outro valor
          </label>
          {choice === "manual" ? (
            <input
              aria-label="Outro valor"
              value={manual}
              onChange={(e) => setManual(e.target.value)}
              className={s.input}
            />
          ) : null}
          <label htmlFor={`${idBase}-note`}>Justificação (fica registada)</label>
          <textarea
            id={`${idBase}-note`}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            className={s.input}
          />
          {resolve.error ? <ErrorNote>{resolve.error.message}</ErrorNote> : null}
          <Buttons>
            <Button
              variant="primary"
              onClick={submit}
              disabled={choice === null || note.trim().length < 3 || resolve.isPending}
            >
              Confirmar escolha
            </Button>
          </Buttons>
        </div>
      ) : (
        <p className={s.muted}>Só um técnico responsável pode resolver conflitos.</p>
      )}
    </section>
  );
}

/** A manual value keeps its type: numbers typed as "34,5" are sent as numbers. */
function manualValue(text: string): unknown {
  const trimmed = text.trim();
  const number = Number(trimmed.replace(/\s/g, "").replace(",", "."));
  return trimmed !== "" && Number.isFinite(number) && /^[\d\s.,-]+$/.test(trimmed) ? number : trimmed;
}

function valueConflicts(ficha: Ficha): Open[] {
  return ficha.groups
    .flatMap((g) => g.values)
    .filter((v) => v.conflict)
    .map((v) => ({ id: v.conflict!.id, label: v.label, unit: v.unit, candidates: v.conflict!.candidates }));
}

/** Conflicts of each circuit with its 09-Folha, grouped: one circuit can have several fields. */
function circuitConflicts(ficha: Ficha): { circuit: string; conflicts: Open[] }[] {
  return ficha.circuits
    .filter((c) => c.conflicts.length)
    .map((c) => ({
      circuit: `${c.origin} → ${c.destination}`,
      conflicts: c.conflicts.map((k) => ({
        id: k.id,
        label: `${c.origin} → ${c.destination} · ${k.label}`,
        unit: null,
        candidates: k.candidates,
      })),
    }));
}

function Conflicts({ ficha, projectId, canResolve }: { ficha: Ficha; projectId: string; canResolve: boolean }) {
  const values = valueConflicts(ficha);
  const circuits = circuitConflicts(ficha);
  const total = values.length + circuits.reduce((n, g) => n + g.conflicts.length, 0);
  if (!total) return null;
  return (
    <Collapsible title={`Conflitos por resolver (${total})`}>
      {values.map((c) => (
        <ConflictBox key={c.id} projectId={projectId} conflict={c} canResolve={canResolve} />
      ))}
      {circuits.map((g) => (
        <Collapsible
          key={g.circuit}
          level={3}
          defaultOpen={false}
          title={`${g.circuit}: difere da 09-Folha`}
          meta={<Pill tone="warn">{`${g.conflicts.length} campo${g.conflicts.length > 1 ? "s" : ""}`}</Pill>}
        >
          {g.conflicts.map((c) => (
            <ConflictBox key={c.id} projectId={projectId} conflict={c} canResolve={canResolve} />
          ))}
        </Collapsible>
      ))}
    </Collapsible>
  );
}

// ---------------------------------------------------------------- circuits and 09-Folhas

function Cell({ value, fail, label, conflict }: { value: string | null; fail: boolean; label: string; conflict?: boolean }) {
  return (
    <td className={fail ? s.fail : conflict ? s.conflictCell : s.num}>
      {formatValue(value)}
      {fail ? <span className="visually-hidden">{` (não cumpre ${label})`}</span> : null}
      {conflict ? <span className="visually-hidden"> (difere da 09-Folha)</span> : null}
    </td>
  );
}

const SHEET_FIELDS: [field: string, label: string, unit: string][] = [
  ["kva", "Potência", "kVA"],
  ["ib_a", "IB", "A"],
  ["in_a", "In", "A"],
  ["iz_a", "Iz", "A"],
  ["i2_a", "I2", "A"],
  ["iz145_a", "1,45·Iz", "A"],
  ["section_mm2", "Secção", "mm²"],
  ["length_m", "Comprimento", "m"],
  ["vd_section_pct", "QDT troço", "%"],
];

const sheetName = (sh: CircuitSheet) =>
  sh.origin_hint && sh.destination_hint ? `${sh.origin_hint}-${sh.destination_hint}` : (sh.source_file ?? "09-Folha");

function SheetDetail({ sheet }: { sheet: CircuitSheet }) {
  const text = SHEET_FIELDS.filter(([f]) => sheet.values[f])
    .map(([f, label, unit]) => `${label} ${formatValue(sheet.values[f]?.value)} ${unit}`)
    .join(" · ");
  return (
    <OriginTag
      source="calc_sheet"
      detail={`${sheet.source_file ?? "09-Folha"}${sheet.link_status === "manual" ? " (associada à mão)" : ""} · ${text}`}
    />
  );
}

function Circuits({ ficha }: { ficha: Ficha }) {
  const { circuits, cal01_note: note } = ficha;
  if (circuits.length === 0) {
    return (
      <EmptyState title="Sem troços" next="Os troços vêm da Tabela de Cálculo, uma linha por troço.">
        Ainda não foi lida nenhuma Tabela de Cálculo.
      </EmptyState>
    );
  }
  const sheetOf = (id: string) => ficha.circuit_sheets.find((sh) => sh.circuit_ids.includes(id));
  const fails = circuits.filter((c) => c.cal01.ib_in_iz === "fail" || c.cal01.i2_iz145 === "fail").length;
  return (
    <>
      <div className={s.circuitsHead}>
        <h2 className={s.h2}>Quadros e troços</h2>
        {fails > 0 ? (
          <Pill tone="warn">{`CAL-01: ${fails} troço${fails > 1 ? "s" : ""} a confirmar na folha`}</Pill>
        ) : (
          <Pill tone="ok">CAL-01: sem falhas nas comparações feitas</Pill>
        )}
      </div>
      <DataTable caption="Troços da Tabela de Cálculo">
        <thead>
          <tr>
            <th scope="col">Troço</th>
            <th scope="col">kVA</th>
            <th scope="col">IB (A)</th>
            <th scope="col">In (A)</th>
            <th scope="col">Iz (A)</th>
            <th scope="col">I2 (A)</th>
            <th scope="col">1,45·Iz (A)</th>
            <th scope="col">Cabo</th>
            <th scope="col">L (m)</th>
            <th scope="col">QDT (%)</th>
            <th scope="col">Origem</th>
            <th scope="col">09-Folha</th>
          </tr>
        </thead>
        <tbody>
          {circuits.map((c) => {
            const a = c.cal01.ib_in_iz === "fail";
            const b = c.cal01.i2_iz145 === "fail";
            const differs = new Set(c.conflicts.map((k) => k.field));
            const sheet = sheetOf(c.id);
            return (
              <tr key={c.id}>
                <th scope="row" className={s.rowHead}>
                  {c.origin} → {c.destination}
                  {c.section ? <span className={s.muted}>{c.section}</span> : null}
                </th>
                <Cell value={c.kva} fail={false} label="" conflict={differs.has("kva")} />
                <Cell value={c.ib_a} fail={a} label="IB ≤ In ≤ Iz" conflict={differs.has("ib_a")} />
                <Cell value={c.in_a} fail={a} label="IB ≤ In ≤ Iz" conflict={differs.has("in_a")} />
                <Cell value={c.iz_a} fail={a} label="IB ≤ In ≤ Iz" conflict={differs.has("iz_a")} />
                <Cell value={c.i2_a} fail={b} label="I2 ≤ 1,45·Iz" conflict={differs.has("i2_a")} />
                <Cell value={c.iz145_a} fail={b} label="I2 ≤ 1,45·Iz" conflict={differs.has("iz145_a")} />
                <td className={s.cable}>{c.cable_raw ?? "—"}</td>
                <Cell value={c.length_m} fail={false} label="" conflict={differs.has("length_m")} />
                <Cell value={c.vd_section_pct ?? c.vd_total_pct} fail={false} label="" conflict={differs.has("vd_section_pct")} />
                <td>
                  <OriginTag source="calc" detail={c.source_ref} />
                </td>
                <td>{sheet ? <SheetDetail sheet={sheet} /> : <span className={s.muted}>—</span>}</td>
              </tr>
            );
          })}
        </tbody>
      </DataTable>
      <p className={s.muted}>
        A CAL-01 compara valores que já estão na Tabela de Cálculo (IB ≤ In ≤ Iz e I2 ≤ 1,45·Iz) e não
        recalcula nada: um troço destacado pede confirmação na folha. As células sublinhadas diferem da
        09-Folha do troço e aparecem nos conflitos. {note}
      </p>
    </>
  );
}

function UnlinkedSheets({ ficha, projectId, canLink }: { ficha: Ficha; projectId: string; canLink: boolean }) {
  const unlinked = ficha.circuit_sheets.filter((sh) => sh.link_status === "unlinked");
  const link = useLinkSheet(projectId);
  const [chosen, setChosen] = useState<Record<string, string[]>>({});
  if (!unlinked.length) return null;
  return (
    <Card title={`09-Folhas por associar (${unlinked.length})`}>
      <p className={s.muted}>
        O nome do ficheiro não indica um único troço da Tabela de Cálculo. Escolha o troço (ou os troços iguais)
        a que a folha corresponde: os valores passam a ser comparados.
      </p>
      <ul className={s.sheets}>
        {unlinked.map((sh) => {
          const id = `sheet-${sh.id}`;
          return (
            <li key={sh.id}>
              <b>{sheetName(sh)}</b>
              <span className={s.muted}>{sh.source_file}</span>
              {canLink ? (
                <>
                  <label htmlFor={id}>Troço(s) da Tabela para {sheetName(sh)}</label>
                  <select
                    id={id}
                    multiple
                    size={Math.min(5, ficha.circuits.length)}
                    className={s.input}
                    value={chosen[sh.id] ?? []}
                    onChange={(e) =>
                      setChosen((c) => ({ ...c, [sh.id]: Array.from(e.target.selectedOptions, (o) => o.value) }))
                    }
                  >
                    {ficha.circuits.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.origin} → {c.destination}
                      </option>
                    ))}
                  </select>
                  <Buttons>
                    <Button
                      disabled={!(chosen[sh.id] ?? []).length || link.isPending}
                      onClick={() => link.mutate({ sheetId: sh.id, circuitIds: chosen[sh.id] ?? [] })}
                    >
                      Associar {sheetName(sh)}
                    </Button>
                  </Buttons>
                </>
              ) : (
                <span className={s.muted}>Só o redator ou o técnico responsável associam folhas.</span>
              )}
            </li>
          );
        })}
      </ul>
      {link.error ? <ErrorNote>{link.error.message}</ErrorNote> : null}
    </Card>
  );
}

// ---------------------------------------------------------------- drawings

function Drawings({ ficha }: { ficha: Ficha }) {
  const all = ficha.groups.flatMap((g) => g.values);
  const index = all.find((v) => v.key === "pd.indice");
  const check: DrawingsCheck | null = ficha.drawings_check;
  if (!index || !Array.isArray(index.value)) return null;
  const rows = index.value as { codigo: string; titulo: string; data: string | null; revisao: string | null }[];
  const missing = new Set(check?.missing_in_pdf ?? []);
  return (
    <Collapsible
      title="Índice das peças desenhadas"
      defaultOpen={!!check && !check.matches}
      meta={
        check ? (
          check.matches ? (
            <Pill tone="ok">Índice e PDF coincidem</Pill>
          ) : (
            <Pill tone="warn">Índice e PDF não coincidem</Pill>
          )
        ) : null
      }
    >
      {check && !check.matches ? (
        <p className={s.warnNote} role="note">
          {`O índice lista ${check.index_sheets} folha${check.index_sheets === 1 ? "" : "s"} e o PDF tem ${check.pages} página${check.pages === 1 ? "" : "s"}.`}
          {check.missing_in_pdf.length ? ` Sem página no PDF: ${check.missing_in_pdf.join(", ")}.` : ""}
          {check.not_in_index.length ? ` Fora do índice: ${check.not_in_index.join(", ")}.` : ""}
          {" A regra DES-01 sinaliza isto na validação."}
        </p>
      ) : null}
      <DataTable caption="Folhas do índice">
        <thead>
          <tr>
            <th scope="col">Código</th>
            <th scope="col">Título</th>
            <th scope="col">Data</th>
            <th scope="col">Rev.</th>
            <th scope="col">No PDF</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.codigo}>
              <th scope="row" className={s.rowHead}>
                {r.codigo}
              </th>
              <td>{r.titulo}</td>
              <td>{r.data ?? "—"}</td>
              <td>{r.revisao ?? "—"}</td>
              <td>{missing.has(r.codigo) ? <Pill tone="warn">Sem página</Pill> : <Pill tone="ok">Sim</Pill>}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
    </Collapsible>
  );
}

// ---------------------------------------------------------------- MQT / LPU

type Filter = "all" | "linked" | "unlinked";

function BomItems({ ficha, projectId, canLink }: { ficha: Ficha; projectId: string; canLink: boolean }) {
  const articles = ficha.bom_items.filter((i) => i.kind === "article");
  const unlinkedCount = articles.filter((i) => i.link_status === "unlinked").length;
  const [filter, setFilter] = useState<Filter>(unlinkedCount ? "unlinked" : "all");
  const link = useLinkBomItem(projectId);
  if (!articles.length) return null;
  const shown = articles.filter((i) =>
    filter === "all" ? true : filter === "linked" ? i.link_status !== "unlinked" : i.link_status === "unlinked",
  );
  const variant = articles[0]?.variant === "lpu" ? "LPU" : "MQT";
  const counts: [Filter, string, number][] = [
    ["unlinked", "Por associar", unlinkedCount],
    ["linked", "Associados", articles.length - unlinkedCount],
    ["all", "Todos", articles.length],
  ];
  return (
    <Collapsible
      title={`Artigos do ${variant}`}
      defaultOpen={false}
      meta={
        <Pill tone={unlinkedCount ? "mute" : "ok"}>
          {unlinkedCount ? `${unlinkedCount} de ${articles.length} por associar` : `${articles.length} associados`}
        </Pill>
      }
    >
      <div className={s.circuitsHead}>
        <div className={s.filters} role="group" aria-label="Filtrar artigos">
          {counts.map(([f, label, n]) => (
            <button key={f} type="button" aria-pressed={filter === f} onClick={() => setFilter(f)}>
              {label} ({n})
            </button>
          ))}
        </div>
      </div>
      <p className={s.muted}>
        Nesta fase os artigos só se associam por regras (quadros, portinhola, carregadores VE, módulos FV e
        luminárias pelo código). Os restantes associam-se aqui, à mão; cada associação fica registada.
      </p>
      <DataTable caption={`Tabela dos artigos do ${variant}`}>
        <thead>
          <tr>
            <th scope="col">Código</th>
            <th scope="col">Designação</th>
            <th scope="col">Un.</th>
            <th scope="col">Quant.</th>
            <th scope="col">Associação</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((i) => (
            <BomRow key={i.id} item={i} keys={ficha.bom_link_keys} canLink={canLink} onLink={(key) => link.mutate({ itemId: i.id, key })} />
          ))}
        </tbody>
      </DataTable>
      {link.error ? <ErrorNote>{link.error.message}</ErrorNote> : null}
    </Collapsible>
  );
}

function BomRow({ item, keys, canLink, onLink }: { item: BomItem; keys: LinkKey[]; canLink: boolean; onLink: (key: string | null) => void }) {
  const status =
    item.link_status === "rule" ? (
      <Pill tone="ok">{`${item.link_label} · por regra`}</Pill>
    ) : item.link_status === "manual" ? (
      <Pill tone="info">{`${item.link_label} · à mão`}</Pill>
    ) : (
      <Pill tone="mute">Por associar</Pill>
    );
  const label = `Associação do artigo ${item.code ?? ""} ${item.designation?.slice(0, 40) ?? ""}`.trim();
  return (
    <tr>
      <th scope="row" className={s.rowHead}>
        <abbr title={detail(item.source_file, item.source_ref)}>{item.code ?? "—"}</abbr>
      </th>
      <td className={s.designation}>{item.designation}</td>
      <td>{item.unit ?? "—"}</td>
      <td className={s.num}>{formatValue(item.quantity)}</td>
      <td>
        <div className={s.linkCell}>
          {status}
          {canLink ? (
            <select
              aria-label={label}
              className={s.select}
              value={item.link_key ?? ""}
              onChange={(e) => onLink(e.target.value || null)}
            >
              <option value="">Sem associação</option>
              {keys.map((k) => (
                <option key={k.key} value={k.key}>
                  {k.group} · {k.label}
                </option>
              ))}
            </select>
          ) : null}
        </div>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------- screen

export function FichaScreen() {
  const projectId = useActiveProject();
  const { data: project } = useProject(projectId);
  const { data: ficha, isLoading, error } = useFicha(projectId);
  const { data: me } = useMe();
  const confirm = useConfirmRevision(projectId ?? "");
  const isTecnico = me?.roles.some((r) => r.id === "tecnico") ?? false;
  const canLink = me?.roles.some((r) => r.id === "tecnico" || r.id === "redator") ?? false;

  if (!projectId) {
    return (
      <Screen title="Ficha do projeto">
        <NoProject screen="a ficha-base" />
      </Screen>
    );
  }
  const revision = ficha?.revision;
  const confirmReason = !revision
    ? "Ainda não há ficha-base."
    : revision.status !== "draft"
      ? "Esta revisão já está confirmada."
      : ficha && ficha.open_conflicts > 0
        ? "Resolva primeiro os conflitos."
        : !isTecnico
          ? "Só um técnico responsável pode confirmar."
          : null;

  return (
    <Screen
      crumb={project ? `${project.code} · ${project.name}` : "Projeto"}
      title={revision ? `Ficha-base · rev. ${revision.label}` : "Ficha do projeto"}
      description="Os dados principais do projeto num único sítio, com a origem de cada valor. É a fonte de verdade para redigir e comparar as peças."
      actions={<ButtonLink to={`/projetos/${projectId}/ficheiros`}>Carregar ficheiros</ButtonLink>}
    >
      {isLoading ? <Loading /> : null}
      {error ? <ErrorNote>Não foi possível carregar a ficha-base: {error.message}</ErrorNote> : null}
      {ficha && !revision ? (
        <EmptyState
          title="Ainda não há ficha-base"
          action={
            <ButtonLink to={`/projetos/${projectId}/ficheiros`} variant="primary">
              Carregar ficheiros
            </ButtonLink>
          }
          next="Cada valor vai mostrar a origem (ficheiro, folha e célula, linha ou página). Quando as fontes divergirem, o valor fica em aberto até uma pessoa o confirmar."
        >
          Carregue a ficha eletrotécnica e a Tabela de Cálculo para criar a ficha-base.
        </EmptyState>
      ) : null}
      {ficha && revision ? (
        <div className={s.main}>
          <div className={s.content}>
            <Conflicts ficha={ficha} projectId={projectId} canResolve={isTecnico} />
            <Groups ficha={ficha} />
            <Drawings ficha={ficha} />
            <Circuits ficha={ficha} />
            <UnlinkedSheets ficha={ficha} projectId={projectId} canLink={canLink} />
            <BomItems ficha={ficha} projectId={projectId} canLink={canLink} />
          </div>
          <aside className={s.side}>
            <Card title="Estado">
              {revision.status === "confirmed" ? (
                <Pill tone="ok">Confirmada</Pill>
              ) : ficha.open_conflicts > 0 ? (
                <Pill tone="warn">{`${ficha.open_conflicts} conflito${ficha.open_conflicts > 1 ? "s" : ""} por resolver`}</Pill>
              ) : (
                <Pill tone="info">Por confirmar</Pill>
              )}
              <Buttons>
                <Button
                  variant="dark"
                  disabled={!ficha.can_confirm || !isTecnico || confirm.isPending}
                  onClick={() => confirm.mutate(revision.id)}
                >
                  Confirmar revisão {revision.label}
                </Button>
              </Buttons>
              {confirmReason ? <p className={s.muted}>{confirmReason}</p> : null}
              {confirm.error ? <ErrorNote>{confirm.error.message}</ErrorNote> : null}
            </Card>
            <Card title="Revisões">
              <Timeline
                items={[...ficha.revisions].reverse().map((r) => ({
                  id: r.id,
                  time: formatDateTime(r.confirmed_at ?? r.created_at),
                  who: `rev. ${r.label}`,
                  what:
                    r.status === "confirmed"
                      ? "confirmada"
                      : r.status === "superseded"
                        ? "substituída"
                        : "em rascunho",
                  human: r.status === "confirmed",
                }))}
              />
            </Card>
          </aside>
        </div>
      ) : null}
    </Screen>
  );
}
