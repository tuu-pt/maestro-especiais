/** Screen G · Biblioteca de equipamentos: items proposed from the CTEs, datasheets, parameters. */

import { useId, useState } from "react";
import { useSearchParams } from "react-router";

import {
  useEquipment,
  useEquipmentActions,
  useEquipmentCategories,
  useEquipmentLibrary,
  useEquipmentParams,
  useMe,
} from "../api/queries";
import type { EquipmentDetail, EquipmentParam, ReviewStatus } from "../api/types";
import { DownloadButton } from "../components/DownloadButton";
import { Button, Buttons, Card, Chip, DataTable, EmptyState, ErrorNote, Pill, type Tone } from "../components/ui";
import { Loading } from "./common";
import { itemModel, sheetDate, VERDICT } from "../lib/equipment";
import { ChecksTable } from "./Equipment";
import s from "./Equipment.module.css";

const STATUS: Record<ReviewStatus, { label: string; tone: Tone }> = {
  proposed: { label: "Proposto", tone: "warn" },
  approved: { label: "Aprovado", tone: "ok" },
  rejected: { label: "Rejeitado", tone: "mute" },
};

function useIsCurator(): boolean {
  const { data: me } = useMe();
  return me?.roles.some((r) => r.id === "curador") ?? false;
}

export function EquipmentLibraryPanel() {
  const [params, setParams] = useSearchParams();
  const category = params.get("categoria") ?? "";
  const { data, isPending, error } = useEquipmentLibrary(category || undefined);
  const { data: categories } = useEquipmentCategories();
  const base = useId();
  const selected = params.get("equipamento");
  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };
  if (isPending) return <Loading />;
  if (error) return <ErrorNote>{error.message}</ErrorNote>;
  if (data.length === 0 && !category) {
    return (
      <EmptyState
        title="A biblioteca de equipamentos está vazia"
        next="Equipamentos de referência dos CTE (portinholas, quadros, luminárias L1…, módulos FV, inversores…), cada um com a ficha técnica do fabricante e os parâmetros revistos pelo curador."
      >
        A biblioteca é semeada a partir dos CTE de referência anonimizados (R1 e R2) com o comando make seed-library,
        corrido pela equipa.
      </EmptyState>
    );
  }
  const withSheet = data.filter((e) => e.datasheet).length;
  return (
    <div className={s.stack}>
      <p className={s.muted}>
        {`${data.length} equipamento${data.length === 1 ? "" : "s"} · ${withSheet} com ficha técnica. Os parâmetros lidos das fichas ficam “por rever” até o curador os confirmar; só os revistos decidem a verificação (EQP-01).`}
      </p>
      <div>
        <label htmlFor={`${base}-cat`} className={s.label}>
          Categoria
        </label>
        <select
          id={`${base}-cat`}
          className={s.input}
          value={category}
          onChange={(e) => set("categoria", e.target.value)}
        >
          <option value="">Todas</option>
          {categories?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.label}
            </option>
          ))}
        </select>
      </div>
      <DataTable caption="Biblioteca de equipamentos">
        <thead>
          <tr>
            <th scope="col">Equipamento</th>
            <th scope="col">Categoria</th>
            <th scope="col">Fabricante · modelo</th>
            <th scope="col">Ficha</th>
            <th scope="col">Parâmetros</th>
            <th scope="col">Estado</th>
          </tr>
        </thead>
        <tbody>
          {data.map((e) => (
            <tr key={e.id} className={e.id === selected ? s.on : undefined}>
              <td>
                <button
                  type="button"
                  className={s.rowButton}
                  aria-pressed={e.id === selected}
                  onClick={() => set("equipamento", e.id)}
                >
                  {e.code ? `${e.code} · ` : ""}
                  {e.name}
                </button>
                <div className={s.muted}>{e.projects.join(", ")}</div>
              </td>
              <td>{e.category_label}</td>
              <td>{itemModel(e)}</td>
              <td className={s.num}>
                {sheetDate(e.datasheet)}
                {e.datasheet?.old ? <div className={s.warn}>antiga</div> : null}
              </td>
              <td className={s.num}>
                {e.datasheet ? `${e.params_reviewed} revistos · ${e.params_to_review} por rever` : "—"}
              </td>
              <td>
                <Pill tone={STATUS[e.status].tone}>{STATUS[e.status].label}</Pill>
              </td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      {selected ? <EquipmentCard id={selected} /> : null}
    </div>
  );
}

function EquipmentCard({ id }: { id: string }) {
  const { data: e, isPending, error } = useEquipment(id);
  const curator = useIsCurator();
  if (isPending) return <Loading />;
  if (error) return <ErrorNote>{error.message}</ErrorNote>;
  const cte = e.params.filter((p) => p.origin === "cte");
  const sheetParams = e.params.filter((p) => p.origin === "datasheet" && p.datasheet_id === e.datasheet?.id);
  return (
    <Card className={s.detail}>
      <div aria-live="polite">
        <div className={s.detailHead}>
          <div>
            <h3 className={s.h3}>
              {e.code ? `${e.code} · ` : ""}
              {e.name}
            </h3>
            <p className={s.muted}>{`${e.category_label} · ${itemModel(e)}`}</p>
          </div>
          <div className={s.pills}>
            <Pill tone={STATUS[e.status].tone}>{STATUS[e.status].label}</Pill>
            <Pill tone={VERDICT[e.verdict].tone}>{VERDICT[e.verdict].label}</Pill>
          </div>
        </div>
        <div className={s.chips}>
          <Chip>{e.or_equivalent ? "ou equivalente" : "sem «ou equivalente»"}</Chip>
          {e.image ? <Chip>{`imagem do CTE de ${e.image.project}`}</Chip> : null}
        </div>
        <h4 className={s.h4}>No CTE</h4>
        <ul className={s.sources}>
          {e.sources.map((src, i) => (
            <li key={i}>
              <span className={s.muted}>{`${src.project} · `}</span>«{src.text}»
            </li>
          ))}
        </ul>
        {cte.length ? (
          <p className={s.muted}>{`Características que o CTE lista: ${cte.map((p) => `${p.label} ${p.shown}`).join("; ")}.`}</p>
        ) : null}
      </div>
      <h4 className={s.h4}>Fichas técnicas</h4>
      <Datasheets equipment={e} curator={curator} />
      {e.datasheet ? (
        <>
          <h4 className={s.h4}>Parâmetros da ficha atual</h4>
          <ParamsTable params={sheetParams} equipmentId={e.id} curator={curator} />
          {curator ? <AddParam equipmentId={e.id} /> : null}
        </>
      ) : null}
      <h4 className={s.h4}>Requisitos dos blocos do CTE</h4>
      <ChecksTable checks={e.checks} caption={`Requisitos do CTE contra a ficha de ${e.name}`} />
      {curator ? <Decision equipment={e} /> : <p className={s.muted}>Só um curador aprova, rejeita ou revê.</p>}
    </Card>
  );
}

function Datasheets({ equipment: e, curator }: { equipment: EquipmentDetail; curator: boolean }) {
  const actions = useEquipmentActions(e.id);
  const [date, setDate] = useState("");
  const base = useId();
  const current = e.datasheet;
  return (
    <div>
      {e.datasheets.length ? (
        <ul className={s.sources}>
          {e.datasheets.map((d) => (
            <li key={d.id}>
              <b>{d.file_name}</b>
              <span className={s.muted}>
                {` · ${d.status === "current" ? "atual" : "substituída"} · ${sheetDate(d)}${d.issue_date_text ? ` («${d.issue_date_text}»)` : ""} · ${d.pages} pág.`}
              </span>
              {d.old ? <span className={s.warn}> · antiga</span> : null}
              {d.warnings.map((w) => (
                <div key={w} className={s.muted}>
                  {w}
                </div>
              ))}
              <div>
                <DownloadButton path={`/equipment/datasheets/${d.id}/file`} filename={d.file_name}>
                  Abrir
                </DownloadButton>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className={s.muted}>Sem ficha técnica (EQP-03). Carregue o PDF do fabricante.</p>
      )}
      {curator ? (
        <div className={s.choose}>
          <label htmlFor={`${base}-file`} className={s.label}>
            Carregar ficha técnica (PDF)
          </label>
          <input
            id={`${base}-file`}
            type="file"
            accept="application/pdf"
            className={s.input}
            onChange={(ev) => {
              const file = ev.target.files?.[0];
              if (file) actions.upload.mutate(file);
              ev.target.value = "";
            }}
          />
          {actions.upload.isPending ? <p className={s.muted}>A ler a ficha…</p> : null}
          {actions.upload.error ? <ErrorNote>{actions.upload.error.message}</ErrorNote> : null}
          {current ? (
            <>
              <label htmlFor={`${base}-date`} className={s.label}>
                Data de emissão da ficha atual (AAAA-MM)
              </label>
              <input
                id={`${base}-date`}
                className={s.input}
                value={date}
                placeholder={current.issue_date?.slice(0, 7) ?? "2025-03"}
                onChange={(ev) => setDate(ev.target.value)}
              />
              {actions.issueDate.error ? <ErrorNote>{actions.issueDate.error.message}</ErrorNote> : null}
              <Buttons>
                <Button
                  small
                  disabled={!/^\d{4}-\d{2}(-\d{2})?$/.test(date) || actions.issueDate.isPending}
                  onClick={() => actions.issueDate.mutate({ datasheetId: current.id, date }, { onSuccess: () => setDate("") })}
                >
                  Guardar a data
                </Button>
              </Buttons>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function ParamsTable({ params, equipmentId, curator }: { params: EquipmentParam[]; equipmentId: string; curator: boolean }) {
  if (!params.length) return <p className={s.muted}>Nenhum parâmetro lido desta ficha: escreva-os à mão.</p>;
  return (
    <DataTable caption="Parâmetros da ficha técnica">
      <thead>
        <tr>
          <th scope="col">Parâmetro</th>
          <th scope="col">Valor</th>
          <th scope="col">Página</th>
          <th scope="col">Estado</th>
          {curator ? <th scope="col">Rever</th> : null}
        </tr>
      </thead>
      <tbody>
        {params.map((p) => (
          <ParamRow key={p.id} param={p} equipmentId={equipmentId} curator={curator} />
        ))}
      </tbody>
    </DataTable>
  );
}

function ParamRow({ param: p, equipmentId, curator }: { param: EquipmentParam; equipmentId: string; curator: boolean }) {
  const actions = useEquipmentActions(equipmentId);
  const [value, setValue] = useState("");
  const base = useId();
  return (
    <tr>
      <td>
        {p.label}
        <div className={s.muted} title={p.text}>{`«${p.text}»`}</div>
      </td>
      <td className={s.mono}>{p.shown}</td>
      <td className={s.num}>{p.page ?? "—"}</td>
      <td>
        <Pill tone={p.review_status === "reviewed" ? "ok" : "warn"}>
          {p.review_status === "reviewed" ? "Revisto" : "Por rever"}
        </Pill>
      </td>
      {curator ? (
        <td>
          <label htmlFor={`${base}-v`} className="visually-hidden">{`Corrigir ${p.label}`}</label>
          <input
            id={`${base}-v`}
            className={s.input}
            value={value}
            placeholder="corrigir (opcional)"
            onChange={(e) => setValue(e.target.value)}
          />
          {actions.reviewParam.error ? <ErrorNote>{actions.reviewParam.error.message}</ErrorNote> : null}
          <Button
            small
            disabled={actions.reviewParam.isPending}
            onClick={() => actions.reviewParam.mutate({ paramId: p.id, value }, { onSuccess: () => setValue("") })}
            aria-label={`${value ? "Corrigir e rever" : "Rever"} ${p.label}`}
          >
            {value ? "Corrigir e rever" : "Rever"}
          </Button>
        </td>
      ) : null}
    </tr>
  );
}

function AddParam({ equipmentId }: { equipmentId: string }) {
  const { data: params } = useEquipmentParams();
  const actions = useEquipmentActions(equipmentId);
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  const [page, setPage] = useState("");
  const base = useId();
  return (
    <div className={s.choose}>
      <h4 className={s.h4}>Acrescentar um parâmetro que a leitura não encontrou</h4>
      <label htmlFor={`${base}-name`} className={s.label}>
        Parâmetro
      </label>
      <select id={`${base}-name`} className={s.input} value={name} onChange={(e) => setName(e.target.value)}>
        <option value="">Escolher…</option>
        {params?.map((p) => (
          <option key={p.name} value={p.name}>
            {p.unit ? `${p.label} (${p.unit})` : p.label}
          </option>
        ))}
      </select>
      <label htmlFor={`${base}-value`} className={s.label}>
        Valor, como na ficha
      </label>
      <input id={`${base}-value`} className={s.input} value={value} onChange={(e) => setValue(e.target.value)} />
      <label htmlFor={`${base}-page`} className={s.label}>
        Página
      </label>
      <input
        id={`${base}-page`}
        className={s.input}
        inputMode="numeric"
        value={page}
        onChange={(e) => setPage(e.target.value.replace(/\D/g, ""))}
      />
      {actions.addParam.error ? <ErrorNote>{actions.addParam.error.message}</ErrorNote> : null}
      <Buttons>
        <Button
          small
          disabled={!name || !value.trim() || actions.addParam.isPending}
          onClick={() =>
            actions.addParam.mutate(
              { name, value, page: page ? Number(page) : undefined },
              {
                onSuccess: () => {
                  setName("");
                  setValue("");
                  setPage("");
                },
              },
            )
          }
        >
          Acrescentar (revisto)
        </Button>
      </Buttons>
    </div>
  );
}

function Decision({ equipment: e }: { equipment: EquipmentDetail }) {
  const actions = useEquipmentActions(e.id);
  const [note, setNote] = useState("");
  const base = useId();
  return (
    <div className={s.choose}>
      <label htmlFor={`${base}-note`} className={s.label}>
        Nota (opcional, fica registada)
      </label>
      <textarea id={`${base}-note`} rows={2} className={s.input} value={note} onChange={(ev) => setNote(ev.target.value)} />
      {actions.review.error ? <ErrorNote>{actions.review.error.message}</ErrorNote> : null}
      <Buttons>
        <Button
          variant="primary"
          small
          disabled={actions.review.isPending || e.status === "approved"}
          onClick={() => actions.review.mutate({ decision: "approved", note })}
          aria-label={`Aprovar ${e.name}`}
        >
          Aprovar
        </Button>
        <Button
          small
          disabled={actions.review.isPending || e.status === "rejected"}
          onClick={() => actions.review.mutate({ decision: "rejected", note })}
          aria-label={`Rejeitar ${e.name}`}
        >
          Rejeitar
        </Button>
      </Buttons>
    </div>
  );
}
