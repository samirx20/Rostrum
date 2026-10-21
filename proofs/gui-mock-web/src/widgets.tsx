import { useRef, useState } from "react";
import type { Param, Value } from "./types";

type W = { p: Param; value: Value; onChange: (v: Value) => void };
const decimals = (step = 1) => (String(step).split(".")[1] ?? "").length;

export function Toggle({ value, onChange }: W) {
  return (
    <button role="switch" aria-checked={!!value} className={"switch" + (value ? " on" : "")} onClick={() => onChange(!value)}>
      <span />
    </button>
  );
}

// A calm compact field: value + unit, a hairline showing where it sits in its range. Drag sideways, arrows
// (Shift = 10x), or click to type.
export function NumberField({ p, value, onChange }: W) {
  const { min = 0, max = 100, step = 1, unit = "" } = p;
  const v = value as number, d = decimals(step);
  const [editing, setEditing] = useState(false);
  const drag = useRef({ x: 0, v: 0, moved: false });
  const set = (n: number) => onChange(+Math.min(max, Math.max(min, Math.round(n / step) * step)).toFixed(d));
  const fmt = (n: number) => n.toFixed(d);
  if (editing)
    return (
      <input className="field num" autoFocus defaultValue={fmt(v)} onFocus={(e) => e.target.select()}
        onBlur={(e) => { const n = parseFloat(e.target.value); if (!isNaN(n)) set(n); setEditing(false); }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === "Escape") { if (e.key === "Escape") e.currentTarget.value = fmt(v); e.currentTarget.blur(); }
        }} />
    );
  const prefix = unit.endsWith("/");
  const key = (e: React.KeyboardEvent, dir: number) => { e.preventDefault(); set(v + dir * step * (e.shiftKey ? 10 : 1)); };
  return (
    <div className="field num" tabIndex={0} role="spinbutton" aria-valuenow={v}
      onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); drag.current = { x: e.clientX, v, moved: false }; }}
      onPointerMove={(e) => {
        if (!e.currentTarget.hasPointerCapture(e.pointerId)) return;
        const dx = e.clientX - drag.current.x;
        if (Math.abs(dx) > 3) drag.current.moved = true;
        if (drag.current.moved) set(drag.current.v + (dx * (max - min)) / 200);
      }}
      onPointerUp={() => { if (!drag.current.moved) setEditing(true); }}
      onKeyDown={(e) => {
        if (e.key === "ArrowUp" || e.key === "ArrowRight") key(e, 1);
        else if (e.key === "ArrowDown" || e.key === "ArrowLeft") key(e, -1);
        else if (e.key === "Enter") setEditing(true);
      }}>
      <span className="mono">{prefix ? unit : ""}{fmt(v)}</span><span className="unit">{prefix ? "" : unit}</span>
      <i style={{ width: `${((v - min) / (max - min)) * 100}%` }} />
    </div>
  );
}

// Segmented for <= 3 options, else a dropdown.
export function Choice({ p, value, onChange }: W) {
  const o = p.options!;
  if (o.length <= 3)
    return (
      <div className="seg" role="radiogroup">
        {o.map((x) => (
          <button key={x} role="radio" aria-checked={x === value} className={x === value ? "on" : ""} onClick={() => onChange(x)}>{x}</button>
        ))}
      </div>
    );
  return (
    <div className="field select">
      <select value={value as string} onChange={(e) => onChange(e.target.value)}>{o.map((x) => <option key={x}>{x}</option>)}</select>
    </div>
  );
}

export function Colour({ value, onChange }: W) {
  return (
    <label className="colour">
      <span className="swatch" style={{ background: value as string }} />
      <span className="mono">{value}</span>
      <input type="color" value={value as string} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

export function TextInput({ value, onChange }: W) {
  return <input className="field text" value={value as string} onChange={(e) => onChange(e.target.value)} />;
}

export const WIDGETS = { toggle: Toggle, number: NumberField, choice: Choice, color: Colour, text: TextInput };
