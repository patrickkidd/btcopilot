"""Render the FD-362 dashboard as one thought-and-decision trace: every statement the
owner made, in the order he made it, with each piece of work drawn as its own horizontal
line and his trace stepping between them.

Statements come from doc/chat-first/trace.json (written by bin/trace.py); what followed
each statement comes from doc/chat-first/events.json; the second view is the topic
register from TOPICS.md.

  python bin/tracepage.py <out.html>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eventpage import topic_blocks  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
DOC = HERE / "doc" / "chat-first"
COLORS = {
    "T-1": "#0e7d78", "T-2": "#c98a1b", "T-3": "#7a5cc4", "T-4": "#b8555f",
    "T-5": "#2e9e57", "T-6": "#2f7fb5", "T-7": "#b4453b", "T-8": "#8a6d3b",
    "T-9": "#8b9792", "unplaced": "#a9b0ad",
}
FOLLOW_KINDS = ("ruling", "defect", "decision", "build", "artifact", "review", "history")


def threads(statements: list[dict], topics: list[dict]) -> list[dict]:
    names = {t["id"]: t["name"] for t in topics}
    names["unplaced"] = "Not yet assigned to a piece of work"
    order, seen = [], set()
    for s in statements:
        if s["thread"] not in seen:
            seen.add(s["thread"])
            order.append(s["thread"])
    return [
        {"id": t, "name": names.get(t, t), "color": COLORS.get(t, "#8b9792")}
        for t in order
    ]


def bands(statements: list[dict]) -> list[dict]:
    """One band per day. Several sittings can run on the same day, so the label names them."""
    out = []
    for i, s in enumerate(statements):
        day = s["time"][:10]
        if out and out[-1]["day"] == day:
            out[-1]["to"] = i
            out[-1]["titles"].add(s["session_title"] or s["session"])
            continue
        out.append({"day": day, "from": i, "to": i, "titles": {s["session_title"] or s["session"]}})
    for band in out:
        titles = sorted(band.pop("titles"))
        band["label"] = f"{band['day']} · " + ", ".join(t[:34] for t in titles[:3])
    return out


def followed(statements: list[dict], events: list[dict]) -> dict:
    """Events in the same piece of work, from a statement's day up to his next statement there."""
    by_thread = {}
    for i, s in enumerate(statements):
        by_thread.setdefault(s["thread"], []).append(i)
    usable = [e for e in events if e.get("date") and e["kind"] in FOLLOW_KINDS]
    out = {}
    for thread, idx in by_thread.items():
        tagged = sorted(
            (e for e in usable if thread in (e.get("topics") or [])),
            key=lambda e: e["date"],
        )
        for n, i in enumerate(idx):
            start = statements[i]["time"][:10]
            end = statements[idx[n + 1]]["time"][:10] if n + 1 < len(idx) else "9999-12-31"
            hits = [e for e in tagged if start <= e["date"] < end or (end == start == e["date"])]
            if hits:
                out[statements[i]["id"]] = [
                    {"k": e["kind"], "l": e["title"][:120], "d": e["date"], "id": e["id"],
                     "link": e.get("link") or "", "commit": e.get("commit") or ""}
                    for e in hits[:12]
                ]
    return out


PAGE = r'''<title>FD-362 Thought Trace</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<style>
:root{--bg:#f7f6f2;--panel:#fff;--ink:#26312f;--faint:#67746f;--line:#d8d5cc;--data:#0e7d78;--ask:#c98a1b;--band:rgba(38,49,47,.05);--tint:rgba(14,125,120,.08);--shadow:rgba(38,49,47,.14);--sans:"Libre Franklin",-apple-system,system-ui,sans-serif;--mono:ui-monospace,Menlo,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#171d1c;--panel:#1f2725;--ink:#e6e8e4;--faint:#9aa5a0;--line:#39443f;--band:rgba(230,232,228,.05);--tint:rgba(14,125,120,.2);--shadow:rgba(0,0,0,.45)}}
:root[data-theme="dark"]{--bg:#171d1c;--panel:#1f2725;--ink:#e6e8e4;--faint:#9aa5a0;--line:#39443f;--band:rgba(230,232,228,.05);--tint:rgba(14,125,120,.2);--shadow:rgba(0,0,0,.45)}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font:14px/1.45 var(--sans);margin:0;height:100vh;display:grid;grid-template-rows:auto auto 1fr;overflow:hidden}
header{display:flex;align-items:center;gap:10px;padding:10px 16px;border-bottom:1px solid var(--line);background:var(--panel);flex-wrap:wrap}
header h1{font:600 16px var(--sans);margin:0 8px 0 0}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:16px;overflow:hidden}
.seg button{border:0;background:none;padding:5px 12px;font:500 13px var(--sans);color:var(--faint);cursor:pointer}
.seg button.on{background:var(--data);color:#fff}
button.plain{font:500 13px var(--sans);color:var(--faint);background:none;border:1px solid var(--line);border-radius:16px;padding:5px 12px;cursor:pointer}
button.plain:hover{border-color:var(--faint)}
input[type=search]{font:13px var(--sans);padding:5px 11px;border:1px solid var(--line);border-radius:14px;background:var(--bg);color:var(--ink);min-width:210px}
.count{font:12px var(--mono);color:var(--faint);margin-left:auto}
#caption{padding:7px 16px;border-bottom:1px solid var(--line);color:var(--faint);font-size:12.5px}
main{display:grid;grid-template-columns:1fr 380px;min-height:0}
#stage{overflow:hidden;position:relative;min-width:0}
#state{overflow:auto;padding:14px 18px 60px;display:none}
#state .blk{border-top:1px solid var(--line);padding:12px 0 6px;max-width:80ch}
#state h3{font:600 15px var(--sans);margin:0 0 4px}
#state .k{font:11px var(--mono);color:var(--faint);letter-spacing:.06em;text-transform:uppercase;margin:8px 0 1px}
#detail{border-left:1px solid var(--line);background:var(--panel);padding:14px 16px;overflow:auto;font-size:13.5px}
#detail h3{font:600 15px var(--sans);margin:0 0 6px;line-height:1.25}
#detail .k{font:11px var(--mono);color:var(--faint);letter-spacing:.06em;text-transform:uppercase;margin:12px 0 3px}
#detail a{color:var(--data)}
#detail details{border:1px solid var(--line);border-radius:9px;padding:9px 11px;margin:10px 0 4px}
#detail summary{cursor:pointer;font-size:13px;color:var(--faint)}
#detail blockquote{margin:9px 0 0;padding-left:11px;border-left:3px solid var(--line);white-space:pre-wrap;font-size:13.5px}
#detail ul{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:7px}
#detail ul li{font-size:12.5px;border:1px solid var(--line);border-radius:999px;padding:3px 10px}
#detail ul .kk{font:10.5px var(--mono);color:var(--faint);text-transform:uppercase;letter-spacing:.05em;margin-right:6px}
#detail .sw{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
svg{display:block;touch-action:none;cursor:grab;width:100%;height:100%}
svg:active{cursor:grabbing}
text{font-family:var(--sans)}
.num,.lane-name,.date{font-family:var(--mono)}
.node-name{fill:var(--ink);font-weight:600}
.num{fill:var(--faint);font-size:10.5px}
.date{fill:var(--faint);font-size:11px}
.lane-name{fill:var(--ink);font-size:12.5px}
.band{fill:var(--band)}
.trace{fill:none;stroke:var(--ink);stroke-width:1.6;opacity:.75;stroke-linecap:round}
.hit{cursor:pointer}
.hit.dim{opacity:.12}
.hit.sel .dot{stroke-width:5}
#tip{position:absolute;pointer-events:none;background:var(--panel);border:1px solid var(--line);border-radius:8px;
  box-shadow:0 6px 18px var(--shadow);padding:8px 10px;max-width:330px;font-size:12.5px;display:none;z-index:5}
#tip b{display:block;font-size:13px;margin-bottom:3px}
#tip span{color:var(--faint)}
</style>
<header><h1>FD-362 · one line of thought</h1>
<span class="seg" id="mode"><button class="on" data-v="trace">The trace</button><button data-v="state">Where it stands</button></span>
<button class="plain" id="fit">Fit</button>
<button class="plain" id="read">Zoom in to read</button>
<input type="search" id="q" placeholder="search his words">
<button class="plain" id="theme">Light / dark</button>
<span class="count" id="counts"></span></header>
<div id="caption">There is one person working, so there is one line of thought through time. Each coloured line is a piece of work he keeps coming back to; the dark line is him, moving between them. Every mark is one thing he said. Point at a mark for its one-line summary, click it for his own words and what followed. Drag to move, scroll to zoom.</div>
<main><div id="stage"><svg id="svg"></svg><div id="tip"></div></div><div id="state"></div><aside id="detail"></aside></main>
<script>
const STATEMENTS = __STATEMENTS__;
const THREADS = __THREADS__;
const BANDS = __BANDS__;
const AFTER = __AFTER__;
const TOPICS = __TOPICS__;
const KIND = {ruling:"ruling",defect:"correction",decision:"decision",history:"session entry",review:"review finding",build:"commit",artifact:"artifact"};
const T = Object.fromEntries(THREADS.map(t => [t.id, t]));
const esc = s => (s||"").replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const linkify = s => esc(s).replace(/(https?:\/\/\S+)/g, '<a href="$1" target="_blank">$1</a>');
const clip = (s,n) => (s||"").length > n ? s.slice(0,n-1).trimEnd()+"…" : (s||"");

const DX = 64, LANE_H = 78, LEFT = 250, TOP = 74, PAD = 150;
const laneY = {}; THREADS.forEach((t,i) => laneY[t.id] = TOP + i*LANE_H);
const x = i => LEFT + i*DX;
const W = LEFT + STATEMENTS.length*DX + PAD;
const H = TOP + THREADS.length*LANE_H + 70;

const svg = d3.select("#svg");
const root = svg.append("g");
const gBands = root.append("g"), gLanes = root.append("g"), gTrace = root.append("g"), gNodes = root.append("g");

/* session bands, one per stretch of statements from the same session on the same day */
BANDS.forEach((b,i) => {
  const x0 = x(b.from) - DX/2, x1 = x(b.to) + DX/2;
  if (i % 2) gBands.append("rect").attr("class","band").attr("x",x0).attr("y",44).attr("width",x1-x0).attr("height",H-70).attr("rx",7);
  gBands.append("line").attr("x1",x0).attr("x2",x0).attr("y1",44).attr("y2",H-26).style("stroke","var(--line)").style("stroke-width",1);
});

/* one line per piece of work, from its first statement to its last */
THREADS.forEach(t => {
  const idx = STATEMENTS.map((s,i) => s.thread === t.id ? i : -1).filter(i => i >= 0);
  gLanes.append("line").attr("x1",x(idx[0])).attr("x2",x(idx[idx.length-1]))
    .attr("y1",laneY[t.id]).attr("y2",laneY[t.id])
    .style("stroke",t.color).style("stroke-width",6).style("opacity",.3).attr("stroke-linecap","round");
  t.said = idx.length;
});

/* the name of each piece of work stays at the left edge, and the date at the top, while you pan */
const pinned = svg.append("g").attr("class","pinned");
const laneTags = pinned.selectAll("g.lane").data(THREADS).enter().append("g").attr("class","lane");
laneTags.append("rect").attr("x",0).attr("y",-13).attr("width",214).attr("height",30).attr("fill","var(--bg)").attr("opacity",.88);
laneTags.append("circle").attr("cx",10).attr("cy",0).attr("r",4.5).style("fill",t => t.color);
laneTags.append("text").attr("class","lane-name").attr("x",22).attr("y",4).text(t => clip(t.name,32));
laneTags.append("text").attr("class","num").attr("x",22).attr("y",16).text(t => t.said + " said");
const dayTags = pinned.selectAll("g.day").data(BANDS).enter().append("g").attr("class","day");
dayTags.append("text").attr("class","date").attr("x",6).attr("y",13).text(b => b.label);

/* his single trace, stepping from line to line */
let d = "";
STATEMENTS.forEach((s,i) => {
  const px = x(i), py = laneY[s.thread];
  if (!i) { d += `M${px},${py}`; return; }
  const qx = x(i-1), qy = laneY[STATEMENTS[i-1].thread];
  d += (qy === py) ? ` L${px},${py}` : ` C${qx+DX*.45},${qy} ${px-DX*.45},${py} ${px},${py}`;
});
gTrace.append("path").attr("class","trace").attr("d",d);

/* one mark per statement, name above or below its line */
const nodes = gNodes.selectAll("g").data(STATEMENTS).enter().append("g")
  .attr("class","hit").attr("data-id",s => s.id)
  .on("click", (e,s) => select(s))
  .on("mousemove", (e,s) => tip(e,s))
  .on("mouseleave", hideTip);
nodes.append("rect").attr("x",(s,i) => x(i)-DX/2).attr("y",s => laneY[s.thread]-40)
  .attr("width",DX).attr("height",80).attr("fill","transparent");
nodes.append("circle").attr("class","dot").attr("cx",(s,i) => x(i)).attr("cy",s => laneY[s.thread]).attr("r",5.5)
  .style("fill","var(--panel)").style("stroke",s => T[s.thread].color).style("stroke-width",3);
const labels = nodes.append("text").attr("class","node-name labelled")
  .attr("x",(s,i) => x(i)).attr("text-anchor","middle").style("font-size","12px")
  .attr("y",(s,i) => laneY[s.thread] + (i % 2 ? 24 : -16));
labels.each(function(s){ wrap(d3.select(this), s.name, DX+30, 13, 2); });

function wrap(sel, text, width, lh, maxLines){
  const words = (text||"").split(/\s+/).reverse();
  let line = [], lineNo = 0;
  let tspan = sel.append("tspan").attr("x", sel.attr("x")).attr("dy", 0);
  let word;
  while ((word = words.pop())){
    line.push(word);
    tspan.text(line.join(" "));
    if (tspan.node().getComputedTextLength() > width && line.length > 1){
      line.pop(); tspan.text(line.join(" "));
      if (++lineNo >= maxLines){ tspan.text(tspan.text()+"…"); return; }
      line = [word];
      tspan = sel.append("tspan").attr("x", sel.attr("x")).attr("dy", lh).text(word);
    }
  }
}

/* pan and zoom: never further out than the whole trace, never closer than six times */
let fitK = 1, fit = d3.zoomIdentity;
const zoom = d3.zoom().on("zoom", e => {
  root.attr("transform", e.transform);
  gNodes.selectAll(".labelled").style("display", e.transform.k < .42 ? "none" : null);
  repin(e.transform);
});
function repin(tr){
  const box = document.getElementById("stage").getBoundingClientRect();
  laneTags.attr("transform", t => `translate(4,${tr.applyY(laneY[t.id])})`)
    .style("display", t => { const y = tr.applyY(laneY[t.id]); return y < 24 || y > box.height - 8 ? "none" : null; });
  dayTags.attr("transform", b => `translate(${Math.max(tr.applyX(x(b.from) - DX/2), 258)},2)`)
    .style("display", b => {
      const a = tr.applyX(x(b.from)), z = tr.applyX(x(b.to));
      return z < 0 || a > box.width || (z - a) < 80 ? "none" : null;
    });
}
function sizeView(){
  const box = document.getElementById("stage").getBoundingClientRect();
  fitK = Math.min(box.width / W, box.height / H);
  fit = d3.zoomIdentity.translate((box.width - W*fitK)/2, (box.height - H*fitK)/2).scale(fitK);
  zoom.scaleExtent([fitK, 6]).translateExtent([[-40,-40],[W+40,H+40]]);
  svg.call(zoom);
}
function latest(){
  const box = document.getElementById("stage").getBoundingClientRect();
  const k = Math.max(Math.min(box.height / H, 1.1), fitK);
  return d3.zoomIdentity.translate(box.width - 90 - x(STATEMENTS.length-1)*k, (box.height - H*k)/2).scale(k);
}
sizeView();
svg.call(zoom.transform, latest());
window.addEventListener("resize", () => { sizeView(); svg.call(zoom.transform, latest()); });
document.getElementById("fit").onclick = () => svg.transition().duration(300).call(zoom.transform, fit);
document.getElementById("read").onclick = () => {
  const s = STATEMENTS.findIndex(x2 => x2.id === sel_id);
  const i = s >= 0 ? s : 0;
  const box = document.getElementById("stage").getBoundingClientRect();
  const k = 1.4;
  svg.transition().duration(350).call(zoom.transform,
    d3.zoomIdentity.translate(box.width/2 - x(i)*k, box.height/2 - laneY[STATEMENTS[i].thread]*k).scale(k));
};

/* hover: the one-line summary */
const tipEl = document.getElementById("tip");
function tip(e, s){
  const box = document.getElementById("stage").getBoundingClientRect();
  tipEl.innerHTML = `<b>${esc(s.name)}</b>${esc(s.summary)}<span> · ${esc(T[s.thread].name)} · ${esc(s.time.slice(0,16).replace("T"," "))}</span>`;
  tipEl.style.display = "block";
  tipEl.style.left = Math.min(e.clientX - box.left + 14, box.width - 350) + "px";
  tipEl.style.top = Math.min(e.clientY - box.top + 14, box.height - 90) + "px";
}
function hideTip(){ tipEl.style.display = "none"; }

/* click: his own words and what followed */
let sel_id = null;
function select(s){
  sel_id = s.id;
  gNodes.selectAll(".hit").classed("sel", n => n.id === s.id);
  const n = STATEMENTS.indexOf(s) + 1;
  const after = AFTER[s.id] || [];
  document.getElementById("detail").innerHTML =
    `<div class="k">statement ${n} of ${STATEMENTS.length}</div><h3>${esc(s.name)}</h3>`
    + `<div><span class="sw" style="background:${T[s.thread].color}"></span>${esc(T[s.thread].name)}</div>`
    + `<div class="k">when</div><div>${esc(s.time.slice(0,16).replace("T"," "))} · ${esc(s.session_title || s.session)}</div>`
    + `<div class="k">what he asked for</div><div>${esc(s.summary)}</div>`
    + `<details><summary>His words</summary><blockquote>${esc(s.text)}</blockquote></details>`
    + `<div class="k">what followed</div>`
    + (after.length
        ? `<ul>${after.map(a => `<li><span class="kk">${esc(KIND[a.k]||a.k)}</span>${esc(clip(a.l,90))}${a.d?` <span style="color:var(--faint)">${esc(a.d)}</span>`:""}</li>`).join("")}</ul>`
        : `<div style="color:var(--faint)">nothing recorded in this piece of work between here and the next thing he said about it</div>`);
}

/* search dims the rest */
document.getElementById("q").addEventListener("input", ev => {
  const q = ev.target.value.trim().toLowerCase();
  gNodes.selectAll(".hit").classed("dim", s => q && !(s.name+" "+s.summary+" "+s.text).toLowerCase().includes(q));
});

/* the two views */
document.querySelectorAll("#mode button").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll("#mode button").forEach(x2 => x2.classList.remove("on"));
  b.classList.add("on");
  const trace = b.dataset.v === "trace";
  document.getElementById("stage").style.display = trace ? "" : "none";
  document.getElementById("state").style.display = trace ? "none" : "block";
  document.getElementById("caption").textContent = trace
    ? "There is one person working, so there is one line of thought through time. Each coloured line is a piece of work he keeps coming back to; the dark line is him, moving between them. Point at a mark for its summary, click it for his words."
    : "Where each piece of work stands right now: what is settled, what is still open, and the next thing to do.";
  if (trace) { sizeView(); svg.call(zoom.transform, latest()); }
}));
document.getElementById("state").innerHTML = TOPICS.map(t =>
  `<div class="blk"><h3>${esc(t.name)}</h3>`
  + `<div class="k">status</div><div>${esc(t.Status)}</div>`
  + (t.Decided ? `<div class="k">settled</div><div>${esc(t.Decided)}</div>` : "")
  + (t.Open ? `<div class="k">still open</div><div>${esc(t.Open)}</div>` : "")
  + (t["Next action"] ? `<div class="k">next</div><div>${esc(t["Next action"])}</div>` : "")
  + (t["Lives in"] ? `<div class="k">lives in</div><div>${linkify(t["Lives in"])}</div>` : "")
  + `</div>`).join("");

document.getElementById("theme").onclick = () => {
  const cur = document.documentElement.getAttribute("data-theme");
  const dark = cur ? cur === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.setAttribute("data-theme", dark ? "light" : "dark");
};
document.getElementById("counts").textContent =
  `${STATEMENTS.length} statements · ${THREADS.length} pieces of work · ${BANDS.length} sittings`;
document.getElementById("detail").innerHTML =
  `<h3>His own line of thought</h3><p style="color:var(--faint)">Every mark is one thing he typed, in order. `
  + `A mark sits on the line of the piece of work it belongs to, so a jump up or down is him changing what he was working on. `
  + `Click any mark for his words and for the rulings, commits and findings that came after it in that same piece of work.</p>`;
select(STATEMENTS[STATEMENTS.length-1]);
</script>
'''


def main(out: str) -> int:
    statements = json.loads((DOC / "trace.json").read_text())
    events = json.loads((DOC / "events.json").read_text())
    topics = topic_blocks()
    lanes = threads(statements, topics)
    slim = [
        {k: s[k] for k in ("id", "time", "session", "session_title", "thread", "name", "summary", "text")}
        for s in statements
    ]
    page = (
        PAGE.replace("__STATEMENTS__", json.dumps(slim, ensure_ascii=False))
        .replace("__THREADS__", json.dumps(lanes, ensure_ascii=False))
        .replace("__BANDS__", json.dumps(bands(statements)))
        .replace("__AFTER__", json.dumps(followed(statements, events), ensure_ascii=False))
        .replace("__TOPICS__", json.dumps(topics, ensure_ascii=False))
    )
    Path(out).write_text(page)
    print(f"{out}: {len(slim)} statements, {len(lanes)} pieces of work, {len(bands(statements))} sittings")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
