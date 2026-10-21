import { useSyncExternalStore } from "react";
import { items, validIds } from "./logic";
import type { Mock, Value, Values } from "./types";

// One tiny store: the selected item and each item's values (kept per item). The only two ways to change it
// are select() and setValue(): clicks, keys, the command bar and the demo script all call these.
type State = { selected: string; values: Record<string, Values> };
let state: State = { selected: items[0].id, values: Object.fromEntries(items.map((i) => [i.id, { ...i.values }])) };
const subs = new Set<() => void>();
const emit = () => subs.forEach((f) => f());

export function select(itemId: string) {
  if (!items.some((i) => i.id === itemId)) throw new Error(`unknown item ${itemId}`);
  state = { ...state, selected: itemId };
  emit();
}
export function setValue(itemId: string, param: string, value: Value) {
  const cur = state.values[itemId];
  if (!cur || !(param in cur)) throw new Error(`unknown control ${itemId}.${param}`);
  state = { ...state, values: { ...state.values, [itemId]: { ...cur, [param]: value } } };
  emit();
}
export const getState = () => state;
export const useStore = () =>
  useSyncExternalStore((f) => (subs.add(f), () => subs.delete(f)), () => state);

export const mock: Mock = {
  select,
  setValue,
  visible() {
    const item = items.find((i) => i.id === state.selected)!;
    const v = validIds(item, state.values[item.id]);
    return [...v.shown, ...v.more];
  },
};
(window as unknown as { mock: Mock }).mock = mock;
