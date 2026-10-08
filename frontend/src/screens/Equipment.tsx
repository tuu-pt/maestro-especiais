/** Screen F · Equipamentos (SPEC 10.F): the reference equipment of the CTE against the datasheets. */

import { useId, useState } from "react";
import { useSearchParams } from "react-router";

import { useActiveProject } from "../app/activeProject";
import {
  useChooseEquipment,
  useEquipmentLibrary,
  useEquipmentSlot,
  useMe,
  useProject,
  useProjectEquipment,
} from "../api/queries";
import type { EquipmentCheck, EquipmentItem, EquipmentSlot, EquipmentVerdict } from "../api/types";
import { DownloadButton } from "../components/DownloadButton";
import {
  Button,
  ButtonLink,
  Buttons,
  Card,
  Chip,
  DataTable,
  EmptyState,
  ErrorNote,
  Pill,
} from "../components/ui";
import { itemModel, OPERATOR, RESULT, sheetDate, VERDICT } from "../lib/equipment";
import { formatValue } from "../lib/format";
import { Loading, NoProject } from "./common";
import s from "./Equipment.module.css";
import { Screen } from "./Screen";

/** The pill of a row: the first parameter that fails says why (e.g. "IP44 < IP55"). */
function verdictPill(slot: { verdict: EquipmentVerdict; checks: EquipmentCheck[]; item: EquipmentItem | null }) {
  const failing = slot.checks.find((c) => c.result === "fails");
  if (failing && failing.offered) {
    return <Pill tone="crit">{`${failing.offered} < ${failing.required}`}</Pill>;
  }
  if (slot.verdict !== "no_datasheet" && slot.item?.datasheet?.old) {
    return <Pill tone="warn">Ficha antiga</Pill>;
  }
  return <Pill tone={VERDICT[slot.verdict].tone}>{VERDICT[slot.verdict].label}</Pill>;
}

export function EquipmentScreen() {
  const projectId = useActiveProject();
  const { data: project } = useProject(projectId);
  return (
    <Screen
      crumb={project ? `${project.code} · Equipamentos` : "Equipamentos"}
      title="Equipamentos e fichas técnicas"
      description="Cada equipamento de referência do CTE é comparado, parâmetro a parâmetro, com a ficha técnica do fabricante. Com “ou equivalente”, só se exigem os requisitos mínimos, nunca a marca."
    >
      {!projectId ? <NoProject screen="os equipamentos" /> : <ProjectEquipmentView projectId={projectId} />}
    </Screen>
  );
}

function ProjectEquipmentView({ projectId }: { projectId: string }) {
  const { data, isPending, error } = useProjectEquipment(projectId);
  const [params, setParams] = useSearchParams();
  if (isPending) return <Loading />;
  if (error) return <ErrorNote>{error.message}</ErrorNote>;
  if (!data.document_id) {
    return (
      <EmptyState
        title="O CTE ainda não foi montado"
        action={
          <Buttons>
            <ButtonLink to={`/projetos/${projectId}/documentos`} variant="primary">
              Montar o CTE
            </ButtonLink>
          </Buttons>
        }
        next="Depois de montado, cada linha do CTE que nomeia um equipamento de referência aparece aqui, com a quantidade do mapa de quantidades, a ficha técnica e a verificação."
      >
        Os equipamentos vêm dos blocos do CTE e da biblioteca de equipamentos da TUU.
      </EmptyState>
    );
  }
  if (data.slots.length === 0) {
    return (
      <EmptyState
        title="O CTE não tem equipamentos da biblioteca"
        action={
          <Buttons>
            <ButtonLink to="/conhecimento?separador=equipamentos">Abrir a biblioteca de equipamentos</ButtonLink>
          </Buttons>
        }
        next="A biblioteca é semeada a partir dos CTE de referência (make seed-library, corrido pela equipa); depois, volte a montar o CTE."
      >
        Nenhuma linha do CTE montado corresponde a um equipamento da biblioteca.
      </EmptyState>
    );
  }
  const selectedId = params.get("slot") ?? data.slots[0]?.id;
  const select = (id: string) => setParams({ slot: id }, { replace: true });
  const count = (fn: (slot: EquipmentSlot) => boolean) => data.slots.filter(fn).length;
  const fails = count((x) => x.verdict === "fails");
  const confirm = count((x) => x.verdict === "to_confirm");
  const old = count((x) => Boolean(x.item?.datasheet?.old));
  const missing = count((x) => x.verdict === "no_datasheet");
  return (
    <div className={s.stack}>
      <div className={s.top}>
        <h2 className={s.h2}>Verificação de equipamentos</h2>
        <div className={s.pills} aria-label="Resumo da verificação">
          {fails ? <Pill tone="crit">{`${fails} não cumpre${fails === 1 ? "" : "m"}`}</Pill> : null}
          {confirm ? <Pill tone="warn">{`${confirm} por confirmar`}</Pill> : null}
          {old ? <Pill tone="warn">{`${old} ficha${old === 1 ? "" : "s"} antiga${old === 1 ? "" : "s"}`}</Pill> : null}
          {missing ? <Pill tone="mute">{`${missing} sem ficha`}</Pill> : null}
          {data.document_status === "approved" ? <Pill tone="info">CTE aprovado: só leitura</Pill> : null}
        </div>
      </div>
      <DataTable caption="Equipamentos de referência do CTE">
        <thead>
          <tr>
            <th scope="col">Equipamento (CTE)</th>
            <th scope="col" className={s.num}>
              Qtd.
            </th>
            <th scope="col">Modelo de referência</th>
            <th scope="col">Ficha</th>
            <th scope="col">Verificação</th>
          </tr>
        </thead>
        <tbody>
          {data.slots.map((slot) => {
            const on = slot.id === selectedId;
            return (
              <tr key={slot.id} className={on ? s.on : undefined}>
                <td>
                  <button type="button" className={s.rowButton} aria-pressed={on} onClick={() => select(slot.id)}>
                    {slot.item?.code ? `${slot.item.code} · ` : ""}
                    {slot.item?.name ?? "—"}
                  </button>
                  <div className={s.muted}>{slot.section_title}</div>
                </td>
                <td className={s.num}>{slot.quantity ? `${formatValue(slot.quantity)} ${slot.unit ?? ""}` : "—"}</td>
                <td>
                  {slot.item ? itemModel(slot.item) : "—"}
                  {!slot.is_reference ? (
                    <div>
                      <Chip>alternativa</Chip>
                    </div>
                  ) : null}
                </td>
                <td className={s.num}>{sheetDate(slot.item?.datasheet ?? null)}</td>
                <td>{verdictPill(slot)}</td>
              </tr>
            );
          })}
        </tbody>
      </DataTable>
      <div className={s.layout}>
        {selectedId ? (
          <SlotDetail slotId={selectedId} projectId={projectId} readOnly={data.document_status === "approved"} />
        ) : null}
        <LibrarySide />
      </div>
    </div>
  );
}

function LibrarySide() {
  const { data } = useEquipmentLibrary();
  const reviewed = data?.filter((e) => e.params_reviewed > 0).length ?? 0;
  const toReview = data?.filter((e) => e.params_to_review > 0).length ?? 0;
  return (
    <div className={s.side}>
      <Card title="Biblioteca de equipamentos TUU">
        <dl className={s.lib}>
          <div>
            <dt>{data?.length ?? 0}</dt>
            <dd>equipamentos</dd>
          </div>
          <div>
            <dt>{reviewed}</dt>
            <dd>com parâmetros revistos</dd>
          </div>
          <div>
            <dt>{toReview}</dt>
            <dd>por rever</dd>
          </div>
        </dl>
        <ButtonLink to="/conhecimento?separador=equipamentos">Abrir a biblioteca</ButtonLink>
      </Card>
      <p className={s.note}>
        Com “ou equivalente”, a verificação confirma que o modelo cumpre os requisitos mínimos do CTE. Não obriga a usar
        a marca. Só os parâmetros revistos pelo curador decidem; os lidos automaticamente ficam por confirmar.
      </p>
    </div>
  );
}

export function ChecksTable({ checks, caption }: { checks: EquipmentCheck[]; caption: string }) {
  if (!checks.length) return <p className={s.muted}>O bloco do CTE não tem requisitos lidos para este equipamento.</p>;
  return (
    <DataTable caption={caption}>
      <thead>
        <tr>
          <th scope="col">Parâmetro</th>
          <th scope="col">Exigido · CTE</th>
          <th scope="col">Ficha do fabricante</th>
          <th scope="col">Resultado</th>
        </tr>
      </thead>
      <tbody>
        {checks.map((c) => (
          <tr key={c.requirement_id}>
            <td>
              {c.label}
              {c.requirement_status !== "approved" ? <div className={s.muted}>requisito por aprovar</div> : null}
            </td>
            <td className={s.mono} title={c.evidence.join("\n")}>
              {`${OPERATOR[c.operator] ?? ""} ${c.required}`.trim()}
            </td>
            <td className={`${s.mono} ${c.result === "fails" ? s.no : ""}`}>
              {c.offered ?? "—"}
              {c.page ? <span className={s.muted}>{` · pág. ${c.page}`}</span> : null}
              {c.review_status === "extracted" ? <span className={s.muted}> · lido, por rever</span> : null}
            </td>
            <td>
              <span className={s[RESULT[c.result].tone]} aria-hidden="true">
                {RESULT[c.result].mark}
              </span>
              <span className={s.resultLabel}>{RESULT[c.result].label}</span>
            </td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}

function suggestion(slot: { verdict: EquipmentVerdict }, passing: EquipmentItem[]): string {
  if (slot.verdict === "fails") {
    if (passing.length) {
      const names = passing.slice(0, 2).map((i) => `${i.name} (${itemModel(i)})`);
      return `${passing.length} equipamento${passing.length === 1 ? "" : "s"} da biblioteca cumpre${passing.length === 1 ? "" : "m"}: ${names.join(" e ")}. Em alternativa, reveja o requisito no CTE.`;
    }
    return "Nenhuma alternativa da biblioteca cumpre com parâmetros revistos: reveja o requisito no CTE ou peça ao curador outra ficha.";
  }
  if (slot.verdict === "no_datasheet") {
    return "Sem ficha técnica na biblioteca: peça-a ao curador. Os parâmetros são lidos automaticamente e ficam por rever até alguém os confirmar.";
  }
  if (slot.verdict === "to_confirm") {
    return "Há parâmetros lidos automaticamente da ficha, ainda não revistos pelo curador: a verificação só decide com eles revistos.";
  }
  if (slot.verdict === "no_requirements") return "O bloco do CTE não diz parâmetros mínimos para este equipamento.";
  return "Todos os parâmetros verificados cumprem o CTE.";
}

function SlotDetail({ slotId, projectId, readOnly }: { slotId: string; projectId: string; readOnly: boolean }) {
  const { data: slot, isPending, error } = useEquipmentSlot(slotId);
  const { data: me } = useMe();
  const choose = useChooseEquipment(projectId);
  const [alternative, setAlternative] = useState("");
  const [reason, setReason] = useState("");
  const base = useId();
  if (isPending) return <Loading />;
  if (error) return <ErrorNote>{error.message}</ErrorNote>;
  const item = slot.item;
  const writer = me?.roles.some((r) => r.id === "redator" || r.id === "tecnico") ?? false;
  const passing = slot.alternatives.filter((a) => a.verdict === "ok").map((a) => a.item);
  const sheet = item?.datasheet ?? null;
  return (
    <Card className={s.detail}>
      <div aria-live="polite">
        <div className={s.detailHead}>
          <div>
            <h3 className={s.h3}>
              {item?.code ? `${item.code} · ` : ""}
              {item?.name ?? "Sem equipamento"}
            </h3>
            <p className={s.muted}>
              {item ? itemModel(item) : ""}
              {sheet ? ` · ${sheet.file_name} · ${sheetDate(sheet)}` : " · sem ficha técnica"}
              {` · ${slot.section_title}`}
            </p>
          </div>
          {verdictPill(slot)}
        </div>
        <div className={s.chips}>
          <Chip>{slot.or_equivalent ? "ou equivalente" : "sem «ou equivalente»"}</Chip>
          {slot.is_reference ? <Chip>modelo de referência</Chip> : <Chip>alternativa escolhida</Chip>}
          {slot.chosen ? <Chip>escolhido{slot.chosen_by ? ` por ${slot.chosen_by}` : ""}</Chip> : null}
          {item?.has_image ? <Chip>{slot.chosen ? "imagem no CTE" : "imagem por incluir"}</Chip> : null}
        </div>
        {slot.reason ? <p className={s.muted}>{`Motivo da troca: “${slot.reason}”`}</p> : null}
        <ChecksTable checks={slot.checks} caption="Requisito do CTE contra a ficha do fabricante" />
        <p className={s.suggestion}>{suggestion(slot, passing)}</p>
        {slot.articles.length ? (
          <p className={s.muted}>{`Mapa de quantidades: ${slot.articles.join("; ")}`}</p>
        ) : null}
      </div>
      <Buttons>
        {sheet ? (
          <DownloadButton path={`/equipment/datasheets/${sheet.id}/file`} filename={sheet.file_name}>
            Abrir ficha
          </DownloadButton>
        ) : null}
        {item ? (
          <ButtonLink to={`/conhecimento?separador=equipamentos&equipamento=${item.id}`}>Ver na biblioteca</ButtonLink>
        ) : null}
        {writer && !readOnly && item && !slot.chosen ? (
          <Button
            small
            disabled={choose.isPending}
            onClick={() => choose.mutate({ slotId: slot.id, equipmentId: item.id })}
          >
            {item.has_image ? "Confirmar e incluir a imagem" : "Confirmar este equipamento"}
          </Button>
        ) : null}
      </Buttons>
      {writer && !readOnly && slot.alternatives.length ? (
        <div className={s.choose}>
          <h4 className={s.h4}>Trocar por uma alternativa da biblioteca</h4>
          <label htmlFor={`${base}-alt`} className={s.label}>
            Equipamento ({slot.alternatives.length} da mesma categoria)
          </label>
          <select
            id={`${base}-alt`}
            className={s.input}
            value={alternative}
            onChange={(e) => setAlternative(e.target.value)}
          >
            <option value="">Escolher…</option>
            {slot.alternatives.map((a) => (
              <option key={a.item.id} value={a.item.id}>
                {`${a.item.code ? `${a.item.code} · ` : ""}${a.item.name} · ${itemModel(a.item)} · ${VERDICT[a.verdict].label}`}
              </option>
            ))}
          </select>
          <label htmlFor={`${base}-reason`} className={s.label}>
            Porque troca (fica registado, ≥ 10 caracteres)
          </label>
          <textarea
            id={`${base}-reason`}
            rows={2}
            className={s.input}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          {choose.error ? <ErrorNote>{choose.error.message}</ErrorNote> : null}
          <Buttons>
            <Button
              variant="primary"
              small
              disabled={!alternative || reason.trim().length < 10 || choose.isPending}
              onClick={() =>
                choose.mutate(
                  { slotId: slot.id, equipmentId: alternative, reason },
                  {
                    onSuccess: () => {
                      setAlternative("");
                      setReason("");
                    },
                  },
                )
              }
            >
              Trocar
            </Button>
          </Buttons>
        </div>
      ) : null}
      {!writer ? <p className={s.muted}>Só o redator e o técnico escolhem os equipamentos do projeto.</p> : null}
    </Card>
  );
}
