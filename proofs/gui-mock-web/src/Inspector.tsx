import { useState, type ReactNode } from "react";
import { kinds, layout, valid } from "./logic";
import { setValue } from "./store";
import type { Item, Param, Values } from "./types";
import { WIDGETS } from "./widgets";

// Stays mounted while closed: grid rows 0fr -> 1fr and opacity do the 160 ms reveal. `inert` keeps a collapsed
// row out of the tab order and away from screen readers.
function Collapse({ open, children }: { open: boolean; children: ReactNode }) {
  return <div className={"c" + (open ? " open" : "")} inert={!open}><div className="ci">{children}</div></div>;
}

// The one generic row: the widget comes from the control's `type`, nothing else is per control.
function Row({ item, p, values, open }: { item: Item; p: Param; values: Values; open: boolean }) {
  const W = WIDGETS[p.type];
  return (
    <Collapse open={open}>
      <div className="row" data-ctl={p.id}>
        <span className="lbl">{p.label}</span>
        <W p={p} value={values[p.id]} onChange={(v) => setValue(item.id, p.id, v)} />
      </div>
    </Collapse>
  );
}

// Mounted fresh for each selected item (key = item id), so changing selection swaps everything at once.
export function Inspector({ item, values }: { item: Item; values: Values }) {
  const kind = kinds[item.kind], { groups, deep } = layout(kind);
  const [more, setMore] = useState(false);
  const ok = (p: Param) => valid(p.validWhen, values, item.facts);
  const deepOpen = deep.some(ok);
  return (
    <div className="inspector">
      <div className="iname">{item.name}</div>
      <div className="ikind">{kind.label}</div>
      {groups.map((g) => (
        <Collapse key={g.name} open={g.params.some(ok)}>
          <div className="group">{g.name}</div>
          {g.params.map((p) => <Row key={p.id} item={item} p={p} values={values} open={ok(p)} />)}
        </Collapse>
      ))}
      <Collapse open={deepOpen}>
        <button className={"more" + (more ? " open" : "")} aria-expanded={more} onClick={() => setMore(!more)}>
          <span className="chev" />More
        </button>
      </Collapse>
      <Collapse open={deepOpen && more}>
        {deep.map((p) => <Row key={p.id} item={item} p={p} values={values} open={deepOpen && more && ok(p)} />)}
      </Collapse>
    </div>
  );
}
