export type Cond =
  | { is: [string, unknown] } | { not: Cond } | { all: Cond[] } | { any: Cond[] } | { fact: string };
export type Param = {
  id: string; label: string; group: string; type: "toggle" | "number" | "choice" | "color" | "text";
  importance: "primary" | "secondary" | "deep"; validWhen?: Cond;
  min?: number; max?: number; step?: number; unit?: string; options?: string[];
};
export type Kind = { label: string; params: Param[] };
export type Value = string | number | boolean;
export type Values = Record<string, Value>;
export type Item = { id: string; name: string; kind: string; facts: Record<string, boolean>; values: Values };
export type Mock = {
  select(itemId: string): void;
  setValue(itemId: string, param: string, value: Value): void;
  visible(): string[];
};
