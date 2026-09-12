"""Render the FD-362 dashboard as one thought-and-decision trace: every statement the
owner made, in the order he made it, with each piece of work drawn as its own horizontal
line and his trace stepping between them.

Zooming changes what a lane shows, not how far away it is: the whole project as seven
story arcs, then the sessions inside an arc, then his single statements, then a summary
under each one.

Statements come from doc/chat-first/trace.json (written by bin/trace.py); the arcs from
doc/chat-first/arcs.json; the sessions and what followed each statement from
doc/chat-first/events.json; the second view is the topic register from TOPICS.md.

  python bin/tracepage.py <out.html>
"""
import json
import re
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
DATED = re.compile(r"^\d{4}-\d{2}-\d{2}[^—]*—\s*")
TAGS = ("ruling", "build", "verify", "waiting")
RULING_ID = re.compile(r"\[(?:Oracle:\s*)?(R-\d+(?:\s*,\s*R-\d+)*)[^\]]*\]")
TOPIC_ID = re.compile(r"\[T-\d+(?:\s*,\s*T-\d+)*\]")
URL = re.compile(r"\(?\bhttps?://[^\s)]+\)?")


def sentence(text: str) -> str:
    """One open item or one settled bullet, as a plain sentence with no ids and no links."""
    t = URL.sub("", TOPIC_ID.sub("", RULING_ID.sub("", text)))
    t = re.sub(r"\(\s*[,;:]?\s*\)", "", t)
    t = " ".join(t.split()).strip(" ;,·—-")
    if t and t[0].islower():
        t = t[0].upper() + t[1:]
    return t + "." if t and t[-1] not in ".?!" else t


def tagged_items(field: str) -> list[tuple[str, str]]:
    """The numbered items of an Open field, each as (tag, its words)."""
    field = " ".join((field or "").split())
    if not field or field.rstrip(".").lower() == "none":
        return []
    parts = re.split(r"\(\d+\)\s*", field)
    out = []
    for part in parts[1:] or [field]:
        m = re.match(rf"\[({'|'.join(TAGS)})\]\s*(.+)", part.strip())
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def open_rows(topics: list[dict]) -> list[dict]:
    rows = []
    for t in topics:
        if t["id"] == "untagged":
            continue
        for tag, words in tagged_items(t["Open"]):
            rows.append({"tag": tag, "text": sentence(words), "tid": t["id"], "topic": t["name"]})
    return rows


def settled(topics: list[dict]) -> list[dict]:
    """Per topic, what is decided: one bullet each, its ruling ids kept for the end of the line."""
    out = []
    for t in topics:
        if t["id"] == "untagged" or not t["Decided"]:
            continue
        bullets = []
        for part in re.split(r";\s+", t["Decided"]):
            if not part.strip():
                continue
            ids = [i for group in RULING_ID.findall(part) for i in re.split(r"\s*,\s*", group)]
            line = sentence(part)
            if line:
                bullets.append({"text": line, "rid": ", ".join(ids)})
        if bullets:
            out.append(
                {"id": t["id"], "name": t["name"],
                 "closed": "CLOSED" in t["Status"], "bullets": bullets}
            )
    out.sort(key=lambda s: not s["closed"])
    return out


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


def span(statements: list[dict], start: str, end: str) -> tuple[int, int, dict]:
    """The run of statements between two days, and how many of them each piece of work holds."""
    hits = [i for i, s in enumerate(statements) if start <= s["time"][:10] <= end]
    counted = {}
    for i in hits:
        thread = statements[i]["thread"]
        counted[thread] = counted.get(thread, 0) + 1
    return (hits[0], hits[-1], counted) if hits else (-1, -1, {})


def arcs(statements: list[dict]) -> list[dict]:
    """The story arcs, each on the piece of work it mostly lived on.

    Where two pieces of work are within a fifth of each other in an arc's days, the one that
    is not the arc before it wins, so the trace shows the story changing subject.
    """
    out, previous = [], ""
    for arc in json.loads((DOC / "arcs.json").read_text()):
        first, last, counted = span(statements, arc["start"], arc["end"])
        if first < 0:
            continue
        placed = {t: n for t, n in counted.items() if t != "unplaced"} or counted
        top = max(placed.values())
        close = sorted((t for t, n in placed.items() if n >= top * 0.8), key=lambda t: -placed[t])
        thread = next((t for t in close if t != previous), close[0])
        previous = thread
        if out:
            first = max(first, out[-1]["to"] + 1)
        out.append(
            {**arc, "from": first, "to": max(last, first), "said": sum(counted.values()), "thread": thread}
        )
    return out


def sessions(statements: list[dict], events: list[dict]) -> list[dict]:
    """One block per session entry, on every lane its entry is tagged with."""
    days = {}
    for i, s in enumerate(statements):
        day = s["time"][:10]
        days.setdefault(day, [i, i])[1] = i
    out = []
    for e in events:
        if e["kind"] != "history" or not e.get("date") or e["date"] not in days:
            continue
        first, last = days[e["date"]]
        lanes = [t for t in (e.get("topics") or []) if t in {s["thread"] for s in statements}]
        out.append(
            {"title": e["title"], "label": DATED.sub("", e["title"]), "date": e["date"],
             "text": e.get("text") or "", "from": first, "to": last,
             "lanes": lanes or ["unplaced"], "thread": (lanes or ["unplaced"])[0]}
        )
    out.sort(key=lambda s: (s["date"], s["title"]))
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
input[type=search]{font:13px var(--sans);padding:5px 11px;border:1px solid var(--line);border-radius:14px;background:var(--bg);color:var(--ink);min-width:180px}
.count{font:12px var(--mono);color:var(--faint);margin-left:auto}
#caption{padding:7px 16px;border-bottom:1px solid var(--line);color:var(--faint);font-size:12.5px}
main{display:grid;grid-template-columns:1fr 380px;min-height:0}
#stage{overflow:hidden;position:relative;min-width:0}
#state{overflow:auto;padding:14px 18px 80px;display:none}
#state .k,#detail .k{font:11px var(--mono);color:var(--faint);letter-spacing:.06em;text-transform:uppercase}
#state .k{margin:9px 0 1px}
#state section,#state details.grp,#state details.blk{max-width:none}
#state h2,#state summary .h2{font:600 17px var(--sans);margin:0;display:inline}
#state section{margin:0 0 26px}
#state .n{font:11.5px var(--mono);color:var(--faint);border:1px solid var(--line);border-radius:999px;padding:1px 7px;margin-left:7px;vertical-align:2px}
#state .sub{color:var(--faint);font-size:12.5px;margin:4px 0 9px}
#state h3.tag-h{font:600 13px var(--sans);color:var(--faint);margin:16px 0 3px}
#state .row{display:flex;gap:14px;align-items:baseline;justify-content:space-between;
  border-bottom:1px solid var(--line);padding:8px 3px;cursor:pointer}
#state .row:hover{background:var(--tint)}
#state .rtext{line-height:1.5}
#state .rtopic{font-size:11.5px;color:var(--faint);white-space:normal;flex:0 0 26ch;text-align:right}
.ldot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;vertical-align:-1px}
#state details.grp,#state details.blk{border-top:1px solid var(--line);padding:11px 0}
#state details.grp>summary,#state details.blk>summary{cursor:pointer;list-style:none}
#state details.blk>summary{font:600 15px var(--sans)}
#state details.grp>summary::-webkit-details-marker,#state details.blk>summary::-webkit-details-marker{display:none}
#state details.grp>summary::before,#state details.blk>summary::before{content:"▸ ";color:var(--faint)}
#state details[open]>summary::before{content:"▾ "}
#state .stop h3{font:600 13.5px var(--sans);margin:13px 0 2px}
#state .tag{font:10.5px var(--mono);color:var(--faint);border:1px solid var(--line);border-radius:999px;padding:1px 6px;margin-right:7px;white-space:nowrap}
#state .alltop{display:block;margin:30px 0 0}
ul.bul{margin:2px 0 0;padding-left:19px}
ul.bul li{margin:3px 0;line-height:1.5}
.rid{font:11px var(--mono);color:var(--faint);white-space:nowrap}
#detail{border-left:1px solid var(--line);background:var(--panel);padding:14px 16px;overflow:auto;font-size:13.5px}
#detail h3{font:600 15px var(--sans);margin:0 0 6px;line-height:1.25}
#detail .k{margin:12px 0 3px}
#detail a{color:var(--data)}
#detail details{border:1px solid var(--line);border-radius:9px;padding:9px 11px;margin:10px 0 4px}
#detail summary{cursor:pointer;font-size:13px;color:var(--faint)}
#detail blockquote{margin:9px 0 0;padding-left:11px;border-left:3px solid var(--line);white-space:pre-wrap;font-size:13.5px}
#detail ul.pills{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:7px}
#detail ul.pills li{font-size:12.5px;border:1px solid var(--line);border-radius:999px;padding:3px 10px}
#detail ul.pills .kk{font:10.5px var(--mono);color:var(--faint);text-transform:uppercase;letter-spacing:.05em;margin-right:6px}
#detail .sw{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
svg{display:block;touch-action:none;cursor:grab;width:100%;height:100%}
svg:active{cursor:grabbing}
text{font-family:var(--sans)}
.num,.lane-name,.date{font-family:var(--mono)}
.node-name{fill:var(--ink);font-weight:600;font-size:12px}
.node-sum{fill:var(--faint);font-size:10.5px}
.thin text.node-sum tspan:nth-child(n+2){display:none}
.num{fill:var(--faint);font-size:10.5px}
.date{fill:var(--faint);font-size:11px}
.lane-name{fill:var(--ink);font-size:12.5px}
.lane{cursor:pointer}
.lane:hover .lane-name{fill:var(--data)}
.band{fill:var(--band)}
.trace{fill:none;stroke:var(--ink);stroke-width:1.6;opacity:.75;stroke-linecap:round;stroke-linejoin:round}
.hit,.arc,.sess{cursor:pointer}
.dim{opacity:.12}
.arc rect,.sess rect{fill:var(--panel);stroke-width:2.5}
.sess rect{stroke-width:2}
.arc text{font:600 12.5px var(--sans);fill:var(--ink)}
.sess text{font:12px var(--sans);fill:var(--ink)}
.sel rect{fill:var(--tint)}
#tip{position:absolute;pointer-events:none;background:var(--panel);border:1px solid var(--line);border-radius:8px;
  box-shadow:0 6px 18px var(--shadow);padding:8px 10px;max-width:330px;font-size:12.5px;display:none;z-index:5}
#tip b{display:block;font-size:13px;margin-bottom:3px}
#tip span{color:var(--faint)}
</style>
<header><h1>FD-362 · one line of thought</h1>
<span class="seg" id="mode"><button class="on" data-v="trace">The trace</button><button data-v="state">Where it stands</button></span>
<span class="seg" id="lvl"><button data-l="1">Arcs</button><button data-l="2">Sessions</button><button data-l="3">What he said</button><button data-l="4">With summaries</button></span>
<input type="search" id="q" placeholder="search his words">
<button class="plain" id="theme">Light / dark</button>
<span class="count" id="counts"></span></header>
<div id="caption"></div>
<main><div id="stage"><svg id="svg"></svg><div id="tip"></div></div><div id="state"></div><aside id="detail"></aside></main>
<script>
const STATEMENTS = __STATEMENTS__;
const THREADS = __THREADS__;
const BANDS = __BANDS__;
const ARCS = __ARCS__;
const SESSIONS = __SESSIONS__;
const AFTER = __AFTER__;
const TOPICS = __TOPICS__;
const OPEN_ROWS = __OPENROWS__;
const SETTLED = __SETTLED__;
const TAGS_ORDER = ["ruling", "build", "verify", "waiting"];
const TAGLABEL = {ruling:"Needs your word", build:"Not built yet",
                  verify:"Built but never checked", waiting:"Blocked on something else"};
const KIND ={ruling:"ruling",defect:"correction",decision:"decision",history:"session entry",review:"review finding",build:"commit",artifact:"artifact"};
const T = Object.fromEntries(THREADS.map(t => [t.id, t]));
const TOPIC = Object.fromEntries(TOPICS.map(t => [t.id, t]));
const esc = s => (s||"").replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const linkify = s => esc(s).replace(/(https?:\/\/\S+)/g, '<a href="$1" target="_blank">$1</a>');
const clip = (s,n) => (s||"").length > n ? s.slice(0,n-1).trimEnd()+"…" : (s||"");
const day = s => (s||"").slice(0,10);

/* the drawing is in screen pixels and is redrawn as you zoom, so a label never changes size
   and the lanes keep their spacing however far out you are */
const DX = 64, NAME_W = 124, SUM_W = 190, NAME_LH = 13, SUM_LH = 12, SUM_LINES = 2;
const WX = Math.max((STATEMENTS.length-1)*DX, 1);
const CAPTION = {
  1: "The whole project, start to finish, as seven story arcs. The dark line is him moving from arc to arc, so a curve up or down is the story changing what it was about.",
  2: "Each arc has opened into its sessions: one block per session entry, on every piece of work that session touched.",
  3: "Every mark is one thing he typed, in his own words, on the line of the piece of work it belongs to.",
  4: "Every mark carries the start of what he said under his words. Click a mark for the whole thing and for what followed it."
};
let stageW = 0, stageH = 0, GUTTER = 250, TOPY = 74, LANE_H = 78;
let K_FIT = .02, K_SESS = .2, K_STMT = 1, K_SUM = 3, K_MAX = 5, level = 0;
let NAME_PX = NAME_W, SUM_PX = SUM_W, SUM_ROOM = SUM_LINES, selKind = "", selId = "";
let shownA = 0, shownB = STATEMENTS.length - 1;   /* the run of marks on screen right now */
const laneY = {};

const stage = document.getElementById("stage");
const caption = document.getElementById("caption");
const svg = d3.select("#svg");
const gBands = svg.append("g"), gLanes = svg.append("g"), gTrace = svg.append("g");
const gArcs = svg.append("g"), gSess = svg.append("g"), gNodes = svg.append("g");
const pinned = svg.append("g");

/* Every label is measured once, on a canvas, and the width kept. Asking the drawing itself
   how wide a word is stops the browser mid-frame to lay the whole picture out again, which is
   what made zooming crawl, so no frame ever asks. Each ruler is checked once against the real
   drawing and carries the correction. */
const PAPER = document.createElement("canvas").getContext("2d");
const PROBE = "Handgloves 0123456789 the quick brown fox jumps";
function ruler(cls, inside){
  const host = inside ? svg.append("g").attr("class", inside) : svg;
  const probe = host.append("text").attr("class", cls || null).text(PROBE);
  const css = getComputedStyle(probe.node());
  const font = `${css.fontStyle} ${css.fontWeight} ${css.fontSize} ${css.fontFamily}`;
  PAPER.font = font;
  const fix = probe.node().getComputedTextLength() / (PAPER.measureText(PROBE).width || 1);
  (inside ? host : probe).remove();
  const seen = new Map();
  return s => {
    s = s || "";
    let w = seen.get(s);
    if (w === undefined){ PAPER.font = font; w = PAPER.measureText(s).width * fix; seen.set(s, w); }
    return w;
  };
}
const wName = ruler("node-name"), wSum = ruler("node-sum"), wLane = ruler("lane-name");
const wDate = ruler("date"), wArc = ruler(null, "arc"), wSess = ruler(null, "sess");
let wrapW = 0;   /* the widest row the last wrap() laid out */

/* the name of each piece of work stays at the left edge; the column is as wide as the longest */
const gutterBg = pinned.append("rect").attr("x",0).attr("y",38).attr("fill","var(--bg)");
const laneTags = pinned.selectAll("g.lane").data(THREADS).enter().append("g").attr("class","lane")
  .on("click", (e,t) => selectTopic(t.id))
  .on("mousemove", (e,t) => tipHTML(e, `<b>${esc(t.name)}</b>${t.said} things he said<span> · click for where it stands</span>`))
  .on("mouseleave", hideTip);
THREADS.forEach(t => t.said = STATEMENTS.filter(s => s.thread === t.id).length);
const laneBg = laneTags.append("rect").attr("x",0).attr("fill","var(--bg)").attr("opacity",.88);
laneTags.append("circle").attr("cx",10).attr("cy",0).attr("r",4.5).style("fill",t => t.color);
const LANE_W = 236;
const laneText = laneTags.append("text").attr("class","lane-name").attr("x",22);
laneText.each(function(t){
  t.lines = wrap(d3.select(this), t.name, LANE_W, 13, 3, 22, wLane);
  t.wide = wrapW;
});
const laneNum = laneTags.append("text").attr("class","num").attr("x",22).text(t => t.said + " said");
laneTags.append("title").text(t => t.name);
const dayTags = pinned.selectAll("g.day").data(BANDS).enter().append("g").attr("class","day");
dayTags.append("text").attr("class","date").attr("x",6).attr("y",13).text(b => b.label);

/* the three kinds of thing a lane can show */
const bandRects = gBands.selectAll("rect").data(BANDS.filter((b,i) => i % 2)).enter().append("rect").attr("class","band").attr("rx",7);
const bandLines = gBands.selectAll("line").data(BANDS).enter().append("line").style("stroke","var(--line)").style("stroke-width",1);
const laneLines = gLanes.selectAll("line").data(THREADS).enter().append("line")
  .style("stroke",t => t.color).style("stroke-width",6).style("opacity",.3).attr("stroke-linecap","round");
const tracePath = gTrace.append("path").attr("class","trace");

const arcs = gArcs.selectAll("g").data(ARCS).enter().append("g").attr("class","arc")
  .on("click", (e,a) => selectArc(a))
  .on("mousemove", (e,a) => tipHTML(e, `<b>${esc(a.name)}</b>${esc(a.line)}<span> · ${a.start} to ${a.end} · ${a.said} said</span>`))
  .on("mouseleave", hideTip);
const arcRects = arcs.append("rect").attr("height",30).attr("rx",15).style("stroke",a => T[a.thread].color);
const arcText = arcs.append("text").attr("text-anchor","middle");
arcs.append("title").text(a => a.name + " — " + a.line);

const sessBlocks = [];
SESSIONS.forEach(s => s.lanes.forEach(lane => sessBlocks.push({...s, lane})));
const sess = gSess.selectAll("g").data(sessBlocks).enter().append("g").attr("class","sess")
  .on("click", (e,s) => selectSession(s))
  .on("mousemove", (e,s) => tipHTML(e, `<b>${esc(s.label)}</b>${esc(T[s.lane].name)}<span> · ${s.date}</span>`))
  .on("mouseleave", hideTip);
const sessRects = sess.append("rect").attr("height",26).attr("rx",13).style("stroke",s => T[s.lane].color);
const sessText = sess.append("text").attr("text-anchor","middle").attr("dy",4).text(s => s.label);
sess.append("title").text(s => s.title);

const nodes = gNodes.selectAll("g").data(STATEMENTS).enter().append("g").attr("class","hit")
  .on("click", (e,s) => selectStatement(s))
  .on("mousemove", (e,s) => tipHTML(e, `<b>${esc(s.name)}</b>${esc(s.summary)}<span> · ${esc(T[s.thread].name)} · ${esc(s.time.slice(0,16).replace("T"," "))}</span>`))
  .on("mouseleave", hideTip);
nodes.append("circle").attr("class","dot").attr("r",5.5).style("fill","var(--panel)")
  .style("stroke",s => T[s.thread].color).style("stroke-width",3);
const labs = nodes.append("g").attr("class","lab");
labs.each(function(s,i){
  s.i = i;
  s.below = i % 2 === 1;
  const g = d3.select(this);
  s.nameLines = wrap(g.append("text").attr("class","node-name").attr("x",0).attr("text-anchor","middle"),
                     s.name, NAME_W, NAME_LH, 2, 0, wName);
  NAME_PX = Math.max(NAME_PX, wrapW);
  s.sumLines = wrap(g.append("text").attr("class","node-sum").attr("x",0).attr("text-anchor","middle"),
                    s.summary, SUM_W, SUM_LH, SUM_LINES, 0, wSum);
  SUM_PX = Math.max(SUM_PX, wrapW);
});
const nodeEls = nodes.nodes();
sessBlocks.forEach(s => s.tw = wSess(s.label));
BANDS.forEach(b => { b.wFull = wDate(b.label); b.wDay = wDate(b.day); });

function wrap(sel, text, width, lh, maxLines, atX, w){
  atX = atX || 0;
  const words = (text||"").split(/\s+/).reverse();
  const rows = [];
  let line = [], cur = "", word;
  while ((word = words.pop())){
    line.push(word);
    cur = line.join(" ");
    if (w(cur) > width && line.length > 1){
      line.pop(); cur = line.join(" ");
      if (rows.length + 1 >= maxLines){ cur += "…"; break; }
      rows.push(cur);
      line = [word]; cur = word;
    }
    while (w(cur) > width && cur.length > 2){
      cur = cur.slice(0,-2) + "…";                      /* one word wider than the row */
      line = [cur];
    }
  }
  rows.push(cur);
  wrapW = 0;
  rows.forEach((r,i) => {
    wrapW = Math.max(wrapW, w(r));
    sel.append("tspan").attr("x", atX).attr("dy", i ? lh : 0).text(r);
  });
  return rows.length;
}

/* the room each level needs, measured: a label must fit the gap to the next mark across and
   the gap to the next lane down */
function measure(){
  const box = stage.getBoundingClientRect();
  stageW = box.width; stageH = box.height;
  const widest = d3.max(THREADS, t => t.wide) || 0;
  GUTTER = Math.min(Math.max(widest + 40, 170), Math.max(stageW*0.34, 200));
  laneText.attr("y", t => -(t.lines-1)*6.5 - 2).selectAll("tspan").attr("x", 22);
  laneNum.attr("y", t => -(t.lines-1)*6.5 + (t.lines-1)*13 + 13);
  gutterBg.attr("width", GUTTER - 10).attr("height", Math.max(stageH - 38, 10));
  laneBg.attr("width", GUTTER - 16)
    .attr("y", t => -(t.lines-1)*6.5 - 13).attr("height", t => 20 + t.lines*13);
  LANE_H = Math.max(44, Math.min(116, (stageH - TOPY - 84) / Math.max(THREADS.length - 1, 1)));
  THREADS.forEach((t,i) => laneY[t.id] = TOPY + i*LANE_H);
  K_FIT = (stageW - GUTTER - 46) / WX;
  K_STMT = Math.max(NAME_PX/(2*DX), K_FIT*3);
  K_SUM = Math.max(Math.max(NAME_PX, SUM_PX)/DX, K_STMT*1.3);
  SUM_ROOM = Math.max(1, Math.min(SUM_LINES, Math.floor((LANE_H - 16 - NAME_LH*2)/SUM_LH)));
  gNodes.classed("thin", SUM_ROOM < SUM_LINES);
  const needs = sessBlocks.map(s => (s.tw + 18)/Math.max((s.to - s.from)*DX, DX)).sort((a,b) => a-b);
  K_SESS = Math.min(Math.max(needs[Math.floor(needs.length*0.25)] || K_FIT*2, K_FIT*1.7), K_STMT*0.5);
  K_MAX = Math.max(K_SUM*1.6, 4);
}

/* a wheel or a drag fires far faster than the screen refreshes, so the picture is drawn
   once per frame and the events in between are dropped */
let waiting = false;
function schedule(){
  if (waiting) return;
  waiting = true;
  requestAnimationFrame(() => { waiting = false; draw(); });
}
const zoom = d3.zoom().on("zoom", schedule);
function setZoom(){
  zoom.scaleExtent([K_FIT, K_MAX])
      .extent([[GUTTER, 0], [Math.max(stageW, GUTTER+10), Math.max(stageH,10)]])
      .translateExtent([[-60, -1e5], [WX + 60, 1e5]]);
  svg.call(zoom);
}
const tr = () => d3.zoomTransform(svg.node());
const sx = i => tr().applyX(i*DX);

function step(points){
  let d = "";
  points.forEach((p,i) => {
    if (!i) { d += `M${p[0]},${p[1]}`; return; }
    const q = points[i-1], bend = Math.min(90, Math.abs(p[0]-q[0])*.45);
    d += (q[1] === p[1]) ? ` L${p[0]},${p[1]}` : ` C${q[0]+bend},${q[1]} ${p[0]-bend},${p[1]} ${p[0]},${p[1]}`;
  });
  return d;
}

function draw(){
  const t = tr(), k = t.k, X = i => t.applyX(i*DX);
  const was = level;
  level = k >= K_SUM ? 4 : k >= K_STMT ? 3 : k >= K_SESS ? 2 : 1;
  if (level !== was){
    caption.textContent = CAPTION[level];
    d3.selectAll("#lvl button").classed("on", function(){ return +this.dataset.l === level; });
    gArcs.style("display", level === 1 ? null : "none");
    gSess.style("display", level === 2 ? null : "none");
    gNodes.style("display", level >= 3 ? null : "none");
  }

  bandRects.attr("x", b => X(b.from) - DX*k/2).attr("y", 42)
    .attr("width", b => Math.max((b.to-b.from)*DX*k + DX*k, 2)).attr("height", Math.max(stageH - 60, 10));
  bandLines.attr("x1", b => X(b.from) - DX*k/2).attr("x2", b => X(b.from) - DX*k/2).attr("y1", 42).attr("y2", stageH - 12);
  laneLines.attr("y1", t2 => laneY[t2.id]).attr("y2", t2 => laneY[t2.id])
    .attr("x1", t2 => Math.max(X(t2.first), GUTTER)).attr("x2", t2 => Math.min(X(t2.last), stageW));
  laneTags.attr("transform", t2 => `translate(4,${laneY[t2.id]})`);
  let taken = GUTTER;
  dayTags.each(function(b){
    const a = Math.max(X(b.from) - DX*k/2, GUTTER + 6), z = X(b.to) + DX*k/2;
    const room = z - a;
    const short = b.wFull > room;
    const wide = short ? b.wDay : b.wFull;
    const fits = room > wide + 10 && a >= taken && z < stageW;
    if (fits !== b.on){ this.style.display = fits ? null : "none"; b.on = fits; }
    if (!fits) return;
    if (short !== b.short){ this.firstChild.textContent = short ? b.day : b.label; b.short = short; }
    this.setAttribute("transform", `translate(${a},2)`);
    taken = a + wide + 16;
  });

  if (level === 1){
    arcs.attr("transform", a => `translate(0,${laneY[a.thread]})`);
    arcRects.attr("x", a => X(a.from) - DX*k/2).attr("y", -15)
      .attr("width", a => Math.max((a.to-a.from+1)*DX*k, 30));
    const placed = [];
    arcText.each(function(a){
      const a0 = Math.max(X(a.from) - DX*k/2, GUTTER + 4), a1 = Math.min(X(a.to) + DX*k/2, stageW - 4);
      const room = Math.round(Math.max(a1 - a0 - 10, 150)/8)*8;   /* re-broken only when the room really changes */
      const t2 = d3.select(this);
      if (a.room !== room){
        t2.selectAll("tspan").remove();
        a.lines = wrap(t2, a.name, room, 14, 3, 0, wArc);
        a.room = room;
        a.wide = wrapW;
      }
      const y = laneY[a.thread], half = a.wide/2 + 8;
      const cx = Math.min(Math.max((a0+a1)/2, GUTTER + half), Math.max(stageW - half, GUTTER + half));
      const above = {l: cx-half, r: cx+half, t: y - 22 - a.lines*14, b: y - 16};
      const under = {l: cx-half, r: cx+half, t: y + 20, b: y + 24 + a.lines*14};
      const clear = b => !placed.some(p => p.l < b.r + 6 && b.l < p.r + 6 && p.t < b.b + 4 && b.t < p.b + 4);
      const low = !clear(above) && clear(under);
      placed.push(low ? under : above);
      t2.attr("x", cx).attr("y", low ? 32 : -22 - (a.lines-1)*14)
        .style("display", a1 - a0 < 26 ? "none" : null)
        .selectAll("tspan").attr("x", cx);
    });
    tracePath.attr("d", step(ARCS.map(a => [(X(a.from)+X(a.to))/2, laneY[a.thread]])));
  } else if (level === 2){
    sess.attr("transform", s => `translate(0,${laneY[s.lane]})`);
    sessRects.attr("x", s => X(s.from) - DX*k/2).attr("y", -13)
      .attr("width", s => Math.max((s.to-s.from+1)*DX*k, 26));
    sessText.each(function(s){
      const a0 = Math.max(X(s.from) - DX*k/2, GUTTER + 4), a1 = Math.min(X(s.to) + DX*k/2, stageW - 4);
      d3.select(this).attr("x", (a0+a1)/2).style("display", a1 - a0 < s.tw + 14 ? "none" : null);
    });
    tracePath.attr("d", step(SESSIONS.map(s => [(X(s.from)+X(s.to))/2, laneY[s.thread]])));
  } else {
    const first = Math.max(0, Math.floor((GUTTER - t.x)/(DX*k)) - 2);
    const last = Math.min(STATEMENTS.length - 1, Math.ceil((stageW - t.x)/(DX*k)) + 2);
    for (let i = shownA; i <= shownB; i++){
      if (i < first || i > last) nodeEls[i].style.display = "none";   /* only the ones that just left */
    }
    shownA = first; shownB = last;
    for (let i = first; i <= last; i++){
      const s = STATEMENTS[i], el = nodeEls[i];
      el.style.display = null;
      const px = X(s.i), py = laneY[s.thread];
      el.firstChild.setAttribute("cx", px);
      el.firstChild.setAttribute("cy", py);
      const tall = s.nameLines*NAME_LH + (level === 4 ? Math.min(s.sumLines, SUM_ROOM)*SUM_LH : 0);
      const below = level === 4 ? true : s.below;
      const top = below ? 20 : -14 - tall + NAME_LH;
      const lab = el.lastChild;
      lab.setAttribute("transform", `translate(${px},${py})`);
      lab.style.display = px - NAME_W/2 < GUTTER + 6 || px + NAME_W/2 > stageW - 6 ? "none" : null;
      lab.firstChild.setAttribute("y", top);
      lab.lastChild.setAttribute("y", top + s.nameLines*NAME_LH);
      lab.lastChild.style.display = level === 4 ? null : "none";
    }
    const pts = [];
    for (let i = first; i <= last; i++) pts.push([X(i), laneY[STATEMENTS[i].thread]]);
    tracePath.attr("d", step(pts));
  }
}

function markSelected(){
  arcs.classed("sel", a => selKind === "arc" && a.name === selId);
  sess.classed("sel", s => selKind === "session" && s.title + s.lane === selId);
  nodes.classed("sel", s => selKind === "statement" && s.id === selId);
}

/* start on the whole project, and keep that as the furthest out you can go */
function reset(){
  measure(); setZoom();
  svg.call(zoom.transform, d3.zoomIdentity.translate(GUTTER + 22, 0).scale(K_FIT));
  draw();
}
THREADS.forEach(t => {
  const idx = STATEMENTS.map((s,i) => s.thread === t.id ? i : -1).filter(i => i >= 0);
  t.first = idx[0]; t.last = idx[idx.length-1];
});
reset();
window.addEventListener("resize", reset);
document.querySelectorAll("#lvl button").forEach(b => b.addEventListener("click", () => {
  const want = {1: K_FIT, 2: K_SESS*1.05, 3: K_STMT*1.05, 4: K_SUM*1.05}[+b.dataset.l];
  const t = tr(), mid = (GUTTER + stageW)/2, i = (mid - t.x)/(DX*t.k);
  svg.transition().duration(400).call(zoom.transform,
    d3.zoomIdentity.translate(mid - i*DX*want, 0).scale(want));
}));

/* hover */
const tipEl = document.getElementById("tip");
function tipHTML(e, html){
  tipEl.innerHTML = html;
  tipEl.style.display = "block";
  tipEl.style.left = Math.min(e.clientX - stage.getBoundingClientRect().left + 14, stageW - 350) + "px";
  tipEl.style.top = Math.min(e.clientY - stage.getBoundingClientRect().top + 14, stageH - 90) + "px";
}
function hideTip(){ tipEl.style.display = "none"; }

/* the side panel: an arc, a session, a statement, or where a piece of work stands */
const detail = document.getElementById("detail");
const RID = /\[(?:Oracle:\s*)?R-\d+[^\]]*\]/g;
const rids = h => h.replace(RID, m => `<span class="rid">${m}</span>`);
const aLine = s => `<div>${rids(linkify(s))}</div>`;
const bullets = parts => `<ul class="bul">${parts.map(p => `<li>${rids(linkify(p))}</li>`).join("")}</ul>`;
const bySemi = s => s.split(/;\s+/).map(p => p.trim()).filter(Boolean);
const byNumber = s => s.split(/\s*\(\d+\)\s*/).map(p => p.trim().replace(/;$/,"")).filter(Boolean);
const TAGRE = /^\[(ruling|build|verify|waiting)\]\s*/;
const openBullets = s => `<ul class="bul">${byNumber(s).map(p => {
  const m = p.match(TAGRE);
  return `<li>${m ? `<span class="tag">${TAGLABEL[m[1]].toLowerCase()}</span>` : ""}`
       + `${rids(linkify(m ? p.slice(m[0].length) : p))}</li>`;
}).join("")}</ul>`;
const swatch = id => `<span class="sw" style="background:${T[id] ? T[id].color : "#8b9792"}"></span>`;

function selectArc(a){
  selKind = "arc"; selId = a.name; markSelected();
  const mine = SESSIONS.filter(s => s.date >= a.start && s.date <= a.end);
  detail.innerHTML = `<div class="k">story arc ${ARCS.indexOf(a)+1} of ${ARCS.length}</div><h3>${esc(a.name)}</h3>`
    + `<div>${swatch(a.thread)}${esc(T[a.thread].name)}</div>`
    + `<div class="k">when</div><div>${a.start} to ${a.end} · ${a.said} things he said</div>`
    + `<div class="k">what it was</div><div>${esc(a.line)}</div>`
    + `<div class="k">sessions inside it</div>`
    + (mine.length ? bullets(mine.map(s => s.date + " — " + s.label))
                   : `<div style="color:var(--faint)">no session entry written for these days yet</div>`);
}
function selectSession(s){
  selKind = "session"; selId = s.title + s.lane; markSelected();
  detail.innerHTML = `<div class="k">session entry</div><h3>${esc(s.label)}</h3>`
    + `<div>${s.lanes.map(l => swatch(l) + esc(T[l].name)).join("<br>")}</div>`
    + `<div class="k">when</div><div>${s.date}</div>`
    + `<div class="k">what happened</div><blockquote>${esc(s.text)}</blockquote>`;
}
function selectStatement(s){
  selKind = "statement"; selId = s.id; markSelected();
  const after = AFTER[s.id] || [];
  detail.innerHTML = `<div class="k">statement ${s.i+1} of ${STATEMENTS.length}</div><h3>${esc(s.name)}</h3>`
    + `<div>${swatch(s.thread)}${esc(T[s.thread].name)}</div>`
    + `<div class="k">when</div><div>${esc(s.time.slice(0,16).replace("T"," "))} · ${esc(s.session_title || s.session)}</div>`
    + `<div class="k">what he asked for</div><div>${esc(s.summary)}</div>`
    + `<details><summary>His words</summary><blockquote>${esc(s.text)}</blockquote></details>`
    + `<div class="k">what followed</div>`
    + (after.length
        ? `<ul class="pills">${after.map(a => `<li><span class="kk">${esc(KIND[a.k]||a.k)}</span>${esc(clip(a.l,90))}${a.d?` <span style="color:var(--faint)">${esc(a.d)}</span>`:""}</li>`).join("")}</ul>`
        : `<div style="color:var(--faint)">nothing recorded in this piece of work between here and the next thing he said about it</div>`);
}
function selectTopic(id){
  const t = TOPIC[id];
  selKind = "topic"; selId = id; markSelected();
  if (!t){
    detail.innerHTML = `<h3>${esc(T[id].name)}</h3><div style="color:var(--faint)">These are the things he said that no piece of work has claimed yet.</div>`;
    return;
  }
  detail.innerHTML = `<div class="k">where it stands</div><h3>${swatch(id)}${esc(t.name)}</h3>`
    + `<div class="k">status</div>` + aLine(t.Status)
    + (t.Decided ? `<div class="k">settled</div>` + bullets(bySemi(t.Decided)) : "")
    + (t.Open ? `<div class="k">still open</div>` + openBullets(t.Open) : "")
    + (t["Lives in"] ? `<div class="k">lives in</div>` + bullets(bySemi(t["Lives in"])) : "")
    + (t["Next action"] ? `<div class="k">next</div>` + aLine(t["Next action"]) : "");
}

/* search dims whatever the trace is showing, and hides rows in the other view */
document.getElementById("q").addEventListener("input", ev => {
  const q = ev.target.value.trim().toLowerCase();
  const hit = s => (s.name+" "+s.summary+" "+s.text).toLowerCase().includes(q);
  nodes.classed("dim", s => q && !hit(s));
  sess.classed("dim", s => q && !(s.title+" "+s.text).toLowerCase().includes(q));
  arcs.classed("dim", a => q && !(a.name+" "+a.line).toLowerCase().includes(q));
  filterState(q);
});

/* the two views */
document.querySelectorAll("#mode button").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll("#mode button").forEach(x2 => x2.classList.remove("on"));
  b.classList.add("on");
  const trace = b.dataset.v === "trace";
  stage.style.display = trace ? "" : "none";
  document.getElementById("state").style.display = trace ? "none" : "block";
  document.getElementById("lvl").style.display = trace ? "" : "none";
  if (trace) reset();
  else document.getElementById("caption").textContent =
    "What is open and what is settled. The top list is everything waiting on you; under it is the "
    + "work already decided but not finished; everything settled is folded away at the bottom.";
}));

/* the second view: open first, settled folded, then a block per topic to drill into */
const stateEl = document.getElementById("state");
const ROWS = {};
TAGS_ORDER.forEach(tag => ROWS[tag] = OPEN_ROWS.filter(r => r.tag === tag));
const nWork = OPEN_ROWS.length - ROWS.ruling.length;
const nSettled = SETTLED.reduce((n,s) => n + s.bullets.length, 0);
// the topic carries its lane colour everywhere it is named: a dot before the name
const laneDot = tid => `<i class="ldot" style="background:${(T[tid] || {}).color || "var(--faint)"}"></i>`;
const stateRow = r => `<div class="row" data-t="${r.tid}">`
  + `<span class="rtext">${esc(r.text)}</span><span class="rtopic">${laneDot(r.tid)}${esc(r.topic)}</span></div>`;
const openTopics = TOPICS.filter(t => t.id !== "untagged");

stateEl.innerHTML =
  `<section><h2>Needs your word</h2><span class="n">${ROWS.ruling.length}</span>`
  + `<div class="sub">Nothing on this list moves until you say which way it goes.</div>`
  + ROWS.ruling.map(stateRow).join("")
  + `</section><section><h2>Open work</h2><span class="n">${nWork}</span>`
  + `<div class="sub">Already decided, not yet finished.</div>`
  + ["build","verify","waiting"].filter(t => ROWS[t].length).map(tag =>
      `<h3 class="tag-h">${TAGLABEL[tag]}<span class="n">${ROWS[tag].length}</span></h3>`
      + ROWS[tag].map(stateRow).join("")).join("")
  + `</section>`
  + `<details class="grp"><summary><span class="h2">Settled</span><span class="n">${nSettled}</span></summary>`
  + SETTLED.map(s => `<div class="stop"><h3>${esc(s.name)}`
      + (s.closed ? `<span class="n">finished</span>` : "") + `</h3>`
      + `<ul class="bul">${s.bullets.map(b => `<li>${esc(b.text)}`
          + (b.rid ? ` <span class="rid">${esc(b.rid)}</span>` : "") + `</li>`).join("")}</ul></div>`).join("")
  + `</details>`
  + `<h2 class="alltop">Every topic</h2>`
  + openTopics.map(t => `<details class="blk" id="blk-${t.id}"><summary>${laneDot(t.id)}${esc(t.name)}</summary>`
      + `<div class="k">status</div>` + aLine(t.Status)
      + (t.Decided ? `<div class="k">settled</div>` + bullets(bySemi(t.Decided)) : "")
      + (t.Open ? `<div class="k">still open</div>` + openBullets(t.Open) : "")
      + (t["Lives in"] ? `<div class="k">lives in</div>` + bullets(bySemi(t["Lives in"])) : "")
      + (t["Next action"] ? `<div class="k">next</div>` + aLine(t["Next action"]) : "")
      + `</details>`).join("");

stateEl.addEventListener("click", ev => {
  const row = ev.target.closest(".row");
  if (!row) return;
  const blk = document.getElementById("blk-" + row.dataset.t);
  if (!blk) return;
  blk.open = true;
  blk.scrollIntoView({behavior:"smooth", block:"start"});
});

function filterState(q){
  const show = el => { el.style.display = !q || el.textContent.toLowerCase().includes(q) ? "" : "none"; };
  stateEl.querySelectorAll(".row, .stop li, details.blk").forEach(show);
  stateEl.querySelectorAll("h3.tag-h").forEach(h => {
    let n = 0;
    for (let el = h.nextElementSibling; el && el.classList.contains("row"); el = el.nextElementSibling)
      if (el.style.display !== "none") n++;
    h.style.display = n ? "" : "none";
  });
  stateEl.querySelectorAll(".stop").forEach(g => {
    g.style.display = [...g.querySelectorAll("li")].some(li => li.style.display !== "none") ? "" : "none";
  });
}

document.getElementById("theme").onclick = () => {
  const cur = document.documentElement.getAttribute("data-theme");
  const dark = cur ? cur === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.setAttribute("data-theme", dark ? "light" : "dark");
  reset();
};
document.getElementById("counts").textContent =
  `${ARCS.length} arcs · ${SESSIONS.length} sessions · ${STATEMENTS.length} statements · ${THREADS.length} pieces of work`;
selectArc(ARCS[ARCS.length-1]);
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
    story, sittings = arcs(statements), sessions(statements, events)
    page = (
        PAGE.replace("__STATEMENTS__", json.dumps(slim, ensure_ascii=False))
        .replace("__THREADS__", json.dumps(lanes, ensure_ascii=False))
        .replace("__BANDS__", json.dumps(bands(statements)))
        .replace("__ARCS__", json.dumps(story, ensure_ascii=False))
        .replace("__SESSIONS__", json.dumps(sittings, ensure_ascii=False))
        .replace("__AFTER__", json.dumps(followed(statements, events), ensure_ascii=False))
        .replace("__TOPICS__", json.dumps(topics, ensure_ascii=False))
        .replace("__OPENROWS__", json.dumps(open_rows(topics), ensure_ascii=False))
        .replace("__SETTLED__", json.dumps(settled(topics), ensure_ascii=False))
    )
    Path(out).write_text(page)
    print(f"{out}: {len(story)} arcs, {len(sittings)} sessions, {len(slim)} statements, {len(lanes)} pieces of work")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
