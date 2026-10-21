import { useEffect, useState, type ReactNode } from "react";
import { CommandBar } from "./CommandBar";
import { Inspector } from "./Inspector";
import { items, kinds } from "./logic";
import { getState, select, useStore } from "./store";

function Panel({ title, className = "", children }: { title: string; className?: string; children: ReactNode }) {
  return (
    <section className={"panel " + className}>
      <header className="ph">{title}</header>
      <div className="pb">{children}</div>
    </section>
  );
}

const TRACKS = [0, 1, 2], SECONDS = Array.from({ length: 21 }, (_, i) => i);

export function App() {
  const { selected, values } = useStore();
  const [bar, setBar] = useState(false);
  const item = items.find((i) => i.id === selected)!;

  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key.toLowerCase() === "k") { e.preventDefault(); setBar((b) => !b); return; }
      if (bar || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
      if ((e.target as HTMLElement).closest("input, select, textarea, [role=spinbutton]")) return;
      e.preventDefault();
      const i = items.findIndex((x) => x.id === getState().selected);
      select(items[(i + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length].id);
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [bar]);

  return (
    <div className="shell">
      <div className="topbar">
        <span className="wordmark">Rostrum</span>
        <span className="doctab">Launch film</span>
        <span className="grow" />
        <button className="cmdbtn" onClick={() => setBar(true)}>
          <span>Search or run a command</span><kbd>Ctrl K</kbd>
        </button>
      </div>
      <div className="main">
        <Panel title="Project" className="project">
          <div className="list" role="listbox">
            {items.map((i) => (
              <button key={i.id} role="option" aria-selected={i.id === selected} tabIndex={-1}
                className={"item" + (i.id === selected ? " sel" : "")} onClick={() => select(i.id)}>
                <span className="chip">{kinds[i.kind].label[0]}</span>
                <span className="iname2">{i.name}</span>
                <span className="ikind2">{kinds[i.kind].label}</span>
              </button>
            ))}
          </div>
        </Panel>
        <div className="centre">
          <Panel title="Viewport" className="viewport">
            <div className="stage"><div className="sname">{item.name}</div><div className="skind">{kinds[item.kind].label}</div></div>
          </Panel>
          <Panel title="Timeline" className="timeline">
            <div className="ruler">
              {SECONDS.map((s) => (
                <span key={s} className={"tick" + (s % 5 === 0 ? " big" : "")} style={{ left: `${(s / 20) * 100}%` }}>
                  {s % 5 === 0 && s < 20 && <b>{s}s</b>}
                </span>
              ))}
            </div>
            {TRACKS.map((t) => <div key={t} className="track" />)}
          </Panel>
        </div>
        <Panel title="Inspector" className="inspect">
          <Inspector key={item.id} item={item} values={values[item.id]} />
        </Panel>
      </div>
      {bar && <CommandBar onClose={() => setBar(false)} />}
    </div>
  );
}
