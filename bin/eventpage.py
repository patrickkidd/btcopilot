"""Render the two-clock dashboard: the event ledger (events.json) as a branching timeline
and the topic register (TOPICS.md) as the state view, on one page with one dataset.

  python bin/eventpage.py <out.html>
"""
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DOC = HERE / "doc" / "chat-first"


def topic_blocks() -> list[dict]:
    text = (DOC / "TOPICS.md").read_text()
    out = []
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        head, _, body = block.partition("\n")
        tid, _, name = head.partition(" · ")
        fields = {}
        for f in ("Status", "Decided", "Open", "Lives in", "Next action", "Updated"):
            m = re.search(rf"\*\*{re.escape(f)}:\*\*\s*(.*?)(?=\n\*\*|\Z)", body, re.S)
            fields[f] = " ".join(m.group(1).split()) if m else ""
        out.append({"id": tid.strip(), "name": name.strip(), **fields})
    out.append({"id": "untagged", "name": "Not yet assigned to a topic (audit lane)", "Status": "every record here needs a home", "Decided": "", "Open": "", "Lives in": "", "Next action": "assign in the next flush", "Updated": ""})
    return out


PAGE = r'''<title>FD-362 Two Clocks</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<style>
:root{--bg:#f7f6f2;--panel:#fff;--ink:#26312f;--faint:#67746f;--line:#d8d5cc;--data:#0e7d78;--ask:#c98a1b;--move:#2e9e57;--bad:#b4453b;--tint:rgba(14,125,120,.08);--sans:"Libre Franklin",-apple-system,system-ui,sans-serif;--mono:ui-monospace,Menlo,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#171d1c;--panel:#1f2725;--ink:#e6e8e4;--faint:#9aa5a0;--line:#39443f;--tint:rgba(14,125,120,.2)}}
:root[data-theme="dark"]{--bg:#171d1c;--panel:#1f2725;--ink:#e6e8e4;--faint:#9aa5a0;--line:#39443f;--tint:rgba(14,125,120,.2)}
body{background:var(--bg);color:var(--ink);font:14px/1.45 var(--sans);margin:0;height:100vh;display:grid;grid-template-rows:auto auto 1fr;overflow:hidden}
header{display:flex;align-items:center;gap:14px;padding:10px 16px;border-bottom:1px solid var(--line);background:var(--panel)}
header h1{font:600 16px var(--sans);margin:0 14px 0 0}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:16px;overflow:hidden}.seg button{border:0;background:none;padding:5px 12px;font:500 13px var(--sans);color:var(--faint);cursor:pointer}.seg button.on{background:var(--data);color:#fff}
.filters{display:flex;gap:10px;align-items:center;padding:6px 16px;border-bottom:1px solid var(--line);font:12px var(--mono);color:var(--faint);flex-wrap:wrap}
.filters label{display:inline-flex;gap:4px;align-items:center;cursor:pointer}.filters input[type=search]{margin-left:auto;font:13px var(--sans);padding:4px 10px;border:1px solid var(--line);border-radius:14px;background:var(--panel);color:var(--ink);min-width:220px}
main{display:grid;grid-template-columns:1fr 380px;min-height:0}
#stage{overflow:auto;position:relative}svg{display:block}
#detail{border-left:1px solid var(--line);background:var(--panel);padding:14px 16px;overflow:auto;font-size:13.5px}
#detail h3{font:600 14px var(--sans);margin:0 0 6px}#detail .k{font:11px var(--mono);color:var(--faint);letter-spacing:.06em;text-transform:uppercase;margin:10px 0 2px}#detail a{color:var(--data)}
.lane-label{font:500 12px var(--sans);fill:var(--ink)}.lane-sub{font:11px var(--mono);fill:var(--faint)}.axis text{font:11px var(--mono);fill:var(--faint)}.axis line,.axis path{stroke:var(--line)}
.branch{fill:none;stroke:var(--line);stroke-width:1.5}.spine{stroke:var(--data);stroke-width:2}
.node{cursor:pointer;stroke:var(--panel);stroke-width:1}.node.dim{opacity:.15}.node.sel{stroke:var(--ink);stroke-width:2}
.state{font-size:13.5px}.state .blk{border:1px solid var(--line);border-radius:12px;background:var(--panel);padding:12px 16px;margin:10px 16px}.state .blk h3{margin:0 0 4px;font:600 15px var(--sans)}.state .blk .st{color:var(--faint);font-size:12.5px;margin-bottom:6px}.state .blk .k{font:11px var(--mono);color:var(--faint);letter-spacing:.06em;text-transform:uppercase;margin:8px 0 2px}.state .cnt{font:12px var(--mono);color:var(--data);margin-left:8px}
.legend{display:inline-flex;gap:10px;align-items:center}.legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:3px}
.tree .lbl{font:12px var(--sans);fill:var(--ink)}.tree .lbl.sess{font:11px var(--mono);fill:var(--faint)}.tree .link{fill:none;stroke:var(--line);stroke-width:1.2}
</style>
<header><h1>FD-362 · two clocks</h1>
<span class="seg" id="clock"><button class="on" data-v="event">Event clock</button><button data-v="state">State clock</button></span>
<span class="seg" id="shape"><button class="on" data-s="river">River</button><button data-s="tree">Tree</button></span>
<span class="legend" id="legend"></span>
<span style="margin-left:auto;font:12px var(--mono);color:var(--faint)" id="counts"></span></header>
<div class="filters" id="filters"></div>
<main><div id="stage"></div><aside id="detail"><h3>Pick anything</h3><p style="color:var(--faint)">A dot is one event: a ruling, a correction, a build, an artifact, a review finding, a decision, or a session's history entry. A lane is a topic; it begins where its first event is. Click a dot for its words and where it lives; click a lane name for its state block.</p></aside></main>
<script>
const EVENTS = __EVENTS__;
const TOPICS = __TOPICS__;
const KIND = {ruling:{c:"#0e7d78",s:"circle",l:"ruling"},defect:{c:"#b4453b",s:"circle",l:"defect ruling"},decision:{c:"#5b4fc4",s:"diamond",l:"decision"},history:{c:"#26312f",s:"square",l:"session entry"},review:{c:"#c98a1b",s:"circle",l:"review finding"},build:{c:"#8f9a95",s:"circle",l:"build (commit)"},artifact:{c:"#2e9e57",s:"square",l:"artifact"}};
const state = {clock:"event", shape:"river", kinds:new Set(Object.keys(KIND)), q:"", sel:null};
const parse = d3.timeParse("%Y-%m-%d");
EVENTS.forEach(e => { e.t = parse(e.date) || null; });
const laneOrder = TOPICS.map(t => t.id);
const byLane = id => EVENTS.filter(e => e.topics.includes(id));
document.getElementById("legend").innerHTML = Object.entries(KIND).map(([k,v]) => `<span><i style="background:${v.c}"></i>${v.l}</span>`).join("");
document.getElementById("filters").innerHTML = Object.entries(KIND).map(([k,v]) => `<label><input type="checkbox" data-k="${k}" checked> ${v.l} (${EVENTS.filter(e=>e.kind===k).length})</label>`).join("") + `<input type="search" id="q" placeholder="search words, ids, commits">`;
document.getElementById("counts").textContent = `${EVENTS.length} events · ${TOPICS.length-1} topics · ${new Set(EVENTS.map(e=>e.date).filter(Boolean)).size} days`;
document.querySelectorAll("#filters input[type=checkbox]").forEach(cb => cb.addEventListener("change", () => { cb.checked ? state.kinds.add(cb.dataset.k) : state.kinds.delete(cb.dataset.k); draw(); }));
document.getElementById("q").addEventListener("input", ev => { state.q = ev.target.value.toLowerCase(); draw(); });
document.querySelectorAll("#clock button").forEach(b => b.addEventListener("click", () => { document.querySelectorAll("#clock button").forEach(x=>x.classList.remove("on")); b.classList.add("on"); state.clock = b.dataset.v; draw(); }));
document.querySelectorAll("#shape button").forEach(b => b.addEventListener("click", () => { document.querySelectorAll("#shape button").forEach(x=>x.classList.remove("on")); b.classList.add("on"); state.shape = b.dataset.s; draw(); }));
const visible = e => state.kinds.has(e.kind) && (!state.q || (e.title+" "+e.text+" "+e.id).toLowerCase().includes(state.q));
const esc = s => (s||"").replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
function showEvent(e){ state.sel = e.id; const t = TOPICS.filter(x=>e.topics.includes(x.id)).map(x=>x.name).join(" · ");
  document.getElementById("detail").innerHTML = `<h3>${esc(e.title)}</h3><div class="k">${KIND[e.kind].l}${e.status?" · "+esc(e.status):""}</div><div>${e.date||"undated"}${e.session?" · "+esc(e.session):""}</div><div class="k">topic</div><div>${esc(t)}</div><div class="k">words</div><div>${esc(e.text).replace(/(https?:\/\/\S+)/g,'<a href="$1" target="_blank">$1</a>')}</div>${e.supersedes&&e.supersedes.length?`<div class="k">supersedes / superseded</div><div>${e.supersedes.join(", ")}</div>`:""}${e.commit?`<div class="k">fixed in</div><div>${e.commit}</div>`:""}<div class="k">source</div><div>${esc(e.source)}</div>`; draw(); }
function showTopic(t){ const evs = byLane(t.id); const k = {}; evs.forEach(e=>k[e.kind]=(k[e.kind]||0)+1);
  document.getElementById("detail").innerHTML = `<h3>${esc(t.name)}</h3><div class="k">status</div><div>${esc(t.Status)}</div><div class="k">decided</div><div>${esc(t.Decided)}</div><div class="k">open</div><div>${esc(t.Open)}</div><div class="k">lives in</div><div>${esc(t["Lives in"]).replace(/(https?:\/\/\S+)/g,'<a href="$1" target="_blank">$1</a>')}</div><div class="k">next action</div><div>${esc(t["Next action"])}</div><div class="k">events</div><div>${evs.length} — ${Object.entries(k).map(([a,b])=>`${b} ${KIND[a].l}`).join(", ")}</div>`; }
function draw(){ const stage = document.getElementById("stage"); stage.innerHTML = "";
  if (state.clock === "state") return drawState(stage);
  state.shape === "river" ? drawRiver(stage) : drawTree(stage); }
function drawRiver(stage){
  const dated = EVENTS.filter(e=>e.t); const W = Math.max(stage.clientWidth, 1400), L = 210, R = 30, rowH = 64, top = 44;
  const x = d3.scaleTime().domain(d3.extent(dated, e=>e.t)).range([L, W-R]).nice();
  const H = top + laneOrder.length*rowH + 20;
  const svg = d3.select(stage).append("svg").attr("width", W).attr("height", H);
  svg.append("g").attr("class","axis").attr("transform",`translate(0,${top-14})`).call(d3.axisTop(x).ticks(d3.timeDay.every(2)).tickFormat(d3.timeFormat("%b %d")));
  const days = Array.from(new Set(dated.map(e=>e.date))).sort();
  days.forEach((d,i)=>{ if(i%2) svg.append("rect").attr("x",x(parse(d))-6).attr("y",top-2).attr("width",12).attr("height",H-top).attr("fill","var(--tint)"); });
  // the spine: the first idea, at the far left, from which lanes branch
  const first = d3.min(dated, e=>e.t);
  svg.append("line").attr("class","spine").attr("x1",x(first)).attr("x2",x(first)).attr("y1",top).attr("y2",H-20);
  laneOrder.forEach((id,i)=>{ const t = TOPICS.find(t=>t.id===id); const evs = byLane(id).filter(e=>e.t); const y = top + i*rowH + rowH/2;
    const start = evs.length ? d3.min(evs,e=>e.t) : first;
    svg.append("path").attr("class","branch").attr("d", `M${x(first)},${top}C${x(first)},${y} ${x(first)+40},${y} ${x(start)},${y}L${W-R},${y}`);
    const lab = svg.append("g").attr("transform",`translate(12,${y})`).style("cursor","pointer").on("click",()=>showTopic(t));
    lab.append("text").attr("class","lane-label").attr("dy","-2").text(t.name.length>34?t.name.slice(0,33)+"…":t.name);
    lab.append("text").attr("class","lane-sub").attr("dy","13").text(`${evs.length} events`);
    // stack events that share a day within the lane
    const byDay = d3.group(evs.filter(visible), e=>e.date);
    byDay.forEach((list,day)=>{ list.sort((a,b)=>a.kind.localeCompare(b.kind)); list.forEach((e,j)=>{ const cx = x(parse(day)) + (j%6)*7 - Math.min(list.length-1,5)*3.5, cy = y - 14 + Math.floor(j/6)*9;
      const g = svg.append("g").attr("class","node"+(state.sel===e.id?" sel":"")).attr("transform",`translate(${cx},${cy})`).on("click",()=>showEvent(e));
      const c = KIND[e.kind].c; const sh = KIND[e.kind].s;
      if (sh==="circle") g.append("circle").attr("r", e.kind==="build"?2.6:4).attr("fill",c);
      else if (sh==="square") g.append("rect").attr("x",-4).attr("y",-4).attr("width",8).attr("height",8).attr("fill",c);
      else g.append("path").attr("d","M0,-5L5,0L0,5L-5,0Z").attr("fill",c);
      if (e.status && /SUPERSEDED/i.test(e.status)) g.append("line").attr("x1",-5).attr("y1",5).attr("x2",5).attr("y2",-5).attr("stroke","var(--bad)").attr("stroke-width",1.5);
      g.append("title").text(`${e.date} · ${KIND[e.kind].l}\n${e.title}`); }); }); }); }
function drawTree(stage){
  const root = {name:"Claude Code for Family Diagram — the hunch, 2026-08-28", children: laneOrder.map(id=>{ const t = TOPICS.find(t=>t.id===id); const evs = byLane(id).filter(visible);
    const days = d3.groups(evs, e=>e.date||"undated").sort((a,b)=>a[0].localeCompare(b[0]));
    return {name:t.name, topic:t, children: days.map(([d,list])=>({name:d, sess:true, children:list.map(e=>({name:e.title, ev:e}))}))}; })};
  const h = d3.hierarchy(root); h.each(n=>{ if(n.depth===3) n.children = null; });   // events are leaves
  const leaves = h.leaves().length; const H = Math.max(600, leaves*14+60), W = Math.max(stage.clientWidth, 1400);
  const tree = d3.tree().size([H-40, W-560]); tree(h);
  const svg = d3.select(stage).append("svg").attr("width", W).attr("height", H).append("g").attr("transform","translate(220,20)").attr("class","tree");
  svg.selectAll("path").data(h.links()).join("path").attr("class","link").attr("d", d3.linkHorizontal().x(d=>d.y).y(d=>d.x));
  const n = svg.selectAll("g").data(h.descendants()).join("g").attr("transform",d=>`translate(${d.y},${d.x})`).style("cursor","pointer")
    .on("click",(ev,d)=>{ if(d.data.ev) showEvent(d.data.ev); else if(d.data.topic) showTopic(d.data.topic); });
  n.filter(d=>!d.data.ev).append("circle").attr("r",d=>d.depth===0?6:4).attr("fill",d=>d.depth===0?"var(--data)":"var(--line)");
  n.filter(d=>d.data.ev).append("circle").attr("r",3.5).attr("fill",d=>KIND[d.data.ev.kind].c).attr("class",d=>"node"+(state.sel===d.data.ev.id?" sel":""));
  n.append("text").attr("class",d=>"lbl"+(d.data.sess?" sess":"")).attr("dx",d=>d.data.ev?7:-8).attr("dy",3).attr("text-anchor",d=>d.data.ev?"start":"end").text(d=>d.data.ev?(d.data.name.length>70?d.data.name.slice(0,69)+"…":d.data.name):d.data.name); }
function drawState(stage){ const div = document.createElement("div"); div.className="state";
  div.innerHTML = TOPICS.map(t=>{ const evs = byLane(t.id); return `<div class="blk"><h3>${esc(t.name)}<span class="cnt">${evs.length} events</span></h3><div class="st">${esc(t.Status)}</div>${t.Decided?`<div class="k">decided</div><div>${esc(t.Decided)}</div>`:""}${t.Open?`<div class="k">open</div><div>${esc(t.Open)}</div>`:""}${t["Next action"]?`<div class="k">next action</div><div>${esc(t["Next action"])}</div>`:""}</div>`; }).join("");
  stage.appendChild(div); div.querySelectorAll(".blk").forEach((b,i)=>b.addEventListener("click",()=>showTopic(TOPICS[i]))); }
draw();
</script>
'''


def main(out: str) -> int:
    events = json.loads((DOC / "events.json").read_text())
    page = PAGE.replace("__EVENTS__", json.dumps(events, ensure_ascii=False)).replace("__TOPICS__", json.dumps(topic_blocks(), ensure_ascii=False))
    Path(out).write_text(page)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
