"""Render the FD-362 dashboard as the thought-and-decision tree: the product idea at the
root, the goals under it, and under each goal its decisions, its open questions, and the
evidence that hangs off each decision. Date, commit and artifact are secondary.

  python bin/eventpage.py <out.html>
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DOC = HERE / "doc" / "chat-first"

ROOT_NAME = "A coach who never forgets your family"
DECISION_KINDS = ("ruling", "defect", "decision")
EVIDENCE_KINDS = ("review", "build", "artifact", "history")
NEAR_DAYS = 3
SHARED_WORDS = 3
STOP = set(
    "the and that this with from into over under about their there them they then than when "
    "what which while will would could should must have has had been being does done your "
    "whose where were was are for not but its it's one two only also same such each every "
    "page view app user users owner claude code file files line lines make made make text "
    "work works working change changes changed after before first second".split()
)


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
    out.append(
        {
            "id": "untagged",
            "name": "Not yet assigned to a goal",
            "Status": "every record here needs a home",
            "Decided": "",
            "Open": "",
            "Lives in": "",
            "Next action": "assign in the next flush",
            "Updated": "",
        }
    )
    return out


def open_questions(field: str) -> list[str]:
    parts = re.split(r"\((\d+)\)\s*", field)
    if len(parts) < 3:
        return [field.strip(" ;.")] if field.strip() else []
    out = []
    for i in range(1, len(parts) - 1, 2):
        q = parts[i + 1].strip().strip(";").strip()
        if q:
            out.append(q)
    return out


def clause(text: str, limit: int = 90) -> str:
    t = " ".join((text or "").split())
    t = re.split(r"\s[—–-]\s|;\s", t)[0]
    if len(t) <= limit:
        return t
    cut = t[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z']{3,}", (text or "").lower()) if w not in STOP}


def day(s: str):
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def ruling_key(e: dict):
    m = re.match(r"R-(\d+)", e["id"] or "")
    if m:
        return (0, int(m.group(1)), "")
    return (1, 0, e.get("date") or "9999")


def build_tree(events: list[dict], topics: list[dict]) -> tuple[list[dict], dict]:
    for i, e in enumerate(events):
        e["_i"] = i
        e["_d"] = day(e.get("date"))
        e["_w"] = words(e.get("title", "") + " " + e.get("text", ""))
    by_id = {e["id"]: e for e in events}
    counts = {"decisions": 0, "open": 0, "evidence": 0, "revised": 0}
    goals = []
    for t in topics:
        tagged = [e for e in events if t["id"] in (e.get("topics") or [])]
        decisions = [e for e in tagged if e["kind"] in DECISION_KINDS]
        decisions.sort(key=ruling_key)
        superseded = set()
        for e in decisions:
            for old in e.get("supersedes") or []:
                if old in by_id:
                    superseded.add(old)
        top = [e for e in decisions if e["id"] not in superseded]
        evidence = [e for e in tagged if e["kind"] in EVIDENCE_KINDS]
        attached = {e["id"]: [] for e in top}
        leftover = []
        for ev in evidence:
            best, best_score = None, 0
            for d in top:
                cites = ev["kind"] == "review" and d["id"] in (ev.get("title", "") + " " + ev.get("text", ""))
                shared = len(ev["_w"] & d["_w"])
                near = ev["_d"] and d["_d"] and abs((ev["_d"] - d["_d"]).days) <= NEAR_DAYS
                score = 0
                if cites:
                    score = 100
                elif shared >= SHARED_WORDS:
                    score = 10 + shared + (5 if near else 0)
                elif near and ev["kind"] != "review":
                    score = 1 + max(0, NEAR_DAYS - abs((ev["_d"] - d["_d"]).days))
                if score > best_score:
                    best, best_score = d, score
            if best is not None:
                attached[best["id"]].append(ev)
            else:
                leftover.append(ev)
        children = []
        for q in open_questions(t["Open"]):
            counts["open"] += 1
            children.append({"t": "open", "l": clause(q, 110), "full": q, "d": ""})
        for d in top:
            counts["decisions"] += 1
            kids = []
            for old in d.get("supersedes") or []:
                if old in by_id:
                    counts["revised"] += 1
                    kids.append({"t": "old", "l": "revised from " + clause(by_id[old]["title"], 76), "d": by_id[old].get("date", ""), "e": by_id[old]["_i"]})
            for ev in sorted(attached[d["id"]], key=lambda e: (e.get("date") or "", e["id"])):
                counts["evidence"] += 1
                kids.append({"t": "ev", "k": ev["kind"], "l": clause(ev["title"], 92), "d": ev.get("date", ""), "e": ev["_i"]})
            children.append({"t": "dec", "k": d["kind"], "l": clause(d["title"]), "d": d.get("date", ""), "e": d["_i"], "c": kids})
        if leftover:
            tally = {k: sum(1 for e in leftover if e["kind"] == k) for k in EVIDENCE_KINDS}
            label = " · ".join(
                f"{n} {name}"
                for n, name in (
                    (tally["build"], "builds"),
                    (tally["artifact"], "artifacts"),
                    (tally["review"], "review findings"),
                    (tally["history"], "session entries"),
                )
                if n
            )
            kids = []
            for ev in sorted(leftover, key=lambda e: (e.get("date") or "", e["id"])):
                counts["evidence"] += 1
                kids.append({"t": "ev", "k": ev["kind"], "l": clause(ev["title"], 92), "d": ev.get("date", ""), "e": ev["_i"]})
            children.append({"t": "more", "l": "not yet attached to a decision: " + label, "d": "", "c": kids})
        goals.append(
            {
                "t": "goal",
                "id": t["id"],
                "l": t["name"],
                "status": t["Status"],
                "next": t["Next action"],
                "lives": t["Lives in"],
                "updated": t["Updated"],
                "c": children,
            }
        )
    for e in events:
        e.pop("_w", None)
        e.pop("_d", None)
    return goals, counts


PAGE = r'''<title>FD-362 Decision Tree</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<style>
:root{--bg:#f7f6f2;--panel:#fff;--ink:#26312f;--faint:#67746f;--line:#d8d5cc;--data:#0e7d78;--ask:#c98a1b;--move:#2e9e57;--bad:#b4453b;--tint:rgba(14,125,120,.08);--sans:"Libre Franklin",-apple-system,system-ui,sans-serif;--mono:ui-monospace,Menlo,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#171d1c;--panel:#1f2725;--ink:#e6e8e4;--faint:#9aa5a0;--line:#39443f;--tint:rgba(14,125,120,.2)}}
:root[data-theme="dark"]{--bg:#171d1c;--panel:#1f2725;--ink:#e6e8e4;--faint:#9aa5a0;--line:#39443f;--tint:rgba(14,125,120,.2)}
body{background:var(--bg);color:var(--ink);font:14px/1.45 var(--sans);margin:0;height:100vh;display:grid;grid-template-rows:auto 1fr;overflow:hidden}
header{display:flex;align-items:center;gap:14px;padding:10px 16px;border-bottom:1px solid var(--line);background:var(--panel);flex-wrap:wrap}
header h1{font:600 16px var(--sans);margin:0 10px 0 0}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:16px;overflow:hidden}
.seg button{border:0;background:none;padding:5px 12px;font:500 13px var(--sans);color:var(--faint);cursor:pointer}
.seg button.on{background:var(--data);color:#fff}
header input[type=search]{font:13px var(--sans);padding:5px 11px;border:1px solid var(--line);border-radius:14px;background:var(--bg);color:var(--ink);min-width:230px}
header .count{font:12px var(--mono);color:var(--faint);margin-left:auto}
main{display:grid;grid-template-columns:1fr 380px;min-height:0}
#stage{overflow:auto;padding:10px 6px 60px}
#detail{border-left:1px solid var(--line);background:var(--panel);padding:14px 16px;overflow:auto;font-size:13.5px}
#detail h3{font:600 14px var(--sans);margin:0 0 6px}
#detail .k{font:11px var(--mono);color:var(--faint);letter-spacing:.06em;text-transform:uppercase;margin:10px 0 2px}
#detail a{color:var(--data)}
#detail .words{white-space:pre-wrap}
.row{display:flex;align-items:baseline;gap:7px;padding:2px 8px 2px 0;border-radius:6px;cursor:pointer}
.row:hover{background:var(--tint)}
.row.sel{background:var(--tint);box-shadow:inset 2px 0 0 var(--data)}
.tw{width:14px;flex:0 0 14px;color:var(--faint);font:11px var(--mono);text-align:center;-webkit-user-select:none;user-select:none}
.tw.leaf{opacity:.25}
.mark{flex:0 0 auto;width:9px;height:9px;border-radius:50%;margin-top:1px}
.lbl{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.dt{flex:0 0 auto;font:11px var(--mono);color:var(--faint)}
.row.root{padding:4px 8px 8px 0;border-bottom:1px solid var(--line)}
.row.root .lbl{font:600 17px var(--sans)}
.row.goal{padding:9px 8px 4px 0;margin-top:8px;border-top:1px solid var(--line)}
.row.goal .lbl{font:600 15px var(--sans)}
.row.goal .gid{font:11px var(--mono);color:var(--faint);flex:0 0 auto}
.goalmeta{color:var(--faint);font-size:12.5px;margin:0 0 4px}
.goalmeta b{font-weight:600;color:var(--ink)}
.row.dec .lbl{font-size:13.5px}
.row.open .lbl{color:var(--ask)}
.row.ev .lbl,.row.more .lbl{color:var(--faint);font-size:12.5px}
.row.old .lbl{color:var(--faint);text-decoration:line-through}
.row.hit .lbl{font-weight:600}
.kids{margin-left:17px;border-left:1px solid var(--line);padding-left:4px}
.empty{color:var(--faint);padding:20px 16px}
</style>
<header><h1>FD-362 · the decision tree</h1>
<span class="seg" id="mode"><button class="on" data-v="tree">Tree</button><button data-v="state">Where it stands</button></span>
<span class="seg" id="order"><button class="on" data-o="idea">Conceptual order</button><button data-o="date">By date</button></span>
<input type="search" id="q" placeholder="search words, ids, commits">
<button id="fold" class="seg" style="padding:5px 12px;font:500 13px var(--sans);color:var(--faint);background:none;cursor:pointer">Collapse all</button>
<span class="count" id="counts"></span></header>
<main><div id="stage"></div><aside id="detail"></aside></main>
<script>
const EVENTS = __EVENTS__;
const GOALS = __GOALS__;
const COUNTS = __COUNTS__;
const ROOT = __ROOT__;
const KIND = {ruling:{c:"#0e7d78",l:"ruling"},defect:{c:"#b4453b",l:"correction"},decision:{c:"#5b4fc4",l:"decision"},history:{c:"#26312f",l:"session entry"},review:{c:"#c98a1b",l:"review finding"},build:{c:"#8f9a95",l:"build (commit)"},artifact:{c:"#2e9e57",l:"artifact"}};
const TREE = {t:"root", l:ROOT, c:GOALS};
const state = {mode:"tree", order:"idea", q:"", sel:null};
const open = new Map();          // node key -> expanded?
const esc = s => (s||"").replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const linkify = s => esc(s).replace(/(https?:\/\/\S+)/g, '<a href="$1" target="_blank">$1</a>');
const supersededNode = n => n.e != null && /SUPERSEDED/i.test(EVENTS[n.e].status || "");

function keyOf(n, parent){ return (parent ? parent + ">" : "") + (n.id || n.e || n.l).toString().slice(0,80); }
function defaultOpen(n){ return n.t === "goal" || n.t === "root"; }
function isOpen(k, n){ return open.has(k) ? open.get(k) : defaultOpen(n); }

function haystack(n){
  let s = n.l || "";
  if (n.e != null){ const e = EVENTS[n.e]; s += " " + e.id + " " + e.title + " " + e.text + " " + (e.commit||"") + " " + (e.session||""); }
  return s.toLowerCase();
}
function matches(n){ return !state.q || haystack(n).includes(state.q); }

function kids(n){
  let c = (n.c || []).slice();
  if (state.mode === "state"){
    if (n.t !== "root" && n.t !== "goal") return [];
    if (n.t === "goal") c = c.filter(x => (x.t === "open" || x.t === "dec") && !supersededNode(x));
  }
  if (state.order === "date" && (n.t === "goal" || n.t === "dec" || n.t === "more"))
    c.sort((a,b) => (a.d||"9999").localeCompare(b.d||"9999"));
  return c;
}

function rowHTML(n, key, depth, expanded, hit){
  const has = kids(n).length > 0;
  const tw = has ? (expanded ? "▾" : "▸") : "·";
  const k = n.k || (n.t === "open" ? "open" : null);
  const colour = k && KIND[k] ? KIND[k].c : (n.t === "open" ? "var(--ask)" : "var(--line)");
  const mark = (n.t === "goal" || n.t === "root") ? "" : `<span class="mark" style="background:${colour}"></span>`;
  const dt = n.d ? `<span class="dt">${esc(n.d)}</span>` : "";
  const label = `<span class="lbl">${esc(n.l)}</span>`;
  const gid = n.t === "goal" ? `<span class="gid">${esc(n.id)}</span>` : "";
  const body = (state.order === "date" && n.d) ? dt + label : label + dt;
  return `<div class="row ${n.t}${hit?" hit":""}${state.sel===key?" sel":""}" data-k="${esc(key)}"><span class="tw${has?"":" leaf"}">${tw}</span>${mark}${gid}${body}</div>`;
}

function renderNode(n, parentKey, depth, out){
  const key = keyOf(n, parentKey);
  const children = kids(n);
  let rendered = [];
  const childHit = [];
  children.forEach(c => { const r = renderNode(c, key, depth+1, rendered); if (r) childHit.push(r); });
  const hit = matches(n);
  if (state.q && !hit && childHit.length === 0) return false;
  const expanded = state.q ? (childHit.length > 0 || isOpen(key, n)) : isOpen(key, n);
  let html = rowHTML(n, key, depth, expanded, state.q && hit);
  if (n.t === "goal" && state.mode === "state")
    html += `<div class="goalmeta"><b>Status.</b> ${esc(n.status)} <b>Next.</b> ${esc(n.next)}</div>`;
  if (expanded && rendered.length) html += `<div class="kids">${rendered.join("")}</div>`;
  out.push(html);
  return true;
}

function render(){
  const stage = document.getElementById("stage");
  const out = [];
  renderNode(TREE, "", 0, out);
  stage.innerHTML = out.length ? out.join("") : `<div class="empty">Nothing matches “${esc(state.q)}”.</div>`;
  stage.querySelectorAll(".row").forEach(r => {
    r.addEventListener("click", ev => {
      const key = r.dataset.k;
      const n = NODES.get(key);
      if (!n) return;
      state.sel = key;
      if (kids(n).length && ev.target.classList.contains("tw")) open.set(key, !isOpen(key, n));
      else if (kids(n).length && !n.e && n.t !== "goal") open.set(key, !isOpen(key, n));
      else if (kids(n).length && ev.target.classList.contains("lbl") && (n.t === "goal" || n.t === "more")) open.set(key, !isOpen(key, n));
      showNode(n);
      render();
    });
  });
}

const NODES = new Map();
function index(n, parentKey){ const key = keyOf(n, parentKey); NODES.set(key, n); (n.c||[]).forEach(c => index(c, key)); }
index(TREE, "");

function showNode(n){
  const d = document.getElementById("detail");
  if (n.t === "root"){
    document.getElementById("detail").innerHTML = INTRO;
    return;
  }
  if (n.t === "goal"){
    const dec = (n.c||[]).filter(x=>x.t==="dec").length, q = (n.c||[]).filter(x=>x.t==="open").length;
    d.innerHTML = `<h3>${esc(n.l)}</h3><div class="k">goal</div><div>${esc(n.id)} · ${dec} decisions · ${q} open questions</div>`
      + `<div class="k">status</div><div>${esc(n.status)}</div><div class="k">next action</div><div>${esc(n.next)}</div>`
      + `<div class="k">lives in</div><div>${linkify(n.lives)}</div><div class="k">updated</div><div>${esc(n.updated)}</div>`;
    return;
  }
  if (n.e == null){
    d.innerHTML = `<h3>${esc(n.l)}</h3><div class="k">${n.t==="open"?"open question":"evidence not yet attached"}</div><div class="words">${linkify(n.full || n.l)}</div>`;
    return;
  }
  const e = EVENTS[n.e];
  const goals = GOALS.filter(g => (e.topics||[]).includes(g.id)).map(g => g.l).join(" · ");
  d.innerHTML = `<h3>${esc(e.title)}</h3>`
    + `<div class="k">${KIND[e.kind].l}${e.status?" · "+esc(e.status):""}</div>`
    + `<div>${esc(e.id)}${e.date?" · "+esc(e.date):" · undated"}${e.session?" · "+esc(e.session):""}</div>`
    + `<div class="k">goal</div><div>${esc(goals)}</div>`
    + `<div class="k">words</div><div class="words">${linkify(e.text)}</div>`
    + ((e.supersedes||[]).length ? `<div class="k">revises</div><div>${esc(e.supersedes.join(", "))}</div>` : "")
    + (e.commit ? `<div class="k">commit</div><div>${esc(e.commit)}</div>` : "")
    + (e.link ? `<div class="k">link</div><div>${linkify(e.link)}</div>` : "")
    + `<div class="k">source</div><div>${esc(e.source)}</div>`;
}

const INTRO = `<h3>${esc(ROOT)}</h3><p style="color:var(--faint)">The tree is the goals, and under each goal the decisions taken and the questions still open. Under a decision, folded, sits its evidence: the review findings, commits and artifacts that belong to it. Click a name for its full words; click the triangle to open it. “Where it stands” drops the evidence and the revised decisions and heads each goal with its status.</p>`;
document.getElementById("detail").innerHTML = INTRO;
document.getElementById("counts").textContent = `${COUNTS.decisions} decisions · ${COUNTS.open} open questions · ${COUNTS.evidence} evidence items · ${GOALS.length} goals`;
document.querySelectorAll("#mode button").forEach(b => b.addEventListener("click", () => { document.querySelectorAll("#mode button").forEach(x=>x.classList.remove("on")); b.classList.add("on"); state.mode = b.dataset.v; render(); }));
document.querySelectorAll("#order button").forEach(b => b.addEventListener("click", () => { document.querySelectorAll("#order button").forEach(x=>x.classList.remove("on")); b.classList.add("on"); state.order = b.dataset.o; render(); }));
document.getElementById("q").addEventListener("input", ev => { state.q = ev.target.value.trim().toLowerCase(); render(); });
document.getElementById("fold").addEventListener("click", () => {
  const anyOpen = [...NODES.entries()].some(([k,n]) => n.t === "goal" && isOpen(k,n));
  NODES.forEach((n,k) => { if (n.t === "goal") open.set(k, !anyOpen); });
  document.getElementById("fold").textContent = anyOpen ? "Expand all" : "Collapse all";
  render();
});
render();
</script>
'''


def main(out: str) -> int:
    events = json.loads((DOC / "events.json").read_text())
    topics = topic_blocks()
    goals, counts = build_tree(events, topics)
    page = (
        PAGE.replace("__EVENTS__", json.dumps(events, ensure_ascii=False))
        .replace("__GOALS__", json.dumps(goals, ensure_ascii=False))
        .replace("__COUNTS__", json.dumps(counts))
        .replace("__ROOT__", json.dumps(ROOT_NAME))
    )
    Path(out).write_text(page)
    print(f"{out}: {counts['decisions']} decisions, {counts['open']} open questions, {counts['evidence']} evidence items, {counts['revised']} revised")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
