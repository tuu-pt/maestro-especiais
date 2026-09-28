/** The text of one section in TipTap, with the marks of SPEC 7.3: value, generated, citation, locked. */

import { Mark, mergeAttributes, Node } from "@tiptap/core";
import { EditorContent, NodeViewWrapper, ReactNodeViewRenderer, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect } from "react";

import type { ContentNode, SectionContent } from "../api/types";
import { fromEditor, nodeText, toEditor } from "../lib/content";
import s from "./Editor.module.css";

const ValueMark = Mark.create({
  name: "value",
  inclusive: false,
  addAttributes() {
    return { key: {}, anchor: {}, label: {}, personal: { default: false }, missing: { default: false } };
  },
  parseHTML: () => [{ tag: "span[data-value]" }],
  renderHTML({ HTMLAttributes, mark }) {
    const a = mark.attrs as { key: string; label: string; personal: boolean; missing: boolean };
    const cls = a.missing ? s.valueMissing : a.personal ? s.valuePersonal : s.value;
    return [
      "span",
      mergeAttributes(HTMLAttributes, { "data-value": a.key, class: cls, title: `Ficha-base · ${a.label}` }),
      0,
    ];
  },
});

const GeneratedMark = Mark.create({
  name: "generated",
  parseHTML: () => [{ tag: "span[data-generated]" }],
  renderHTML: ({ HTMLAttributes }) => [
    "span",
    mergeAttributes(HTMLAttributes, { "data-generated": "", class: s.generated }),
    0,
  ],
});

const CitationMark = Mark.create({
  name: "citation",
  addAttributes: () => ({ target: {} }),
  renderHTML: ({ HTMLAttributes }) => ["span", mergeAttributes(HTMLAttributes, { class: s.citation }), 0],
});

/** Paragraph attributes the backend needs back (entry of the block, generated, sources…). */
const KeepAttributes = Node.create({
  name: "keepAttributes",
  addGlobalAttributes() {
    return [
      {
        types: ["paragraph"],
        attributes: {
          entry: { default: null, rendered: false },
          generated: { default: null, rendered: false },
          anchor: { default: null, rendered: false },
          sources: { default: null, rendered: false },
          lockedEntry: { default: null, rendered: false },
        },
      },
    ];
  },
});

function AtomView({ node }: { node: { type: { name: string }; attrs: Record<string, unknown> } }) {
  const original = JSON.parse(String(node.attrs.original)) as ContentNode;
  if (node.type.name === "pendingAtom") {
    return (
      <NodeViewWrapper className={s.pending} contentEditable={false}>
        {`Texto adaptativo por gerar${original.attrs?.note ? ` · ${String(original.attrs.note)}` : ""}`.replace(/\.?$/, ".")}
      </NodeViewWrapper>
    );
  }
  const lines = (original.content ?? []).map((p) => nodeText(p as ContentNode)).filter((t) => t.trim());
  if (!lines.length) return <NodeViewWrapper className={s.lockedEmpty} contentEditable={false} />;
  return (
    <NodeViewWrapper className={s.locked} contentEditable={false}>
      {lines.map((line, i) => (
        <p key={i}>{line}</p>
      ))}
    </NodeViewWrapper>
  );
}

function atom(name: string) {
  return Node.create({
    name,
    group: "block",
    atom: true,
    selectable: true,
    draggable: false,
    addAttributes: () => ({ original: { default: "{}" } }),
    parseHTML: () => [{ tag: `div[data-${name}]` }],
    renderHTML: ({ HTMLAttributes }) => ["div", mergeAttributes(HTMLAttributes, { [`data-${name}`]: "" })],
    addNodeView: () => ReactNodeViewRenderer(AtomView),
  });
}

const extensions = [
  StarterKit.configure({ heading: false, codeBlock: false, blockquote: false, horizontalRule: false }),
  ValueMark,
  GeneratedMark,
  CitationMark,
  KeepAttributes,
  atom("lockedAtom"),
  atom("pendingAtom"),
];

export function SectionEditor({
  content,
  editable,
  unlocked,
  reviewed,
  label,
  onChange,
}: {
  content: SectionContent;
  editable: boolean;
  unlocked: boolean;
  reviewed: boolean;
  label: string;
  onChange?: (content: SectionContent) => void;
}) {
  const editor = useEditor(
    {
      extensions,
      content: toEditor(content, unlocked),
      editable,
      editorProps: { attributes: { "aria-label": label, class: s.prose ?? "" } },
      onUpdate: ({ editor: e }) => onChange?.(fromEditor(e.getJSON() as Parameters<typeof fromEditor>[0])),
    },
    [content, unlocked],
  );
  useEffect(() => {
    editor?.setEditable(editable);
  }, [editor, editable]);
  return (
    <div className={`${s.document} ${reviewed ? s.reviewed : ""}`}>
      <EditorContent editor={editor} />
    </div>
  );
}
