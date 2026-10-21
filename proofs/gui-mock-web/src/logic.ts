import data from "../../gui-mock/controls.json";
import type { Cond, Item, Kind, Param, Values } from "./types";

export const kinds = data.kinds as unknown as Record<string, Kind>;
export const items = data.items as unknown as Item[];
const RANK = { primary: 0, secondary: 1, deep: 2 };

// The whole condition language: is, not, all, any, fact. No condition = always valid.
export function valid(c: Cond | undefined, values: Values, facts: Record<string, boolean>): boolean {
  if (!c) return true;
  if ("is" in c) return values[c.is[0]] === c.is[1];
  if ("not" in c) return !valid(c.not, values, facts);
  if ("all" in c) return c.all.every((x) => valid(x, values, facts));
  if ("any" in c) return c.any.some((x) => valid(x, values, facts));
  return !!facts[c.fact];
}

// Every control of a kind in display order (groups as they first appear; primary, secondary, then data order).
// Validity is NOT applied here: invalid rows stay mounted and collapse, so the order never changes.
export function layout(kind: Kind) {
  const groups = [...new Set(kind.params.map((p) => p.group))];
  const sorted = [...kind.params].sort(
    (a, b) => groups.indexOf(a.group) - groups.indexOf(b.group) || RANK[a.importance] - RANK[b.importance]);
  return {
    groups: groups.map((g) => ({ name: g, params: sorted.filter((p) => p.group === g && p.importance !== "deep") })),
    deep: sorted.filter((p) => p.importance === "deep"),
  };
}

export function validIds(item: Item, values: Values) {
  const k = kinds[item.kind], l = layout(k);
  const ok = (p: Param) => valid(p.validWhen, values, item.facts);
  return { shown: l.groups.flatMap((g) => g.params).filter(ok).map((p) => p.id), more: l.deep.filter(ok).map((p) => p.id) };
}
