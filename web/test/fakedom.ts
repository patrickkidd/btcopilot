/** Just enough of a page for a view drawn from markup and drawn again in
 * place: elements with attributes and children, text, a template, and a
 * reader for the plain markup the app's lists are written in. */

const VOID = new Set(["br", "img", "input", "hr", "meta", "link"]);

export class FakeNode {
  parentNode: FakeElement | null = null;
  nodeType = 0;
  nodeValue: string | null = null;

  get nextSibling(): FakeNode | null {
    const siblings = this.parentNode?.childNodes;
    return siblings ? (siblings[siblings.indexOf(this) + 1] ?? null) : null;
  }

  get isConnected(): boolean {
    return this.parentNode !== null;
  }
}

export class FakeText extends FakeNode {
  constructor(text: string) {
    super();
    this.nodeType = 3;
    this.nodeValue = text;
  }
}

export class FakeElement extends FakeNode {
  childNodes: FakeNode[] = [];
  onclick: unknown = null;
  scrollTop = 0;
  parentElement = null;
  private attrs = new Map<string, string>();
  readonly tagName: string;
  readonly content: FakeElement | null;

  constructor(tag: string) {
    super();
    this.nodeType = 1;
    this.tagName = tag.toUpperCase();
    this.content = this.tagName === "TEMPLATE" ? new FakeElement("fragment") : null;
  }

  get attributes(): { name: string; value: string }[] {
    return [...this.attrs].map(([name, value]) => ({ name, value }));
  }
  getAttribute(name: string): string | null {
    return this.attrs.get(name) ?? null;
  }
  setAttribute(name: string, value: string): void {
    this.attrs.set(name, value);
  }
  removeAttribute(name: string): void {
    this.attrs.delete(name);
  }
  hasAttribute(name: string): boolean {
    return this.attrs.has(name);
  }
  get firstChild(): FakeNode | null {
    return this.childNodes[0] ?? null;
  }
  get children(): FakeElement[] {
    return this.childNodes.filter((n): n is FakeElement => n instanceof FakeElement);
  }
  get firstElementChild(): FakeElement | null {
    return this.children[0] ?? null;
  }
  get childElementCount(): number {
    return this.children.length;
  }
  insertBefore(node: FakeNode, ref: FakeNode | null): FakeNode {
    node.parentNode?.removeChild(node);
    const at = ref === null ? this.childNodes.length : this.childNodes.indexOf(ref);
    this.childNodes.splice(at < 0 ? this.childNodes.length : at, 0, node);
    node.parentNode = this;
    return node;
  }
  removeChild(node: FakeNode): FakeNode {
    this.childNodes.splice(this.childNodes.indexOf(node), 1);
    node.parentNode = null;
    return node;
  }
  addEventListener(): void {}
  /** Every element under this one, in order. */
  all(): FakeElement[] {
    return this.children.flatMap((child) => [child, ...child.all()]);
  }
  set innerHTML(html: string) {
    const into = this.content ?? this;
    for (const node of [...into.childNodes]) into.removeChild(node);
    for (const node of read(html)) into.insertBefore(node, null);
  }
}

/** The markup as nodes: tags with quoted attributes, text, void and
 * self-closed elements. */
function read(html: string): FakeNode[] {
  const top = new FakeElement("fragment");
  const open: FakeElement[] = [top];
  const tag = /<(\/?)([a-zA-Z][\w-]*)((?:\s+[^\s=>/]+(?:="[^"]*")?)*)\s*(\/?)>/g;
  let at = 0;
  for (let m = tag.exec(html); m; m = tag.exec(html)) {
    if (m.index > at) open.at(-1)!.insertBefore(new FakeText(html.slice(at, m.index)), null);
    at = tag.lastIndex;
    const [, closing, name, attrs, selfClosed] = m;
    if (closing) {
      open.pop();
      continue;
    }
    const element = new FakeElement(name);
    for (const a of attrs.matchAll(/([^\s=]+)(?:="([^"]*)")?/g)) element.setAttribute(a[1], a[2] ?? "");
    open.at(-1)!.insertBefore(element, null);
    if (!selfClosed && !VOID.has(name.toLowerCase())) open.push(element);
  }
  if (at < html.length) open.at(-1)!.insertBefore(new FakeText(html.slice(at)), null);
  return [...top.childNodes];
}
