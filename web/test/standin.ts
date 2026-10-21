/** A form as lock() reads it: its buttons, fields and choices, stood in for
 * without a browser. */
export function standInForm() {
  const fields = [{ readOnly: false }, { readOnly: false }];
  const picks = [{ disabled: false }, { disabled: false }];
  const acts = { removed: false, remove() { this.removed = true; } };
  const form = {
    fields,
    picks,
    acts,
    querySelector: (sel: string) => (sel === ".acts" ? acts : null),
    querySelectorAll: (sel: string) => (sel === ".f" ? fields : picks),
  };
  return form;
}
