/**
 * Section content (TipTap JSON, SPEC 7.3) and what the editor does with it.
 *
 * The backend writes three kinds of nodes: "locked" (a fixed block, with its paragraphs inside),
 * "pending" (adaptive text not written yet) and "paragraph" (parametric or generated text, with
 * "value" and "generated" marks). In the editor, locked and pending nodes are atoms that keep
 * their original JSON, so that a fixed block never changes unless it was unlocked.
 */

import type { ContentNode, SectionContent, TextNode } from "../api/types";

export function isText(node: TextNode | ContentNode): node is TextNode {
  return node.type === "text";
}

/** Plain text of a node (values as shown). */
export function nodeText(node: ContentNode): string {
  return (node.content ?? [])
    .map((child) => (isText(child) ? child.text : nodeText(child)))
    .join(node.type === "locked" ? "\n" : "");
}

/** The paragraphs the agent wrote (or will write), in order. */
export function generatedParagraphs(content: SectionContent): string[] {
  return content.content
    .filter((n) => n.type === "paragraph" && n.attrs?.generated)
    .map((n) => nodeText(n))
    .filter((t) => t.trim());
}

export function hasPending(content: SectionContent): boolean {
  return content.content.some((n) => n.type === "pending");
}

type EditorNode = { type: string; attrs?: Record<string, unknown>; content?: EditorNode[] } & Record<string, unknown>;

/** Section content → TipTap document: locked and pending nodes become atoms. */
export function toEditor(content: SectionContent, unlocked: boolean): EditorNode {
  const nodes: EditorNode[] = [];
  for (const node of content.content) {
    if (node.type === "locked" && unlocked) {
      for (const p of node.content ?? []) {
        nodes.push({
          ...(p as EditorNode),
          attrs: { ...(p as EditorNode).attrs, lockedEntry: node.attrs?.entry ?? null },
        });
      }
      if (!(node.content ?? []).length) nodes.push({ type: "lockedAtom", attrs: { original: JSON.stringify(node) } });
    } else if (node.type === "locked" || node.type === "pending") {
      nodes.push({
        type: node.type === "locked" ? "lockedAtom" : "pendingAtom",
        attrs: { original: JSON.stringify(node) },
      });
    } else {
      nodes.push(node as unknown as EditorNode);
    }
  }
  return { type: "doc", content: nodes.length ? nodes : [{ type: "paragraph" }] };
}

/** TipTap document → section content (the atoms give back their original JSON). */
export function fromEditor(doc: EditorNode): SectionContent {
  const out: ContentNode[] = [];
  let unlockedGroup: ContentNode | null = null;
  for (const node of doc.content ?? []) {
    if (node.type === "lockedAtom" || node.type === "pendingAtom") {
      unlockedGroup = null;
      out.push(JSON.parse(String(node.attrs?.original)) as ContentNode);
      continue;
    }
    const lockedEntry = node.attrs?.lockedEntry;
    const { lockedEntry: _drop, ...attrs } = node.attrs ?? {};
    void _drop;
    const paragraph = { ...node, attrs } as unknown as ContentNode;
    if (lockedEntry !== undefined && lockedEntry !== null) {
      if (!unlockedGroup || unlockedGroup.attrs?.entry !== lockedEntry) {
        unlockedGroup = { type: "locked", attrs: { entry: lockedEntry, parametric: false }, content: [] };
        out.push(unlockedGroup);
      }
      unlockedGroup.content!.push(paragraph);
    } else {
      unlockedGroup = null;
      out.push(paragraph);
    }
  }
  return { type: "doc", content: out };
}
