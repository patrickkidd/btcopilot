/** A form as lock() reads it: its buttons, fields and choices, stood in for
 * without a browser. */
export function standInForm() {
  const fields = [{ readOnly: false }, { readOnly: false }];
  const picks = [{ disabled: false }, { disabled: false }];
  const acts = { removed: false, remove() { this.removed = true; } };
  const top: { textContent: string }[] = [];
  const form = {
    fields,
    picks,
    acts,
    top,
    querySelector: (sel: string) => (sel === ".acts" ? acts : null),
    querySelectorAll: (sel: string) => (sel === ".f" ? fields : picks),
    prepend: (node: { innerHTML: string }) => top.push({ textContent: node.innerHTML }),
  };
  return form;
}
