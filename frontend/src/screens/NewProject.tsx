/** Screen B: new project wizard (Projeto → Âmbito → Ficheiros → Ficha-base → Montar). */

import { useQueryClient } from "@tanstack/react-query";
import { type DragEvent, type FormEvent, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { useProjectEvents } from "../api/events";
import { keys, uploadFile, useCreateProject, useFicha, useFiles, useProject, useRefreshProject } from "../api/queries";
import type { ProjectFile, ProjectIn } from "../api/types";
import { Button, ButtonLink, Buttons, Card, ErrorNote, Pill, type Tone } from "../components/ui";
import { fileSize, kindLabel } from "../lib/format";
import { Checklist, Loading } from "./common";
import s from "./NewProject.module.css";
import { Screen } from "./Screen";

const STEPS = ["Projeto", "Âmbito", "Ficheiros", "Ficha-base", "Montar"];

function Steps({ current }: { current: number }) {
  return (
    <ol className={s.steps} aria-label="Passos">
      {STEPS.map((label, i) => (
        <li
          key={label}
          className={i < current ? s.done : i === current ? s.on : undefined}
          aria-current={i === current ? "step" : undefined}
        >
          {label}
        </li>
      ))}
    </ol>
  );
}

const BUILDING_TYPES = [
  "Moradia unifamiliar",
  "Habitação coletiva",
  "Comércio",
  "Serviços",
  "Equipamento público",
  "Indústria",
];

export function NewProjectScreen() {
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<ProjectIn>({
    code: "",
    name: "",
    building_type: "",
    phase: "execucao",
    public_procurement: false,
  });
  const create = useCreateProject();
  const navigate = useNavigate();

  const next = (event: FormEvent) => {
    event.preventDefault();
    if (step === 0) {
      setStep(1);
      return;
    }
    create.mutate(
      { ...form, code: form.code.trim().toUpperCase(), building_type: form.building_type || null },
      { onSuccess: (project) => navigate(`/projetos/${project.id}/ficheiros`) },
    );
  };

  return (
    <Screen
      crumb="Novo projeto"
      title="Novo projeto"
      description="A entrada é estruturada: o agente recebe dados concretos do projeto, não uma descrição vaga."
    >
      <div className={s.wiz}>
        <Steps current={step} />
        <form className={s.form} onSubmit={next}>
          {step === 0 ? (
            <>
              <div className={s.row2}>
                <div className={s.field}>
                  <label htmlFor="code">Código do projeto</label>
                  <input
                    id="code"
                    required
                    pattern="[A-Za-z0-9][A-Za-z0-9_\-]{1,31}"
                    title="Letras, algarismos, - ou _ (2 a 32 carateres)"
                    value={form.code}
                    onChange={(e) => setForm({ ...form, code: e.target.value })}
                    autoComplete="off"
                  />
                </div>
                <div className={s.field}>
                  <label htmlFor="name">Designação</label>
                  <input
                    id="name"
                    required
                    maxLength={200}
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                  />
                </div>
              </div>
              <div className={s.field}>
                <label htmlFor="type">Tipo de edifício</label>
                <input
                  id="type"
                  list="building-types"
                  maxLength={120}
                  value={form.building_type ?? ""}
                  onChange={(e) => setForm({ ...form, building_type: e.target.value })}
                />
                <datalist id="building-types">
                  {BUILDING_TYPES.map((t) => (
                    <option key={t} value={t} />
                  ))}
                </datalist>
              </div>
              <Buttons>
                <ButtonLink to="/">Cancelar</ButtonLink>
                <Button type="submit" variant="primary">
                  Seguinte: âmbito →
                </Button>
              </Buttons>
            </>
          ) : (
            <>
              <fieldset className={s.field}>
                <legend>Fase do projeto</legend>
                <div className={s.seg}>
                  {(["licenciamento", "execucao"] as const).map((phase) => (
                    <button
                      key={phase}
                      type="button"
                      aria-pressed={form.phase === phase}
                      onClick={() => setForm({ ...form, phase })}
                    >
                      {phase === "licenciamento" ? "Licenciamento" : "Execução"}
                    </button>
                  ))}
                </div>
              </fieldset>
              <fieldset className={s.field}>
                <legend>Especialidades</legend>
                <label className={s.check}>
                  <input type="checkbox" checked disabled /> Instalações elétricas
                </label>
                <p className={s.hint}>ITED, SCIE e as restantes especialidades entram na Fase 9.</p>
              </fieldset>
              <label className={s.check}>
                <input
                  type="checkbox"
                  checked={form.public_procurement}
                  onChange={(e) => setForm({ ...form, public_procurement: e.target.checked })}
                />{" "}
                Contratação pública (CCP): marcas com “ou equivalente”
              </label>
              {create.error ? <ErrorNote>{create.error.message}</ErrorNote> : null}
              <Buttons>
                <Button onClick={() => setStep(0)}>← Voltar</Button>
                <Button type="submit" variant="primary" disabled={create.isPending}>
                  Criar projeto e carregar ficheiros →
                </Button>
              </Buttons>
            </>
          )}
        </form>
      </div>
    </Screen>
  );
}

const STATUS: Record<ProjectFile["ingest_status"], [Tone, string]> = {
  pending: ["info", "Na fila"],
  running: ["info", "A ler…"],
  done: ["ok", "Lido"],
  failed: ["crit", "Não lido"],
  skipped: ["mute", "Guardado"],
};

export function ProjectFilesScreen() {
  const { projectId = "" } = useParams();
  const { data: project } = useProject(projectId);
  const { data: files, isLoading } = useFiles(projectId);
  const { data: ficha } = useFicha(projectId);
  const client = useQueryClient();
  const refresh = useRefreshProject();
  const [uploading, setUploading] = useState<string[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);

  useProjectEvents(projectId, (event) => {
    if (event.type === "section") return; // drafting progress: the editor follows it
    client.setQueryData<ProjectFile[]>(keys.files(projectId), (old) =>
      old?.map((f) =>
        f.id === event.file_id
          ? {
              ...f,
              ingest_status: event.status,
              ingest_message: event.message,
              ingest_warnings: event.warnings ?? f.ingest_warnings,
            }
          : f,
      ),
    );
    if (event.status === "done" || event.status === "failed") refresh(projectId);
  });

  const send = async (list: FileList | null) => {
    if (!list) return;
    setErrors([]);
    for (const file of Array.from(list)) {
      setUploading((u) => [...u, file.name]);
      try {
        await uploadFile(projectId, file);
      } catch (error) {
        setErrors((e) => [...e, `${file.name}: ${error instanceof Error ? error.message : "erro"}`]);
      } finally {
        setUploading((u) => u.filter((n) => n !== file.name));
        refresh(projectId);
      }
    }
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    void send(event.dataTransfer.files);
  };

  const confirmed = ficha?.revisions.some((r) => r.status === "confirmed") ?? false;
  const hasFicha = Boolean(ficha?.revision);
  const step = confirmed ? 4 : hasFicha ? 3 : 2;

  return (
    <Screen
      crumb={project ? `${project.code} · ${project.name}` : "Projeto"}
      title="Ficheiros do projeto"
      description="Carregue os ficheiros do projeto. A ficha eletrotécnica, a Tabela de Cálculo, as 09-Folhas de Cálculo, o MQT ou a LPU e o PDF das peças desenhadas são lidos e juntam-se à ficha-base, cada valor com a sua origem. Os restantes (DWG, DOCX…) ficam guardados."
    >
      <div className={s.wiz}>
        <Steps current={step} />
        <div className={s.form}>
          <div
            className={dragging ? `${s.drop} ${s.dragging}` : s.drop}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
          >
            <p>
              Arraste para aqui os ficheiros do projeto: ficha eletrotécnica (.xlsm), Tabela de Cálculo e
              MQT/LPU (.xlsx), 09-Folhas de Cálculo (.xls) e peças desenhadas (.pdf)
            </p>
            <label className={s.pick}>
              Escolher ficheiros
              <input
                type="file"
                multiple
                className="visually-hidden"
                accept=".xlsm,.xlsx,.xls,.pdf,.dwg,.dwfx,.docx"
                onChange={(e) => {
                  void send(e.target.files);
                  e.target.value = "";
                }}
              />
            </label>
          </div>
          {errors.map((e) => (
            <ErrorNote key={e}>{e}</ErrorNote>
          ))}
          {isLoading ? <Loading /> : null}
          <ul className={s.files} aria-label="Ficheiros carregados">
            {uploading.map((name) => (
              <li key={`up-${name}`} className={s.file}>
                <span className={s.ext}>…</span>
                <span className={s.fileMain}>
                  <b>{name}</b>
                  <span>A carregar…</span>
                </span>
                <Pill tone="info">A carregar</Pill>
              </li>
            ))}
            {(files ?? []).map((f) => {
              const [tone, label] = STATUS[f.ingest_status];
              const warnings = f.ingest_warnings ?? [];
              return (
                <li key={f.id} className={s.file}>
                  <span className={s.ext}>{f.filename.split(".").pop()?.toUpperCase().slice(0, 4)}</span>
                  <span className={s.fileMain}>
                    <b>{f.filename}</b>
                    <span>
                      {kindLabel(f.kind)} · {fileSize(f.size_bytes)}
                      {f.ingest_message ? ` · ${f.ingest_message}` : ""}
                    </span>
                    {f.ingest_status === "failed" ? (
                      <span className={s.failed}>
                        Este ficheiro não entrou na ficha-base; os outros continuam a ser lidos. Confirme
                        que é o ficheiro certo ou peça uma nova cópia.
                      </span>
                    ) : null}
                    {warnings.length ? (
                      <ul className={s.warnings} aria-label={`Avisos de ${f.filename}`}>
                        {warnings.map((w) => (
                          <li key={w}>{w}</li>
                        ))}
                      </ul>
                    ) : null}
                  </span>
                  <Pill tone={warnings.length && f.ingest_status === "done" ? "warn" : tone}>
                    {warnings.length && f.ingest_status === "done" ? "Lido com avisos" : label}
                  </Pill>
                </li>
              );
            })}
          </ul>
          {files && files.length === 0 && uploading.length === 0 ? (
            <p className={s.hint}>Ainda não há ficheiros neste projeto.</p>
          ) : null}
          {files && files.length ? <ReadSummary files={files} /> : null}
          <Card title="A seguir">
            <Checklist
              items={[
                { done: hasFicha, text: "Ficha-base criada a partir dos ficheiros" },
                {
                  done: hasFicha && (ficha?.open_conflicts ?? 0) === 0,
                  text:
                    ficha && ficha.open_conflicts > 0
                      ? `${ficha.open_conflicts} conflito(s) por resolver na ficha-base`
                      : "Sem conflitos por resolver",
                },
                { done: confirmed, text: "Ficha-base confirmada por um técnico responsável" },
              ]}
            />
            <Buttons>
              <ButtonLink to={`/projetos/${projectId}/ficha`} variant="primary">
                Ver a ficha do projeto →
              </ButtonLink>
              <Button disabled title="Disponível na Fase 4, com a ficha-base confirmada">
                Montar peças
              </Button>
            </Buttons>
            <p className={s.hint}>
              Não é possível montar peças sem ficha-base confirmada. A montagem do MDJ e do CTE chega
              na Fase 4.
            </p>
          </Card>
          <p className={s.hint}>
            <Link to="/">Voltar ao painel</Link>
          </p>
        </div>
      </div>
    </Screen>
  );
}


/** The five kinds that are read (SPEC 8.2), with what arrived of each. */
const READ_KINDS: [kinds: string[], label: string][] = [
  [["ficha_eletrotecnica"], "Ficha eletrotécnica"],
  [["calc_summary"], "Tabela de Cálculo"],
  [["calc_circuit"], "09-Folhas de Cálculo"],
  [["mqt", "lpu"], "MQT / LPU"],
  [["drawing_pdf"], "Peças desenhadas (PDF)"],
];

function ReadSummary({ files }: { files: ProjectFile[] }) {
  return (
    <Card title="O que foi lido">
      <ul className={s.summary} aria-label="Resumo por tipo de ficheiro">
        {READ_KINDS.map(([kinds, label]) => {
          const mine = files.filter((f) => kinds.includes(f.kind));
          const done = mine.filter((f) => f.ingest_status === "done").length;
          const failed = mine.filter((f) => f.ingest_status === "failed").length;
          const warned = mine.filter((f) => (f.ingest_warnings ?? []).length > 0).length;
          const reading = mine.length - done - failed;
          const [tone, text]: [Tone, string] = !mine.length
            ? ["mute", "Por carregar"]
            : failed
              ? ["crit", `${failed} não lido${failed > 1 ? "s" : ""}`]
              : reading
                ? ["info", "A ler…"]
                : warned
                  ? ["warn", `${warned} com avisos`]
                  : ["ok", "Lido"];
          return (
            <li key={label}>
              <span>
                <b>{label}</b>
                {mine.length ? ` · ${mine.length} ficheiro${mine.length > 1 ? "s" : ""}` : ""}
              </span>
              <Pill tone={tone}>{text}</Pill>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
