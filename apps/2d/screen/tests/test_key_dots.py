"""Key dots on a timeline row never sit closer than their 16 px click area (qml/KeyGroups.js), at the bar's ends too,
merged or apart. Runs the real file through node (skipped where node is missing)."""
import json, shutil, subprocess, pathlib, pytest

JS = pathlib.Path(__file__).resolve().parents[1] / "qml" / "KeyGroups.js"


@pytest.mark.skipif(not shutil.which("node"), reason="node missing")
def test_dots_never_closer_than_16px():
    code = f"""const src=require('fs').readFileSync({json.dumps(str(JS))},'utf8').replace('.pragma library','');
const group=new Function(src+';return group')();
let worst=1e9;
for (const perSec of [3,17.3,40,90,200,1000]) for (let seed=1;seed<60;seed++) {{
  let r=seed, ts=[]; for (let i=0;i<40;i++) {{ r=(r*1103515245+12345)%2147483648; ts.push(r/2147483648*4); }}
  ts.sort((a,b)=>a-b); ts=ts.filter((t,i)=>i==0||t>ts[i-1]);
  const xOf=t=>8+Math.round(t*perSec);
  const d=group(ts.map((t,i)=>({{t,id:i}})),xOf,16);
  for (let i=1;i<d.length;i++) worst=Math.min(worst,xOf(d[i].t)-xOf(d[i-1].t));
}}
console.log(worst)"""
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout
    assert float(out) >= 16
