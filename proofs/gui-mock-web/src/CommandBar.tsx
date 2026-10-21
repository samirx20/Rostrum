import { useEffect, useRef, useState } from "react";
import { items, kinds } from "./logic";
import { select, setValue, useStore } from "./store";
import type { Values } from "./types";

type Cmd = { name: string; hint: string; run: () => void };

// Every command is a select() and/or setValue(): the same two operations a click makes.
const toggle = (item: string, param: string, values: Record<string, Values>) =>
  () => { select(item); setValue(item, param, !values[item][param]); };

const commands = (values: Record<string, Values>): Cmd[] => [
  ...items.map((i) => ({ name: `Select ${i.name}`, hint: kinds[i.kind].label, run: () => select(i.id) })),
  { name: "Toggle depth of field", hint: "Main camera", run: toggle("cam1", "dof", values) },
  { name: "Toggle motion blur", hint: "Main camera", run: toggle("cam1", "motionBlur", values) },
  { name: "Toggle animate on", hint: "Title", run: toggle("title", "animateOn", values) },
  { name: "Toggle shadows", hint: "Key light", run: toggle("key", "shadows", values) },
];

// Ctrl+K: type to filter, arrows to move, Enter to run, Esc to close.
export function CommandBar({ onClose }: { onClose: () => void }) {
  const { values } = useStore();
  const [q, setQ] = useState(""), [cur, setCur] = useState(0);
  const list = commands(values).filter((c) => c.name.toLowerCase().includes(q.toLowerCase()));
  const sel = useRef<HTMLDivElement>(null);
  useEffect(() => { sel.current?.scrollIntoView({ block: "nearest" }); }, [cur]);
  const run = (c?: Cmd) => { if (c) { onClose(); c.run(); } };
  return (
    <div className="scrim" onMouseDown={onClose}>
      <div className="cmdbar" onMouseDown={(e) => e.stopPropagation()}>
        <input autoFocus placeholder="Type a command" value={q}
          onChange={(e) => { setQ(e.target.value); setCur(0); }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setCur(Math.min(list.length - 1, cur + 1)); }
            else if (e.key === "ArrowUp") { e.preventDefault(); setCur(Math.max(0, cur - 1)); }
            else if (e.key === "Enter") run(list[cur]);
            else if (e.key === "Escape") onClose();
          }} />
        <div className="cmdlist">
          {list.map((c, i) => (
            <div key={c.name} ref={i === cur ? sel : undefined} className={"cmd" + (i === cur ? " cur" : "")}
              onMouseEnter={() => setCur(i)} onClick={() => run(c)}>
              <span>{c.name}</span><span className="hint">{c.hint}</span>
            </div>
          ))}
          {list.length === 0 && <div className="none">No matching command</div>}
        </div>
      </div>
    </div>
  );
}
