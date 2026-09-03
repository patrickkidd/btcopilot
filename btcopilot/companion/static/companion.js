/* The companion app: a coach you talk to, with the picture of your family's
   timeline pinned above the chat. Three levels of picture (resting wire,
   chapter, play-by-play), the chat and its chips, the sessions overlay, the
   settings stack and the full-screen timeline list with its editor.

   Everything is drawn from the REST surface in doc/chat-first/API.md. */
(function () {
  "use strict";

  /* ============================ plumbing ============================ */

  var $ = function (id) { return document.getElementById(id); };
  var CSRF = document.querySelector('meta[name="csrf-token"]').content;

  function esc(text) {
    return String(text == null ? "" : text)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function api(method, path, body) {
    var options = { method: method, headers: { Accept: "application/json" } };
    if (method !== "GET") options.headers["X-CSRFToken"] = CSRF;
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    return fetch("/companion" + path, options).then(function (response) {
      return response.text().then(function (text) {
        if (!response.ok) throw new Error(text || String(response.status));
        return text ? JSON.parse(text) : null;
      });
    });
  }

  function toast(text) {
    var node = document.createElement("div");
    node.className = "toast";
    node.textContent = text;
    $("toasts").appendChild(node);
    setTimeout(function () { node.remove(); }, 2200);
  }

  function failed(error) {
    console.error(error);
    toast(String(error.message || error).slice(0, 80));
  }

  /* Mouse drag scrolls any overflow container; wheel and touch already do. */
  (function () {
    var box = null, startY = 0, startTop = 0, dragging = false, moved = false;
    document.addEventListener("pointerdown", function (event) {
      var target = event.target.closest && event.target.closest("[data-dragscroll]");
      if (!target || event.pointerType === "touch") return;
      box = target; startY = event.clientY; startTop = target.scrollTop;
      dragging = true; moved = false;
    }, true);
    document.addEventListener("pointermove", function (event) {
      if (!dragging || !box) return;
      var dy = event.clientY - startY;
      if (!moved && Math.abs(dy) < 6) return;
      moved = true;
      box.scrollTop = startTop - dy;
    }, true);
    function end() {
      if (dragging && moved && box) {
        var node = box;
        var swallow = function (event) {
          event.stopPropagation(); event.preventDefault();
          node.removeEventListener("click", swallow, true);
        };
        node.addEventListener("click", swallow, true);
      }
      dragging = false; moved = false; box = null;
    }
    document.addEventListener("pointerup", end, true);
    document.addEventListener("pointercancel", end, true);
  })();

  function onLongPress(node, handler) {
    var timer = null, fired = false, x = 0, y = 0;
    node.addEventListener("pointerdown", function (event) {
      fired = false; x = event.clientX; y = event.clientY;
      timer = setTimeout(function () { timer = null; fired = true; handler(event); }, 500);
    });
    function cancel() { clearTimeout(timer); timer = null; }
    ["pointerup", "pointercancel", "pointerleave"].forEach(function (name) {
      node.addEventListener(name, cancel);
    });
    node.addEventListener("pointermove", function (event) {
      if (timer && Math.hypot(event.clientX - x, event.clientY - y) > 8) cancel();
    });
    node.addEventListener("click", function (event) {
      if (fired) { fired = false; event.stopPropagation(); event.preventDefault(); }
    }, true);
  }

  /* ============================== dates ============================== */

  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  var MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
                     "August", "September", "October", "November", "December"];
  var DAY = 86400000;

  function moment(text) {
    /* The API returns naive UTC timestamps; without the zone the browser
       reads them as local time and a session lands on the wrong day. */
    return new Date(/[Z+]|-\d\d:\d\d$/.test(text) ? text : text + "Z");
  }

  function toTime(iso) {
    var parts = iso.split("-");
    return new Date(+parts[0], +parts[1] - 1, +parts[2]).getTime();
  }

  function dateText(iso, certainty) {
    if (!iso || certainty === "unknown") return "no date yet";
    var parts = iso.split("-");
    var words = MONTHS[+parts[1] - 1] + " " + parts[0];
    return certainty === "approximate" ? "~" + words : words;
  }

  function shortDate(when) {
    var now = new Date();
    var day = function (d) { return d.getFullYear() * 400 + d.getMonth() * 40 + d.getDate(); };
    if (day(when) === day(now)) {
      return (when.getHours() % 12 || 12) + ":" +
        String(when.getMinutes()).padStart(2, "0") + (when.getHours() >= 12 ? "pm" : "am");
    }
    var yesterday = new Date(now.getTime() - DAY);
    if (day(when) === day(yesterday)) return "yesterday";
    if (now - when < 7 * DAY) return WEEKDAYS[when.getDay()];
    if (when.getFullYear() === now.getFullYear()) {
      return MONTHS[when.getMonth()] + " " + when.getDate();
    }
    return MONTHS[when.getMonth()] + " " + when.getFullYear();
  }

  function recencyGroup(when) {
    var now = new Date();
    var day = function (d) { return d.getFullYear() * 400 + d.getMonth() * 40 + d.getDate(); };
    if (day(when) === day(now)) return "Today";
    if (day(when) === day(new Date(now.getTime() - DAY))) return "Yesterday";
    if (now - when < 7 * DAY) return "This week";
    if (when.getFullYear() === now.getFullYear() && when.getMonth() === now.getMonth()) {
      return "This month";
    }
    return MONTH_NAMES[when.getMonth()] + " " + when.getFullYear();
  }

  /* ============================== state ============================== */

  var S = {
    timeline: null,
    prefs: null,
    account: null,
    sessions: [],
    session: null,
    messages: [],
    level: 1,
    chapter: null,
    step: 0,
    selected: null,
    lit: [],
    screen: "chat",
    settings: [],
    search: "",
    editing: null,
    adding: false
  };

  function events() { return S.timeline ? S.timeline.events : []; }
  function chapters() { return S.timeline ? S.timeline.chapters : []; }
  function people() { return S.timeline ? S.timeline.people : []; }

  function eventById(id) {
    var found = events().filter(function (e) { return e.id === id; });
    return found.length ? found[0] : null;
  }

  function personName(id) {
    var found = people().filter(function (p) { return p.id === id; });
    return found.length ? found[0].name : null;
  }

  function chapterEvents(index) {
    var chapter = chapters()[index];
    if (!chapter) return [];
    return chapter.event_ids.map(eventById).filter(Boolean);
  }

  function chapterOfEvent(id) {
    var list = chapters();
    for (var i = 0; i < list.length; i++) {
      if (list[i].event_ids.indexOf(id) >= 0) return i;
    }
    return null;
  }

  function protagonist() {
    var primary = people().filter(function (p) { return p.primary; });
    if (primary.length) return primary[0].id;
    var counts = {};
    events().forEach(function (e) {
      if (e.person != null) counts[e.person] = (counts[e.person] || 0) + 1;
    });
    var best = null;
    Object.keys(counts).forEach(function (id) {
      if (best === null || counts[id] > counts[best]) best = id;
    });
    return best === null ? null : +best;
  }

  function words(event) {
    var who = event.person !== protagonist() ? event.person_name : null;
    return [dateText(event.dateTime, event.dateCertainty), who, event.label]
      .filter(Boolean).join(" · ");
  }

  /* ============================= the picture ========================= */

  var CH = 7.8;                    // mono advance at the 13px floor
  var ROWS = [44, 59, 74];         // label rows in the chapter view
  var LINE = 99;                   // the chapter's wire
  var BAND_TOP = 45, BAND_H = 44;  // one 44px target over the labels
  var HIT_TOP = 89, HIT_H = 44;    // 44px zones over the dots
  var NODAL = ["cutoff", "defined-self", "fusion"];
  var WIRE_H = 78, CHAPTER_H = 158, BOARD_H = 264;
  var ASK_GAP_DAYS = 4 * 365;

  function clip(text, chars) {
    text = String(text);
    return text.length > chars ? text.slice(0, Math.max(0, chars - 1)) + "…" : text;
  }

  function nodal(event) {
    return (event.relationshipTargets || []).length >= 2 ||
      NODAL.indexOf(String(event.relationship)) >= 0;
  }

  function scale(minTime, maxTime, x0, x1) {
    var span = maxTime - minTime;
    return function (iso) {
      if (!span) return (x0 + x1) / 2;
      return x0 + (x1 - x0) * (toTime(iso) - minTime) / span;
    };
  }

  function renderWire() {
    var view = $("view");
    var list = chapters();
    view.style.height = WIRE_H + "px";
    if (!list.length) {
      view.innerHTML = "<p>Nothing on your line yet — it draws itself as you talk.</p>";
      return;
    }
    var W = Math.round(view.clientWidth || 380), x0 = 16, x1 = W - 16;
    var X = scale(toTime(list[0].start), toTime(list[list.length - 1].end), x0, x1);
    var svg = '<svg viewBox="0 0 ' + W + " " + WIRE_H + '">';
    svg += '<line x1="' + x0 + '" y1="40" x2="' + x1 + '" y2="40" stroke="var(--line)" stroke-width="1.5"/>';
    list.forEach(function (chapter, index) {
      var xa = X(chapter.start), xb = X(chapter.end);
      var mid = (xa + xb) / 2;
      var left = xa - 10, width = Math.max(44, xb - xa + 20);
      svg += '<g class="ep" data-chapter="' + index + '" role="button" tabindex="0">';
      svg += '<rect x="' + left + '" y="20" width="' + width + '" height="40" rx="8" fill="var(--data)" opacity="0.07"/>';
      svg += '<rect x="' + left + '" y="20" width="' + width + '" height="40" rx="8" fill="none" stroke="var(--data)" stroke-width="1" opacity="0.35"/>';
      if (chapter.count > 8) {
        svg += '<circle cx="' + mid + '" cy="40" r="12" fill="none" stroke="var(--data)" stroke-width="1.5"/>';
        svg += '<text x="' + mid + '" y="45" text-anchor="middle" font-size="13" fill="var(--data)">' + chapter.count + "</text>";
      } else {
        chapter.event_ids.forEach(function (id, j) {
          var at = xa + (xb - xa) * (chapter.count > 1 ? j / (chapter.count - 1) : 0.5);
          svg += '<circle cx="' + at.toFixed(1) + '" cy="40" r="4.5" fill="var(--data)"/>';
        });
      }
      if (width >= 44) {
        var years = chapter.label.length * CH + 8 <= width
          ? chapter.label
          : chapter.label.replace(/(\d\d)(\d\d)/g, "$2");
        svg += '<text x="' + mid + '" y="14" text-anchor="middle" font-size="13" fill="var(--faint)">' + esc(years) + "</text>";
      }
      svg += "</g>";
      if (index && chapter.gap_days >= ASK_GAP_DAYS) {
        var gapX = (X(list[index - 1].end) + xa) / 2;
        svg += '<text x="' + gapX.toFixed(1) + '" y="45" text-anchor="middle" font-size="13" fill="var(--ask)">?</text>';
      }
    });
    svg += '<text x="' + x0 + '" y="74" font-size="13" fill="var(--faint)">tap a chapter</text>';
    view.innerHTML = svg + "</svg>";
  }

  function renderChapter() {
    var view = $("view");
    var chapter = chapters()[S.chapter];
    var list = chapterEvents(S.chapter);
    view.style.height = CHAPTER_H + "px";
    if (!chapter || !list.length) { S.level = 1; renderWire(); return; }

    var W = Math.round(view.clientWidth || 380), x0 = 16, x1 = W - 16;
    var span = toTime(chapter.end) - toTime(chapter.start);
    var pad = Math.max(DAY * 30, span * 0.06);
    var X = scale(toTime(chapter.start) - pad, toTime(chapter.end) + pad, x0, x1);

    var litList = S.lit.map(eventById).filter(function (e) {
      return e && chapter.event_ids.indexOf(e.id) >= 0;
    }).slice(0, 3);
    var selected = S.selected != null ? eventById(S.selected) : null;
    if (selected && chapter.event_ids.indexOf(selected.id) < 0) selected = null;
    var isLit = function (event) {
      return litList.some(function (e) { return e.id === event.id; });
    };

    var count = list.length;
    var radius = count <= 12 ? 4.5 : count <= 30 ? 3.5 : count <= 60 ? 2.6 : 1.8;
    var baseOpacity = litList.length ? 0.35 : (count <= 24 ? 1 : 0.6);

    var keys = [], byDate = {};
    list.forEach(function (event) {
      var key = String(event.dateTime);
      if (!byDate[key]) { byDate[key] = []; keys.push(key); }
      byDate[key].push(event);
    });

    var svg = '<svg viewBox="0 0 ' + W + " " + CHAPTER_H + '" aria-hidden="true">';
    svg += '<line x1="' + x0 + '" y1="' + LINE + '" x2="' + x1 + '" y2="' + LINE + '" stroke="var(--line)" stroke-width="1.5"/>';
    keys.forEach(function (key) {
      var group = byDate[key], at = X(key).toFixed(1);
      var lit = group.filter(isLit);
      if (lit.length) {
        if (group.length > lit.length) {
          svg += '<circle cx="' + at + '" cy="' + LINE + '" r="7" fill="none" stroke="var(--data)" stroke-width="1" opacity="0.35"/>';
        }
        lit.forEach(function (event, i) {
          var cy = i === 0 ? (lit.length > 1 ? 104 : LINE) : i === 1 ? 94 : 104 + 10 * (i - 1);
          if (selected && event.id === selected.id) {
            svg += '<circle cx="' + at + '" cy="' + cy + '" r="7" fill="var(--data)"/>';
          } else if (nodal(event)) {
            svg += '<circle cx="' + at + '" cy="' + cy + '" r="6.5" fill="none" stroke="var(--data)" stroke-width="1.5"/>' +
              '<circle cx="' + at + '" cy="' + cy + '" r="2" fill="var(--data)"/>';
          } else {
            svg += '<circle cx="' + at + '" cy="' + cy + '" r="5" fill="var(--data)"/>';
          }
        });
      } else {
        if (group.length > 1) {
          svg += '<circle cx="' + at + '" cy="' + LINE + '" r="7" fill="none" stroke="var(--data)" stroke-width="1" opacity="' + baseOpacity + '"/>';
        }
        var here = selected && group.some(function (e) { return e.id === selected.id; });
        if (here) {
          svg += '<circle cx="' + at + '" cy="' + LINE + '" r="7" fill="var(--data)"/>';
        } else {
          svg += '<circle cx="' + at + '" cy="' + LINE + '" r="' + radius + '" fill="var(--data)" opacity="' + baseOpacity + '"/>';
        }
      }
    });

    var html = "", labelled = [];
    if (selected) {
      var meta = dateText(selected.dateTime, selected.dateCertainty) +
        (selected.person !== protagonist() && selected.person_name ? " · " + selected.person_name : "");
      var wide = Math.floor((x1 - x0) / CH);
      var full = clip(String(selected.label), Math.min(88, wide * 2));
      var lines = full.length <= wide ? [full, ""] : (function () {
        var cut = full.lastIndexOf(" ", wide);
        if (cut < Math.floor(wide * 0.6)) cut = wide;
        return [full.slice(0, cut).trim(), full.slice(cut).trim()];
      })();
      [meta, lines[0], lines[1]].forEach(function (text, i) {
        if (!text) return;
        html += '<div class="ss-t ' + (i ? "on" : "meta") + '" style="left:' + x0 +
          "px;top:" + ROWS[i] + "px;width:" + (x1 - x0) + 'px">' + esc(text) + "</div>";
      });
    } else if (litList.length) {
      var ordered = litList.slice().sort(function (a, b) { return X(a.dateTime) - X(b.dateTime); });
      var drawn = {};
      ordered.forEach(function (event, i) {
        var at = X(event.dateTime);
        var key = at.toFixed(1);
        if (!drawn[key]) {
          drawn[key] = 1;
          svg += '<line x1="' + key + '" y1="' + LINE + '" x2="' + key + '" y2="' +
            (ROWS[i] + 15) + '" stroke="var(--data)" stroke-width="1" opacity="0.5"/>';
        }
        var budget = Math.min(44, Math.floor((x1 - at - 4) / CH));
        var left = at + 4, width = x1 - left, align = "left";
        if (budget < 12) {
          /* Each label owns its own row, so a crowded right edge can spill
             back to the gutter without colliding with its neighbours. */
          width = (at - 4) - x0;
          budget = Math.min(44, Math.floor(width / CH));
          left = x0;
          align = "right";
        }
        if (budget < 8) return;
        labelled.push({ id: event.id, row: i });
        html += '<div class="ss-t on" style="left:' + left.toFixed(1) + "px;top:" + ROWS[i] +
          "px;width:" + Math.max(0, width).toFixed(1) + "px;text-align:" + align + '">' +
          esc(clip(words(event), budget)) + "</div>";
      });
    }

    html += '<div class="ss-yr" style="left:' + x0 + "px;top:136px\">" + chapter.start.slice(0, 4) + "</div>";
    if (chapter.end.slice(0, 4) !== chapter.start.slice(0, 4)) {
      html += '<div class="ss-yr" style="right:' + x0 + 'px;top:136px">' + chapter.end.slice(0, 4) + "</div>";
    }

    var zoneCount = Math.max(1, Math.floor((x1 - x0) / 44));
    var zoneWidth = (x1 - x0) / zoneCount;
    var zones = [];
    for (var z = 0; z < zoneCount; z++) zones.push([]);
    list.forEach(function (event) {
      var index = Math.min(zoneCount - 1, Math.max(0, Math.floor((X(event.dateTime) - x0) / zoneWidth)));
      zones[index].push(event.id);
    });
    var hits = '<button class="ss-hit" data-band="1" aria-label="Chapter labels" style="left:' +
      x0 + "px;top:" + BAND_TOP + "px;width:" + (x1 - x0) + "px;height:" + BAND_H + 'px"></button>';
    zones.forEach(function (zone, index) {
      if (!zone.length) return;
      hits += '<button class="ss-hit" data-zone="' + index + '" aria-label="Events here" style="left:' +
        (x0 + index * zoneWidth).toFixed(1) + "px;top:" + HIT_TOP + "px;width:" +
        zoneWidth.toFixed(1) + "px;height:" + HIT_H + 'px"></button>';
    });

    view.innerHTML = '<div class="ss" style="height:' + CHAPTER_H + 'px">' + svg + "</svg>" +
      html + hits + "</div>";
    view.querySelector(".ss").zones = zones;
    view.querySelector(".ss").labelled = labelled;
  }

  /* ---- the ratified move vocabulary: one action-green, no other colour ---- */
  var MV = "var(--move)";

  function pairFrame(a, t) {
    var dx = t[0] - a[0], dy = t[1] - a[1];
    return {
      open: '<g transform="translate(' + a[0] + "," + a[1] + ") rotate(" +
        (Math.atan2(dy, dx) * 180 / Math.PI).toFixed(1) + ')">',
      close: "</g>",
      L: Math.hypot(dx, dy)
    };
  }

  function gSpikes(cx, cy, r, n) {
    var out = "";
    for (var i = 0; i < n; i++) {
      var a = (i / n) * 6.283 + (i % 2 ? 0.4 : 0), l = 6 + (i % 3) * 3;
      out += '<line x1="' + (cx + Math.cos(a) * (r + 2)).toFixed(0) + '" y1="' +
        (cy + Math.sin(a) * (r + 2)).toFixed(0) + '" x2="' + (cx + Math.cos(a) * (r + 2 + l)).toFixed(0) +
        '" y2="' + (cy + Math.sin(a) * (r + 2 + l)).toFixed(0) + '" stroke="' + MV +
        '" stroke-width="1.6"><animate attributeName="opacity" values="0;1;.2;1;0" dur="' +
        (0.3 + (i % 3) * 0.15).toFixed(2) + 's" repeatCount="indefinite"/></line>';
    }
    return out;
  }

  function gArrow(x1, y1, x2, y2) {
    var dx = x2 - x1, dy = y2 - y1, L = Math.hypot(dx, dy) || 1;
    var ux = dx / L, uy = dy / L, px = -uy, py = ux;
    return '<line x1="' + x1 + '" y1="' + y1 + '" x2="' + (x2 - ux * 18) + '" y2="' + (y2 - uy * 18) +
      '" stroke="' + MV + '" stroke-width="2.4" stroke-dasharray="8 6" class="flow"/>' +
      '<polygon points="' + (x2 - ux * 16) + "," + (y2 - uy * 16) + " " +
      (x2 - ux * 26 + px * 6) + "," + (y2 - uy * 26 + py * 6) + " " +
      (x2 - ux * 26 - px * 6) + "," + (y2 - uy * 26 - py * 6) + '" fill="' + MV + '"/>';
  }

  function gZig(x1, y1, x2, y2) {
    var L = Math.hypot(x2 - x1, y2 - y1), n = Math.max(4, Math.round(L / 13));
    var dx = (x2 - x1) / n, dy = (y2 - y1) / n;
    var px = -(y2 - y1), py = (x2 - x1), len = Math.hypot(px, py) || 1;
    var ux = px / len * 7, uy = py / len * 7, points = [];
    for (var i = 0; i <= n; i++) {
      var sign = i % 2 ? 1 : -1, inner = i > 0 && i < n;
      points.push((x1 + dx * i + (inner ? ux * sign : 0)).toFixed(0) + "," +
        (y1 + dy * i + (inner ? uy * sign : 0)).toFixed(0));
    }
    var mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
    return '<g class="spark" style="transform-origin:' + mx + "px " + my + 'px"><polyline points="' +
      points.join(" ") + '" fill="none" stroke="' + MV + '" stroke-width="2.2"/></g>';
  }

  function gWallPair(a, t, slash) {
    var frame = pairFrame(a, t), wall = frame.L * 0.45;
    return frame.open +
      '<line x1="' + wall + '" y1="-26" x2="' + wall + '" y2="26" stroke="' + MV + '" stroke-width="4.5"/>' +
      '<line x1="16" y1="0" x2="' + (wall - 3) + '" y2="0" stroke="' + MV +
      '" stroke-width="1.4" stroke-dasharray="3 5" opacity=".55"/>' +
      (slash ? '<line x1="' + (wall - 10) + '" y1="16" x2="' + (wall + 10) +
        '" y2="-16" stroke="' + MV + '" stroke-width="2.6"/>' : "") + frame.close;
  }

  function gWallSolo(x, y, cx, cy, slash) {
    var dx = x - cx, dy = y - cy, L = Math.hypot(dx, dy) || 1;
    var ux = dx / L, uy = dy / L, px = -uy, py = ux;
    var wx = x + ux * 30, wy = y + uy * 30;
    var out = '<line x1="' + (wx + px * 20).toFixed(0) + '" y1="' + (wy + py * 20).toFixed(0) +
      '" x2="' + (wx - px * 20).toFixed(0) + '" y2="' + (wy - py * 20).toFixed(0) +
      '" stroke="' + MV + '" stroke-width="4"/>';
    out += '<line x1="' + (x + ux * 16).toFixed(0) + '" y1="' + (y + uy * 16).toFixed(0) +
      '" x2="' + (wx - ux * 4).toFixed(0) + '" y2="' + (wy - uy * 4).toFixed(0) +
      '" stroke="' + MV + '" stroke-width="1.4" stroke-dasharray="3 5" opacity=".55"/>';
    if (slash) {
      out += '<line x1="' + (wx - px * 9 - ux * 7).toFixed(0) + '" y1="' + (wy - py * 9 - uy * 7).toFixed(0) +
        '" x2="' + (wx + px * 9 + ux * 7).toFixed(0) + '" y2="' + (wy + py * 9 + uy * 7).toFixed(0) +
        '" stroke="' + MV + '" stroke-width="2.4"/>';
    }
    return out;
  }

  function gGhost(x, y, r) {
    return '<g class="shake"><circle cx="' + x + '" cy="' + y + '" r="' + (r + 1) +
      '" fill="none" stroke="' + MV + '" stroke-width="2" opacity=".8"/></g>' + gSpikes(x, y, r, 8);
  }

  function gCross(x, y, up) {
    return '<g transform="translate(' + x + "," + y + ')"><rect x="-7" y="-2.6" width="14" height="5.2" fill="' +
      MV + '" rx="1"/><rect x="-2.6" y="-7" width="5.2" height="14" fill="' + MV + '" rx="1"/></g>' +
      '<line x1="' + (x + 16) + '" y1="' + (up ? y + 9 : y - 9) + '" x2="' + (x + 16) + '" y2="' +
      (up ? y - 9 : y + 9) + '" stroke="' + MV + '" stroke-width="2.2"/>' +
      '<polygon points="' + (x + 16) + "," + (up ? y - 14 : y + 14) + " " + (x + 11) + "," +
      (up ? y - 5 : y + 5) + " " + (x + 21) + "," + (up ? y - 5 : y + 5) + '" fill="' + MV + '"/>';
  }

  function gFlank(x, y, up) {
    var s = up ? -1 : 1;
    return '<line x1="' + x + '" y1="' + (y - 11 * s) + '" x2="' + x + '" y2="' + (y + 11 * s) +
      '" stroke="' + MV + '" stroke-width="2.2"/>' +
      '<line x1="' + x + '" y1="' + (y + 11 * s) + '" x2="' + (x - 5) + '" y2="' + (y + 5 * s) +
      '" stroke="' + MV + '" stroke-width="2.2"/>' +
      '<line x1="' + x + '" y1="' + (y + 11 * s) + '" x2="' + (x + 5) + '" y2="' + (y + 5 * s) +
      '" stroke="' + MV + '" stroke-width="2.2"/>';
  }

  function gRing(x, y) {
    return '<circle cx="' + x + '" cy="' + y + '" r="18" fill="none" stroke="' + MV +
      '" stroke-width="2.2"><animate attributeName="r" values="16;16;60" keyTimes="0;.2;1" ' +
      'dur="2.6s" repeatCount="indefinite"/><animate attributeName="opacity" values="0;.9;0" ' +
      'keyTimes="0;.2;1" dur="2.6s" repeatCount="indefinite"/></circle>';
  }

  function gFusion(a, t) {
    var frame = pairFrame(a, t), mid = frame.L / 2, out = frame.open;
    [-6, 0, 6].forEach(function (k) {
      out += '<line x1="' + (mid - 9) + '" y1="' + k + '" x2="' + (mid + 9) + '" y2="' + k +
        '" stroke="' + MV + '" stroke-width="2.4"/>';
    });
    return out + frame.close;
  }

  function gestureFor(move, pos) {
    var a = pos[move.from], t = (move.to.length && pos[move.to[0]]) || null;
    var gesture = { symbol: "", stroke: {}, slide: null, buzz: [] };
    if (!a) return gesture;
    var kind = move.kind;
    if (kind.endsWith("-up") || kind.endsWith("-down")) {
      var up = kind.endsWith("-up"), base = kind.split("-")[0];
      if (base === "anxiety") {
        gesture.symbol = up ? gGhost(a[0], a[1], 14)
          : '<g opacity=".35">' + gGhost(a[0], a[1], 14) + "</g>";
      } else if (base === "symptom") {
        gesture.symbol = gCross(a[0] + 30, a[1] - 24, up);
      } else {
        gesture.stroke[move.from] = up ? { stroke: MV, dash: null }
          : { stroke: "currentColor", dash: "5 6" };
        if (up) gesture.symbol = gRing(a[0], a[1]);
      }
      return gesture;
    }
    if (!t) {
      if (kind === "cutoff") gesture.symbol = gWallSolo(a[0], a[1], 190, 132, true);
      else if (kind === "distance") gesture.symbol = gWallSolo(a[0], a[1], 190, 132, false);
      else if (kind === "defined-self") {
        gesture.stroke[move.from] = { stroke: MV, dash: null };
        gesture.symbol = gRing(a[0], a[1]);
      } else if (kind === "fusion") {
        gesture.symbol = gFusion(a, [a[0] + 44, a[1]]);
      }
      return gesture;
    }
    if (kind === "conflict") {
      gesture.symbol = gZig(a[0], a[1], t[0], t[1]);
      gesture.buzz = [move.from, move.to[0]];
    }
    else if (kind === "toward") {
      gesture.symbol = gArrow(a[0], a[1], t[0], t[1]);
      gesture.slide = { who: move.from, dx: (t[0] - a[0]) * 0.3, dy: (t[1] - a[1]) * 0.3 };
    } else if (kind === "inside") {
      gesture.slide = { who: move.from, dx: (t[0] - a[0]) * 0.4, dy: (t[1] - a[1]) * 0.4 };
      gesture.symbol = gArrow(a[0], a[1], t[0], t[1]);
    } else if (kind === "away") {
      gesture.symbol = gArrow(t[0], t[1], a[0], a[1]);
      gesture.slide = { who: move.from, dx: -(t[0] - a[0]) * 0.25, dy: -(t[1] - a[1]) * 0.25 };
    } else if (kind === "outside") {
      gesture.slide = { who: move.from, dx: -(t[0] - a[0]) * 0.3, dy: -(t[1] - a[1]) * 0.3 };
    } else if (kind === "distance") gesture.symbol = gWallPair(a, t, false);
    else if (kind === "cutoff") gesture.symbol = gWallPair(a, t, true);
    else if (kind === "projection") {
      gesture.symbol = gArrow(a[0], a[1], t[0], t[1]) + gGhost(a[0], a[1], 14) +
        '<g opacity=".45">' + gSpikes(t[0], t[1], 12, 6) + "</g>";
    } else if (kind === "fusion") gesture.symbol = gFusion(a, t);
    else if (kind === "overfunctioning") {
      gesture.symbol = gFlank(a[0] - 24, a[1], true) + gFlank(t[0] + 24, t[1], false);
    } else if (kind === "underfunctioning") {
      gesture.symbol = gFlank(a[0] - 24, a[1], false) + gFlank(t[0] + 24, t[1], true);
    } else if (kind === "defined-self") {
      gesture.stroke[move.from] = { stroke: MV, dash: null };
      gesture.symbol = gRing(a[0], a[1]) + gArrow(a[0], a[1], t[0], t[1]);
    } else gesture.symbol = gArrow(a[0], a[1], t[0], t[1]);
    return gesture;
  }

  function histMark(move, pos) {
    var a = pos[move.from], t = (move.to.length && pos[move.to[0]]) || null;
    if (!a) return "";
    var kind = move.kind;
    if (kind.indexOf("symptom") === 0) {
      return '<g transform="translate(' + (a[0] + 26) + "," + (a[1] - 20) +
        ') scale(.6)"><rect x="-6" y="-2.2" width="12" height="4.4" fill="' + MV +
        '"/><rect x="-2.2" y="-6" width="4.4" height="12" fill="' + MV + '"/></g>';
    }
    if (kind.indexOf("anxiety") === 0) {
      return '<circle cx="' + a[0] + '" cy="' + a[1] + '" r="16" fill="none" stroke="' + MV + '" stroke-width="1"/>';
    }
    if (kind.indexOf("functioning") === 0) {
      return '<circle cx="' + a[0] + '" cy="' + a[1] + '" r="15" fill="none" stroke="' + MV +
        '" stroke-width="1"' + (kind.endsWith("down") ? ' stroke-dasharray="4 5"' : "") + "/>";
    }
    if (!t) return "";
    if (kind === "conflict") return gZig(a[0], a[1], t[0], t[1]).replace('stroke-width="2.2"', 'stroke-width="1.2"');
    if (kind === "distance" || kind === "cutoff") {
      var frame = pairFrame(a, t), wall = frame.L * 0.45;
      return frame.open + '<line x1="' + wall + '" y1="-18" x2="' + wall + '" y2="18" stroke="' +
        MV + '" stroke-width="2.4"/>' + (kind === "cutoff" ? '<line x1="' + (wall - 7) +
        '" y1="11" x2="' + (wall + 7) + '" y2="-11" stroke="' + MV + '" stroke-width="1.6"/>' : "") +
        frame.close;
    }
    if (kind === "fusion") return gFusion(a, t);
    return '<line x1="' + a[0] + '" y1="' + a[1] + '" x2="' + t[0] + '" y2="' + t[1] +
      '" stroke="' + MV + '" stroke-width="1.4"/>';
  }

  var SHIFT_VARIABLES = ["symptom", "anxiety", "functioning"];

  function movesOf(index) {
    var out = [];
    chapterEvents(index).forEach(function (event) {
      if (event.relationship) {
        out.push({
          kind: event.relationship, from: event.person,
          to: (event.relationshipTargets || []).slice(), event: event
        });
      }
      SHIFT_VARIABLES.forEach(function (variable) {
        if (event[variable] && event[variable] !== "same") {
          out.push({
            kind: variable + "-" + event[variable], from: event.person, to: [], event: event
          });
        }
      });
    });
    return out;
  }

  function renderBoard() {
    var view = $("view");
    var moves = movesOf(S.chapter);
    var chapter = chapters()[S.chapter];
    view.style.height = BOARD_H + "px";
    if (!chapter) { S.level = 1; renderWire(); return; }

    var cast = [];
    moves.forEach(function (move) {
      [move.from].concat(move.to).forEach(function (id) {
        if (id != null && cast.indexOf(id) < 0) cast.push(id);
      });
    });
    if (!cast.length) {
      view.innerHTML = "<p>No moves recorded in this chapter yet.</p>";
      return;
    }
    var bonds = (S.timeline.pair_bonds || []).filter(function (bond) {
      return cast.indexOf(bond.person_a) >= 0 && cast.indexOf(bond.person_b) >= 0;
    });
    var ordered = [];
    cast.forEach(function (id) {
      if (ordered.indexOf(id) < 0) ordered.push(id);
      bonds.forEach(function (bond) {
        var other = bond.person_a === id ? bond.person_b : bond.person_b === id ? bond.person_a : null;
        if (other != null && cast.indexOf(other) >= 0 && ordered.indexOf(other) < 0) ordered.push(other);
      });
    });

    var W = Math.round(view.clientWidth || 380), cx = W / 2, cy = BOARD_H / 2;
    var radius = Math.min(82, (W - 120) / 3.5);
    var pos = {};
    ordered.forEach(function (id, i) {
      var angle = -Math.PI / 2 + i * 2 * Math.PI / ordered.length;
      pos[id] = [cx + radius * 1.75 * Math.cos(angle), cy + radius * Math.sin(angle)];
    });

    var current = moves[S.step - 1];
    var gesture = current ? gestureFor(current, pos)
      : { symbol: "", stroke: {}, slide: null, buzz: [] };
    var svg = '<svg viewBox="0 0 ' + W + " " + BOARD_H + '">';
    bonds.forEach(function (bond) {
      var a = pos[bond.person_a], b = pos[bond.person_b];
      if (a && b) {
        svg += '<line x1="' + a[0] + '" y1="' + a[1] + '" x2="' + b[0] + '" y2="' + b[1] +
          '" stroke="var(--line)" stroke-width="1.2"/>';
      }
    });
    moves.slice(0, Math.max(0, S.step - 1)).forEach(function (move) {
      var mark = histMark(move, pos);
      if (mark) svg += '<g opacity=".16">' + mark + "</g>";
    });
    svg += gesture.symbol;
    ordered.forEach(function (id) {
      var at = pos[id], x = at[0], y = at[1];
      var slide = gesture.slide && gesture.slide.who === id ? gesture.slide : null;
      var moving = slide
        ? '<animateTransform attributeName="transform" type="translate" values="0,0;' +
          slide.dx.toFixed(0) + "," + slide.dy.toFixed(0) + '" dur="1.1s" fill="freeze"/>'
        : "";
      var buzzing = gesture.buzz.indexOf(id) >= 0 ? ' class="buzz"' : "";
      svg += "<g" + buzzing + ">" + moving;
      var override = gesture.stroke[id];
      var stroke = override ? override.stroke : "currentColor";
      var dash = override && override.dash ? ' stroke-dasharray="' + override.dash + '"' : "";
      var width = override ? 2.4 : 1.5;
      var person = people().filter(function (p) { return p.id === id; })[0];
      var mover = current && current.from === id;
      if (person && person.gender === "female") {
        svg += '<circle cx="' + x.toFixed(0) + '" cy="' + y.toFixed(0) + '" r="13" fill="var(--panel)" stroke="' +
          stroke + '" stroke-width="' + width + '"' + dash + "/>";
      } else {
        svg += '<rect x="' + (x - 12).toFixed(0) + '" y="' + (y - 12).toFixed(0) +
          '" width="24" height="24" fill="var(--panel)" stroke="' + stroke +
          '" stroke-width="' + width + '"' + dash + "/>";
      }
      svg += '<text x="' + x.toFixed(0) + '" y="' + (y - 20).toFixed(0) +
        '" text-anchor="middle" font-size="13" fill="' +
        (mover ? MV : "var(--faint)") + '">' + esc(clip(personName(id) || "?", 12)) + "</text></g>";
    });
    view.innerHTML = svg + "</svg>";

    if (current) {
      var to = current.to.map(personName).filter(Boolean).join(", ");
      captionFor(current.event, S.step + "/" + moves.length + " · " +
        dateText(current.event.dateTime, current.event.dateCertainty) + " · " +
        (personName(current.from) || "?") + (to ? " → " + to : "") + " · " + current.event.label);
    } else {
      captionFor(null, "Play " + moves.length + " moves, one at a time.");
    }
  }

  function captionFor(event, text) {
    var html = text ? esc(text) : "";
    var trace = event ? S.timeline.coded_in[String(event.id)] : null;
    if (trace) {
      var named = S.sessions.filter(function (session) {
        return session.id === trace.discussion_id;
      });
      var where = named.length ? clip(sessionTitle(named[0]), 28) : "an earlier session";
      html += ' <span class="chip" data-coded="' + event.id + '">coded in: ' +
        esc(where) + " →</span>";
    }
    $("caption").innerHTML = html;
  }

  function chapterTitle(index) {
    var chapter = chapters()[index];
    return chapter ? chapter.title : "";
  }

  function renderPicture() {
    var navL = $("nav-l"), navR = $("nav-r"), controls = $("pctl");
    navL.replaceChildren(); navR.replaceChildren(); controls.replaceChildren();
    $("caption").textContent = "";
    $("crumb").textContent = "";

    if (S.level === 1) {
      S.selected = null;
      renderWire();
    } else if (S.level === 2) {
      $("crumb").textContent = chapterTitle(S.chapter);
      navR.appendChild(navButton("✕", "Close the chapter", function () { setLevel(1); }));
      renderChapter();
      var count = movesOf(S.chapter).length;
      if (count) {
        var play = document.createElement("button");
        play.className = "btn primary";
        play.type = "button";
        play.textContent = "▶ watch the " + count + " moves";
        play.addEventListener("click", function () { S.level = 3; S.step = 0; renderPicture(); });
        controls.appendChild(play);
      }
    } else {
      $("crumb").textContent = chapterTitle(S.chapter) + " · the moves";
      navL.appendChild(navButton("←", "Back to the chapter", function () { setLevel(2); }));
      renderBoard();
      var back = document.createElement("button");
      back.className = "btn"; back.type = "button"; back.textContent = "◀";
      back.setAttribute("aria-label", "Previous move");
      back.addEventListener("click", function () { S.step = Math.max(0, S.step - 1); renderPicture(); });
      var next = document.createElement("button");
      next.className = "btn primary"; next.type = "button"; next.textContent = "▶ next move";
      next.addEventListener("click", function () {
        S.step = Math.min(movesOf(S.chapter).length, S.step + 1);
        renderPicture();
      });
      controls.appendChild(back);
      controls.appendChild(next);
    }
    controls.appendChild(listButton());
  }

  function navButton(glyph, label, handler) {
    var button = document.createElement("button");
    button.className = "navbtn";
    button.type = "button";
    button.textContent = glyph;
    button.setAttribute("aria-label", label);
    button.addEventListener("click", handler);
    return button;
  }

  function listButton() {
    var button = document.createElement("button");
    button.className = "iconbtn end";
    button.type = "button";
    button.setAttribute("aria-label", "Open the timeline list");
    button.innerHTML = '<svg width="20" height="16" viewBox="0 0 16 12" aria-hidden="true">' +
      '<path d="M1 1h14M1 6h14M1 11h14" stroke="currentColor" stroke-width="1.8" ' +
      'stroke-linecap="round" fill="none"/></svg>';
    button.addEventListener("click", openTimeline);
    return button;
  }

  function setLevel(level) {
    S.level = level;
    if (level < 3) S.step = 0;
    if (level < 2) { S.chapter = null; S.selected = null; }
    renderPicture();
  }

  function openChapter(index) {
    if (index == null || !chapters()[index]) return;
    S.chapter = index;
    S.level = 2;
    S.step = 0;
    renderPicture();
  }

  function selectEvent(id) {
    S.selected = id;
    if (id != null) {
      var index = chapterOfEvent(id);
      if (index == null) { S.selected = null; renderPicture(); return; }
      S.chapter = index;
      S.level = 2;
    }
    renderPicture();
    if (id != null) captionFor(eventById(id), "");
  }

  $("view").addEventListener("click", function (event) {
    var box = event.target.closest("g.ep");
    if (box) { openChapter(+box.dataset.chapter); return; }
    var hit = event.target.closest(".ss-hit");
    if (!hit) return;
    var wrap = $("view").querySelector(".ss");
    if (!wrap) return;
    if (hit.dataset.zone !== undefined) {
      var zone = wrap.zones[+hit.dataset.zone] || [];
      var at = zone.indexOf(S.selected);
      selectEvent(at < 0 ? zone[0] : (zone[at + 1] !== undefined ? zone[at + 1] : null));
      return;
    }
    if (S.selected != null) return;
    if (!wrap.labelled.length) return;
    var box2 = wrap.getBoundingClientRect(), y = event.clientY - box2.top;
    var best = wrap.labelled[0], distance = 1e9;
    wrap.labelled.forEach(function (row) {
      var d = Math.abs(ROWS[row.row] + 7.5 - y);
      if (d < distance) { distance = d; best = row; }
    });
    selectEvent(best.id);
  });

  $("caption").addEventListener("click", function (event) {
    var chip = event.target.closest(".chip[data-coded]");
    if (!chip) return;
    var trace = S.timeline.coded_in[chip.dataset.coded];
    if (trace) jumpToSession(trace.discussion_id, trace.statement_id);
  });

  /* ================================ chat ============================= */

  function chipHtml(index, ref) {
    return '<span class="chip" data-ref="' + index + '">' + esc(ref.label) + " →</span>";
  }

  function messageHtml(message) {
    var html = esc(message.text);
    (message.refs || []).forEach(function (ref, index) {
      var label = esc(ref.label);
      var at = html.indexOf(label);
      if (at >= 0) {
        html = html.slice(0, at) + chipHtml(index, ref) + html.slice(at + label.length);
      } else {
        html += " " + chipHtml(index, ref);
      }
    });
    return html;
  }

  function renderChat() {
    var chat = $("chat");
    if (!S.messages.length) {
      chat.innerHTML = '<div class="empty">Say hello — the picture above fills in as you talk.</div>';
      return;
    }
    chat.innerHTML = S.messages.map(function (message, index) {
      return '<div class="bub ' + (message.role === "coach" ? "coach" : "user") +
        '" data-index="' + index + '" data-statement="' + (message.id || "") + '">' +
        messageHtml(message) + "</div>";
    }).join("");
    chat.scrollTop = chat.scrollHeight;
  }

  function litFromRefs(refs) {
    var lit = [];
    (refs || []).forEach(function (ref) {
      if (ref.kind === "events") lit = lit.concat(ref.event_ids);
      else if (ref.kind === "chapter") lit = lit.concat(eventsOfCluster(ref.cluster_id));
      else if (ref.kind === "person") lit = lit.concat(eventsOfPerson(ref.person_id));
      else if (ref.kind === "range") lit = lit.concat(eventsInRange(ref.start, ref.end));
    });
    return lit.slice(0, 3);
  }

  function eventsOfCluster(clusterId) {
    var found = chapters().filter(function (chapter) {
      return chapter.cluster_ids.indexOf(clusterId) >= 0;
    });
    return found.length ? found[0].event_ids : [];
  }

  function eventsOfPerson(personId) {
    return events().filter(function (event) {
      return event.person === personId || (event.relationshipTargets || []).indexOf(personId) >= 0;
    }).map(function (event) { return event.id; });
  }

  function eventsInRange(start, end) {
    return events().filter(function (event) {
      return event.dateTime && event.dateTime >= start && event.dateTime <= end;
    }).map(function (event) { return event.id; });
  }

  function aim(ref) {
    var ids = litFromRefs([ref]);
    if (!ids.length) return;
    S.lit = ids;
    var index = chapterOfEvent(ids[0]);
    if (index == null) return;
    S.selected = null;
    openChapter(index);
  }

  $("chat").addEventListener("click", function (event) {
    var chip = event.target.closest(".chip[data-ref]");
    if (!chip) return;
    var bubble = chip.closest(".bub");
    var message = S.messages[+bubble.dataset.index];
    aim(message.refs[+chip.dataset.ref]);
  });

  function send(text) {
    var path = S.session ? "/sessions/" + S.session.id + "/statements" : "/chat";
    S.messages.push({ role: "user", text: text, refs: [] });
    renderChat();
    $("chat-send").disabled = true;
    return api("POST", path, { statement: text }).then(function (reply) {
      S.session = reply.session;
      S.messages.push({ role: "coach", text: reply.statement, refs: reply.refs });
      S.lit = litFromRefs(reply.refs);
      if (S.lit.length) S.selected = null;
      renderChat();
      setTitle();
      return refreshTimeline();
    }).catch(failed).then(function () {
      $("chat-send").disabled = false;
      $("chat-input").focus({ preventScroll: true });
    });
  }

  $("chat-form").addEventListener("submit", function (event) {
    event.preventDefault();
    var text = $("chat-input").value.trim();
    if (!text) return;
    $("chat-input").value = "";
    send(text);
  });

  /* ============================== sessions =========================== */

  function sessionTitle(session) {
    return session.title || "Untitled session";
  }

  function sessionSummary(session) {
    return session.summary || (session.message_count ? "In progress" : "Just started");
  }

  function renderSessions() {
    var body = $("sessions-body");
    var query = $("sessions-search").value.trim().toLowerCase();
    var list = S.sessions.filter(function (session) {
      if (!query) return true;
      return (sessionTitle(session) + " " + sessionSummary(session)).toLowerCase().indexOf(query) >= 0;
    });
    if (!list.length) {
      body.innerHTML = '<div class="none">' +
        (S.sessions.length ? "Nothing matches that search." : "No sessions yet.") + "</div>";
      return;
    }
    var html = "", group = null;
    list.forEach(function (session) {
      var when = moment(session.last_activity);
      var label = recencyGroup(when);
      if (label !== group) {
        if (group !== null) html += "</div>";
        group = label;
        html += '<div class="group"><div class="grouphead">' + esc(label) + "</div>";
      }
      html += '<div class="row' + (S.session && session.id === S.session.id ? " cur" : "") +
        '" data-session="' + session.id + '" role="button" tabindex="0">' +
        '<div class="rmain"><div class="r1">' + esc(sessionTitle(session)) + "</div>" +
        '<div class="r2 sans">' + esc(sessionSummary(session)) + "</div></div>" +
        '<div class="rside">' + esc(shortDate(when)) + "</div></div>";
    });
    body.innerHTML = html + "</div>";
    body.querySelectorAll(".row").forEach(function (row) {
      onLongPress(row, function () { renameSession(row); });
    });
  }

  function renameSession(row) {
    var id = +row.dataset.session;
    var session = S.sessions.filter(function (s) { return s.id === id; })[0];
    var title = row.querySelector(".r1");
    var input = document.createElement("input");
    input.className = "rename";
    input.setAttribute("aria-label", "Session title");
    input.value = session.title || "";
    title.replaceChildren(input);
    input.focus({ preventScroll: true });
    input.select();
    var done = false;
    function finish(commit) {
      if (done) return;
      done = true;
      var value = input.value.trim();
      if (commit && value && value !== session.title) {
        api("PATCH", "/sessions/" + id, { title: value }).then(function (updated) {
          session.title = updated.title;
          if (S.session && S.session.id === id) { S.session.title = updated.title; setTitle(); }
          renderSessions();
        }).catch(failed);
      } else {
        renderSessions();
      }
    }
    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter") { event.preventDefault(); finish(true); }
      else if (event.key === "Escape") { event.preventDefault(); finish(false); }
    });
    input.addEventListener("blur", function () { finish(true); });
    input.addEventListener("click", function (event) { event.stopPropagation(); });
  }

  function loadSession(id) {
    return api("GET", "/sessions/" + id).then(function (session) {
      S.session = { id: session.id, title: session.title, summary: session.summary,
                    last_activity: session.last_activity, message_count: session.message_count };
      S.messages = session.statements.map(function (statement) {
        return { id: statement.id, role: statement.role, text: statement.text, refs: [] };
      });
      S.lit = [];
      renderChat();
      setTitle();
    });
  }

  function refreshSessions() {
    return api("GET", "/sessions").then(function (list) {
      S.sessions = list;
      renderSessions();
    });
  }

  function jumpToSession(discussionId, statementId) {
    var open = function () {
      if (statementId == null) return;
      var bubble = $("chat").querySelector('.bub[data-statement="' + statementId + '"]');
      if (!bubble) return;
      var chat = $("chat").getBoundingClientRect(), box = bubble.getBoundingClientRect();
      $("chat").scrollTop += (box.top - chat.top) - (chat.height - box.height) / 2;
      bubble.classList.add("traced");
      setTimeout(function () { bubble.classList.remove("traced"); }, 2400);
    };
    if (S.session && S.session.id === discussionId) { open(); return; }
    loadSession(discussionId).then(open).catch(failed);
  }

  $("sessions-open").addEventListener("click", function () {
    $("sessions").hidden = false;
    $("sessions-search").value = "";
    refreshSessions().catch(failed);
  });
  $("sessions-close").addEventListener("click", function () { $("sessions").hidden = true; });
  $("sessions-search").addEventListener("input", renderSessions);
  $("sessions-new").addEventListener("click", function () {
    api("POST", "/sessions").then(function (session) {
      S.session = session;
      S.messages = [];
      S.lit = [];
      renderChat();
      setTitle();
      $("sessions").hidden = true;
      return refreshSessions();
    }).catch(failed);
  });
  $("sessions-body").addEventListener("click", function (event) {
    var row = event.target.closest(".row[data-session]");
    if (!row) return;
    loadSession(+row.dataset.session).then(function () {
      $("sessions").hidden = true;
    }).catch(failed);
  });

  /* ============================== settings =========================== */

  var CHEVRON = '<svg class="chev" viewBox="0 0 9 15" aria-hidden="true"><path d="M1.5 1.5 7 7.5 1.5 13.5" ' +
    'stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  var PAGES = {
    root: { title: "Settings", render: renderSettingsRoot },
    profile: { title: "Profile", render: renderProfile },
    coach: { title: "Coach", render: renderCoach },
    appearance: { title: "Appearance", render: renderAppearance },
    diagrams: { title: "Your diagrams", render: renderDiagrams },
    plan: { title: "Plan and licenses", render: renderPlan },
    signin: { title: "Email and sign-in", render: renderSignIn }
  };

  function pushPage(name) {
    S.settings.push(name);
    S.screen = "settings";
    renderScreen();
  }

  function popPage() {
    S.settings.pop();
    if (!S.settings.length) S.screen = "chat";
    renderScreen();
  }

  function plural(count, noun) {
    return count + " " + noun + (count === 1 ? "" : "s");
  }

  function settingsRow(name, value) {
    return '<div class="row" data-page="' + name + '" role="button" tabindex="0">' +
      '<div class="rmain"><div class="r1">' + esc(PAGES[name].title) + "</div></div>" +
      '<div class="rside">' + esc(value || "") + "</div>" + CHEVRON + "</div>";
  }

  function renderSettingsRoot(body) {
    var user = S.prefs || {};
    var name = [user.first_name, user.last_name].filter(Boolean).join(" ");
    body.innerHTML =
      '<div class="sechead">You</div>' +
      settingsRow("profile", name) +
      settingsRow("coach", S.prefs ? (S.prefs.speak ? "speaks" : "silent") : "") +
      settingsRow("appearance", S.prefs ? S.prefs.theme : "") +
      '<div class="sechead">Your record</div>' +
      settingsRow("diagrams", S.account ? String(S.account.diagrams.length) : "") +
      settingsRow("plan", S.account ? plural(S.account.licenses.length, "license") : "") +
      '<div class="sechead">Account</div>' +
      settingsRow("signin", S.account ? S.account.email : "");
  }

  function textRow(label, key, value, type) {
    return '<div class="fieldrow"><label for="pref-' + key + '">' + esc(label) + "</label>" +
      '<input id="pref-' + key + '" data-pref="' + key + '" type="' + (type || "text") +
      '" value="' + esc(value || "") + '"></div>';
  }

  function renderProfile(body) {
    body.innerHTML =
      '<div class="sechead">What the coach calls you</div>' +
      textRow("First name", "first_name", S.prefs.first_name) +
      textRow("Last name", "last_name", S.prefs.last_name) +
      textRow("Birthdate", "birthdate", S.prefs.birthdate, "date") +
      '<div class="note">Your birthdate anchors your own line on the picture.</div>';
    body.querySelectorAll("[data-pref]").forEach(function (input) {
      input.addEventListener("change", function () {
        var patch = {};
        patch[input.dataset.pref] = input.value || null;
        savePrefs(patch);
      });
    });
  }

  function segments(key, values, current) {
    return '<div class="segs" data-pref="' + key + '">' + values.map(function (value) {
      return '<button type="button" class="seg' + (value === current ? " on" : "") +
        '" data-value="' + value + '">' + esc(value) + "</button>";
    }).join("") + "</div>";
  }

  function renderCoach(body) {
    body.innerHTML =
      '<div class="sechead">Replies</div>' +
      '<div class="fieldrow"><label>Speak replies</label>' +
      '<button class="switch" id="pref-speak" role="switch" aria-label="Speak replies" aria-checked="' +
      (S.prefs.speak ? "true" : "false") + '"><i></i></button></div>' +
      '<div class="segrow"><span>Voice or text</span>' + segments("mode", ["text", "voice"], S.prefs.mode) + "</div>" +
      '<div class="sechead">Messaging you first</div>' +
      '<div class="segrow"><span>How often</span>' +
      segments("proactive", ["never", "rarely", "weekly"], S.prefs.proactive) + "</div>" +
      '<div class="note">The coach never messages first unless you ask it to.</div>';
    $("pref-speak").addEventListener("click", function () {
      savePrefs({ speak: !S.prefs.speak });
    });
    wireSegments(body);
  }

  function renderAppearance(body) {
    body.innerHTML = '<div class="sechead">Theme</div>' +
      '<div class="segrow"><span>Theme</span>' +
      segments("theme", ["system", "light", "dark"], S.prefs.theme) + "</div>";
    wireSegments(body);
  }

  function wireSegments(body) {
    body.querySelectorAll(".segs[data-pref]").forEach(function (group) {
      group.addEventListener("click", function (event) {
        var button = event.target.closest(".seg");
        if (!button) return;
        var patch = {};
        patch[group.dataset.pref] = button.dataset.value;
        savePrefs(patch);
      });
    });
  }

  function renderDiagrams(body) {
    var list = S.account.diagrams;
    var search = list.length > 8
      ? '<div class="searchbar"><input id="diagram-search" placeholder="Search diagrams" aria-label="Search diagrams"></div>'
      : "";
    var rows = function (query) {
      return list.filter(function (diagram) {
        return !query || String(diagram.name || "").toLowerCase().indexOf(query) >= 0;
      }).map(function (diagram) {
        return '<div class="row' + (diagram.free ? " cur" : "") + '" role="button" tabindex="0">' +
          '<div class="rmain"><div class="r1">' + esc(diagram.name || "Untitled") + "</div>" +
          '<div class="r2">' + (diagram.last_activity ? esc(shortDate(moment(diagram.last_activity))) : "never saved") +
          (diagram.free ? " · in use" : "") + "</div></div></div>";
      }).join("") || '<div class="none">Nothing matches that search.</div>';
    };
    body.innerHTML = search + '<div id="diagram-rows">' + rows("") + "</div>";
    var input = $("diagram-search");
    if (input) {
      input.addEventListener("input", function () {
        $("diagram-rows").innerHTML = rows(input.value.trim().toLowerCase());
      });
    }
  }

  function renderPlan(body) {
    var licenses = S.account.licenses.map(function (license) {
      return '<div class="row"><div class="rmain"><div class="r1">' + esc(license.policy) + "</div>" +
        '<div class="r2">' + esc(license.status) + "</div></div></div>";
    }).join("") || '<div class="none">No licenses on this account.</div>';
    body.innerHTML = '<div class="sechead">Plan</div>' +
      '<div class="note">' + esc(S.account.plan) + "</div>" +
      '<div class="sechead">Licenses</div>' + licenses;
  }

  function renderSignIn(body) {
    body.innerHTML = '<div class="sechead">Sign-in</div>' +
      '<div class="fieldrow"><label>Email</label><div class="r1">' + esc(S.account.email) + "</div></div>" +
      '<div class="fieldrow"><label>Method</label><div class="r1">' + esc(S.account.sign_in_method) + "</div></div>" +
      '<div class="foot" style="border:none;background:none"><button class="btn danger" id="signout" type="button">Sign out</button></div>';
    $("signout").addEventListener("click", function () { $("signout-form").submit(); });
  }

  function savePrefs(patch) {
    return api("PATCH", "/preferences", patch).then(function (prefs) {
      S.prefs = prefs;
      applyTheme();
      $("speak").checked = !!prefs.speak;
      renderScreen();
    }).catch(failed);
  }

  function applyTheme() {
    var theme = S.prefs ? S.prefs.theme : "system";
    if (theme === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
  }

  $("settings-body").addEventListener("click", function (event) {
    var row = event.target.closest(".row[data-page]");
    if (row) pushPage(row.dataset.page);
  });

  $("avatar").addEventListener("click", function () {
    S.settings = ["root"];
    S.screen = "settings";
    renderScreen();
  });

  $("speak-row").addEventListener("click", function (event) {
    if (event.target === $("speak")) return;
    event.preventDefault();
    savePrefs({ speak: !S.prefs.speak });
  });
  $("speak").addEventListener("change", function () {
    if ($("speak").checked !== !!S.prefs.speak) savePrefs({ speak: $("speak").checked });
  });

  /* =========================== timeline list ========================= */

  var KINDS = ["shift", "birth", "adopted", "bonded", "married", "separated",
               "divorced", "moved", "death"];
  var PAIR_KINDS = ["bonded", "married", "separated", "divorced"];
  var CHILD_KINDS = ["birth", "adopted"];
  var DIRECTIONS = ["up", "down", "same"];
  var RELATIONSHIPS = ["fusion", "conflict", "distance", "overfunctioning", "underfunctioning",
                       "projection", "defined-self", "toward", "away", "inside", "outside", "cutoff"];
  var CERTAINTIES = ["unknown", "approximate", "certain"];
  var TARGET_LABELS = {
    conflict: "Other(s)", distance: "Other(s)", overfunctioning: "Underfunctioner(s)",
    underfunctioning: "Overfunctioner(s)", projection: "Focused", inside: "Inside(s)",
    outside: "Inside(s) 1", toward: "To", away: "From", "defined-self": "In relation to"
  };
  var ARROWS = { up: "↑", down: "↓", same: "=" };

  function targetLabel(relationship) {
    return TARGET_LABELS[relationship] || "Person 2";
  }

  function triangleLabel(relationship) {
    return relationship === "inside" ? "Outside(s)" : relationship === "outside" ? "Inside(s) 2" : "";
  }

  function codes(event) {
    var out = [];
    [["symptom", "S"], ["anxiety", "A"], ["functioning", "F"]].forEach(function (pair) {
      if (event[pair[0]]) out.push(pair[1] + ARROWS[event[pair[0]]]);
    });
    if (event.relationship) {
      var targets = (event.relationshipTargets || []).map(personName).filter(Boolean);
      var triangles = (event.relationshipTriangles || []).map(personName).filter(Boolean);
      out.push("R " + event.relationship + (targets.length ? "→" + targets.join(",") : "") +
        (triangles.length ? " △" + triangles.join(",") : ""));
    }
    return out.join("  ");
  }

  function matches(event, query) {
    var hay = (event.label + " " + (event.person_name || "") + " " + (event.notes || "") + " " +
      (event.location || "") + " " + codes(event)).toLowerCase();
    return query.toLowerCase().split(/\s+/).filter(Boolean).every(function (word) {
      return hay.indexOf(word) >= 0;
    });
  }

  function renderTimelineList() {
    var body = $("tl-body");
    var query = S.search.trim();
    var index = {};
    chapters().forEach(function (chapter, i) {
      chapter.event_ids.forEach(function (id) { index[id] = i; });
    });
    var unplaced = events().filter(function (event) { return index[event.id] === undefined; }).length;
    var html = "", last = "none", shown = 0;
    events().forEach(function (event) {
      if (query && !matches(event, query)) return;
      var chapterIndex = index[event.id];
      var key = chapterIndex === undefined ? "unplaced" : String(chapterIndex);
      if (key !== last) {
        if (last !== "none") html += "</div>";
        last = key;
        var chapter = chapters()[chapterIndex];
        html += '<div class="group"><div class="divider"><span>' + esc(chapter ? chapter.label : "No date yet") +
          '</span><span class="count">' + plural(chapter ? chapter.count : unplaced, "event") +
          "</span></div>";
      }
      html += '<div class="row' + (S.editing === event.id ? " on" : "") + '" data-event="' + event.id +
        '" role="button" tabindex="0"><div class="rmain"><div class="r1">' +
        esc(event.label) + '</div><div class="r2">' +
        esc([dateText(event.dateTime, event.dateCertainty), event.person_name, codes(event)]
          .filter(Boolean).join(" · ")) + "</div></div></div>";
      shown++;
    });
    if (shown) html += "</div>";
    if (!shown) {
      html = '<div class="none">' +
        (events().length ? "Nothing matches that search." : "Nothing on your timeline yet.") + "</div>";
    }
    var top = body.scrollTop;
    body.innerHTML = html;
    body.scrollTop = top;
    if (S.adding) openEditor(null);
    else if (S.editing != null) openEditor(eventById(S.editing));
  }

  function optionChips(name, values, current, multiple) {
    return '<div class="segs" data-name="' + name + '" data-multiple="' + (multiple ? "1" : "") + '">' +
      values.map(function (option) {
        var on = multiple ? current.indexOf(option.value) >= 0 : String(current) === String(option.value);
        return '<button type="button" class="seg' + (on ? " on" : "") + '" data-value="' +
          esc(option.value) + '">' + esc(option.label) + "</button>";
      }).join("") + "</div>";
  }

  function plainOptions(values) {
    return values.map(function (value) { return { value: value, label: value }; });
  }

  function personOptions(withNone) {
    var options = people().map(function (person) {
      return { value: person.id, label: person.name };
    });
    return withNone ? [{ value: "", label: "nobody" }].concat(options) : options;
  }

  function field(label, name, value, type) {
    return '<div class="lab">' + esc(label) + "</div>" +
      (type === "text"
        ? '<textarea class="f" data-name="' + name + '" rows="1">' + esc(value || "") + "</textarea>"
        : '<input class="f" data-name="' + name + '" type="' + (type || "text") + '" value="' +
          esc(value == null ? "" : value) + '">');
  }

  function openEditor(event) {
    var editor = document.createElement("div");
    editor.className = "editor";
    var kind = event ? event.kind : "shift";
    var relationship = event && event.relationship ? event.relationship : "";
    editor.innerHTML =
      '<div class="sec">What</div>' + optionChips("kind", plainOptions(KINDS), kind) +
      '<div class="sec">Who</div>' +
      '<div class="lab">Person</div>' + optionChips("person", personOptions(true), event && event.person != null ? event.person : "") +
      '<div data-block="pair"' + (PAIR_KINDS.indexOf(kind) < 0 ? " hidden" : "") + '>' +
      '<div class="lab">With</div>' + optionChips("spouse", personOptions(true), event && event.spouse != null ? event.spouse : "") + "</div>" +
      '<div data-block="child"' + (CHILD_KINDS.indexOf(kind) < 0 ? " hidden" : "") + '>' +
      '<div class="lab">Child</div>' + optionChips("child", personOptions(true), event && event.child != null ? event.child : "") + "</div>" +
      '<div class="sec">Words</div>' +
      field("Summary", "description", event && event.description, "text") +
      field("Details", "notes", event && event.notes, "text") +
      field("Where", "location", event && event.location) +
      '<div class="sec">When</div>' +
      field("When", "dateTime", event && event.dateTime, "date") +
      field("Ended (optional)", "endDateTime", event && event.endDateTime, "date") +
      '<div class="lab">Certainty</div>' +
      optionChips("dateCertainty", plainOptions(CERTAINTIES), event ? event.dateCertainty : "certain") +
      '<div data-block="shift"' + (kind !== "shift" ? " hidden" : "") + '>' +
      '<div class="sec">Shifts</div>' +
      SHIFT_VARIABLES.map(function (variable) {
        return '<div class="lab">Δ ' + variable + "</div>" +
          optionChips(variable, plainOptions(DIRECTIONS.concat([""])).map(function (option) {
            return { value: option.value, label: option.value || "none" };
          }), event && event[variable] ? event[variable] : "");
      }).join("") +
      '<div class="lab">Δ relationship</div>' +
      optionChips("relationship", [{ value: "", label: "none" }].concat(plainOptions(RELATIONSHIPS)), relationship) +
      '<div data-block="targets"' + (relationship ? "" : " hidden") + '>' +
      '<div class="lab" data-label="targets">' + esc(targetLabel(relationship)) + "</div>" +
      optionChips("relationshipTargets", personOptions(false), (event && event.relationshipTargets) || [], true) + "</div>" +
      '<div data-block="triangles"' + (relationship === "inside" || relationship === "outside" ? "" : " hidden") + '>' +
      '<div class="lab" data-label="triangles">' + esc(triangleLabel(relationship)) + "</div>" +
      optionChips("relationshipTriangles", personOptions(false), (event && event.relationshipTriangles) || [], true) +
      "</div></div>" +
      '<div class="acts"><button class="save" type="button">Save</button>' +
      (event ? '<button class="del" type="button">Delete</button>' : "") + "</div>";

    if (event) {
      var row = $("tl-body").querySelector('.row[data-event="' + event.id + '"]');
      if (!row) return;
      row.after(editor);
    } else {
      $("tl-body").prepend(editor);
    }

    editor.querySelectorAll("textarea").forEach(function (area) {
      var grow = function () { area.style.height = "auto"; area.style.height = area.scrollHeight + "px"; };
      area.addEventListener("input", grow);
      grow();
    });
    editor.querySelectorAll(".segs").forEach(function (group) {
      group.addEventListener("click", function (clicked) {
        var button = clicked.target.closest(".seg");
        if (!button) return;
        if (group.dataset.multiple) {
          button.classList.toggle("on");
        } else {
          group.querySelectorAll(".seg").forEach(function (other) {
            other.classList.toggle("on", other === button);
          });
        }
        if (group.dataset.name === "kind") {
          var value = button.dataset.value;
          editor.querySelector('[data-block="pair"]').hidden = PAIR_KINDS.indexOf(value) < 0;
          editor.querySelector('[data-block="child"]').hidden = CHILD_KINDS.indexOf(value) < 0;
          editor.querySelector('[data-block="shift"]').hidden = value !== "shift";
        }
        if (group.dataset.name === "relationship") {
          var chosen = button.dataset.value;
          editor.querySelector('[data-block="targets"]').hidden = !chosen;
          editor.querySelector('[data-label="targets"]').textContent = targetLabel(chosen);
          var triangle = chosen === "inside" || chosen === "outside";
          editor.querySelector('[data-block="triangles"]').hidden = !triangle;
          editor.querySelector('[data-label="triangles"]').textContent = triangleLabel(chosen);
        }
      });
    });
    editor.querySelector(".save").addEventListener("click", function () { saveEvent(event, editor); });
    var remove = editor.querySelector(".del");
    if (remove) {
      remove.addEventListener("click", function () {
        api("DELETE", "/events/" + event.id).then(function () {
          S.editing = null;
          return refreshTimeline();
        }).then(renderTimelineList).catch(failed);
      });
    }
  }

  function saveEvent(event, editor) {
    var one = function (name) {
      var on = editor.querySelector('.segs[data-name="' + name + '"] .seg.on');
      return on && on.dataset.value !== "" ? on.dataset.value : null;
    };
    var many = function (name) {
      return Array.prototype.map.call(
        editor.querySelectorAll('.segs[data-name="' + name + '"] .seg.on'),
        function (button) { return +button.dataset.value; });
    };
    var text = function (name) {
      var node = editor.querySelector('[data-name="' + name + '"]');
      return node && node.value.trim() ? node.value.trim() : null;
    };
    var number = function (name) {
      var value = one(name);
      return value === null ? null : +value;
    };
    var body = {
      kind: one("kind"),
      person: number("person"),
      spouse: number("spouse"),
      child: number("child"),
      description: text("description"),
      notes: text("notes"),
      location: text("location"),
      dateTime: text("dateTime"),
      endDateTime: text("endDateTime"),
      dateCertainty: one("dateCertainty") || "certain",
      symptom: one("symptom"),
      anxiety: one("anxiety"),
      functioning: one("functioning"),
      relationship: one("relationship"),
      relationshipTargets: many("relationshipTargets"),
      relationshipTriangles: many("relationshipTriangles")
    };
    var request = event
      ? api("PATCH", "/events/" + event.id, body)
      : api("POST", "/events", body);
    request.then(function () {
      S.editing = null;
      S.adding = false;
      return refreshTimeline();
    }).then(renderTimelineList).catch(failed);
  }

  function openTimeline() {
    S.screen = "timeline";
    S.search = "";
    S.editing = null;
    S.adding = false;
    $("tl-search").value = "";
    renderScreen();
    $("tl-body").scrollTop = 0;
  }

  $("tl-search").addEventListener("input", function () {
    S.search = $("tl-search").value;
    S.editing = null;
    S.adding = false;
    renderTimelineList();
  });
  $("tl-add").addEventListener("click", function () {
    S.editing = null;
    S.adding = true;
    $("tl-body").scrollTop = 0;
    renderTimelineList();
  });
  $("tl-body").addEventListener("click", function (event) {
    var row = event.target.closest(".row[data-event]");
    if (!row) return;
    var id = +row.dataset.event;
    S.adding = false;
    S.editing = S.editing === id ? null : id;
    renderTimelineList();
  });

  /* ============================== screens ============================ */

  function setTitle() {
    if (S.screen === "settings") {
      $("title").textContent = PAGES[S.settings[S.settings.length - 1]].title;
    } else if (S.screen === "timeline") {
      $("title").textContent = "Timeline";
    } else {
      $("title").textContent = S.session ? sessionTitle(S.session) : "Your family";
    }
  }

  function renderScreen() {
    $("chat-screen").hidden = S.screen !== "chat";
    $("timeline-screen").hidden = S.screen !== "timeline";
    $("settings-screen").hidden = S.screen !== "settings";
    var back = $("back");
    if (S.screen === "chat") {
      back.hidden = true;
    } else {
      back.hidden = false;
      $("back-label").textContent = S.screen === "timeline" ? "Chat"
        : S.settings.length > 1 ? PAGES[S.settings[S.settings.length - 2]].title : "Chat";
    }
    setTitle();
    if (S.screen === "timeline") renderTimelineList();
    if (S.screen === "settings") {
      var body = $("settings-body");
      body.replaceChildren();
      PAGES[S.settings[S.settings.length - 1]].render(body);
      body.scrollTop = 0;
    }
    if (S.screen === "chat") renderPicture();
  }

  $("back").addEventListener("click", function () {
    if (S.screen === "settings") popPage();
    else { S.screen = "chat"; renderScreen(); }
  });

  function renderFreshness() {
    var notes = {
      extracting: "Updating the picture from your conversation…",
      pending_review: "New details from your conversation are waiting to be added.",
      chat_ahead: "The picture may be a little behind the conversation."
    };
    $("freshness").textContent = notes[S.timeline.extraction.state] || "";
  }

  function refreshTimeline() {
    return api("GET", "/timeline").then(function (timeline) {
      S.timeline = timeline;
      if (S.chapter != null && !chapters()[S.chapter]) { S.chapter = null; S.level = 1; }
      renderFreshness();
      if (S.screen === "chat") renderPicture();
    });
  }

  window.addEventListener("resize", function () {
    if (S.timeline && S.screen === "chat") renderPicture();
  });

  /* =============================== boot ============================== */

  function avatarMark() {
    var user = window.COMPANION.user;
    var initial = ((user.first_name || user.last_name || user.username || "").trim()[0] || "").toUpperCase();
    if (initial) $("avatar-mark").textContent = initial;
    else {
      $("avatar").innerHTML = '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="5" r="3"/>' +
        '<path d="M2 15c0-3.3 2.7-5.5 6-5.5s6 2.2 6 5.5z"/></svg>';
    }
  }

  S.session = window.COMPANION.session;
  S.messages = (window.COMPANION.statements || []).map(function (statement) {
    return { id: statement.id, role: statement.role, text: statement.text, refs: [] };
  });
  avatarMark();
  renderChat();
  renderScreen();

  Promise.all([
    refreshTimeline(),
    refreshSessions(),
    api("GET", "/preferences").then(function (prefs) {
      S.prefs = prefs;
      applyTheme();
      $("speak").checked = !!prefs.speak;
    }),
    api("GET", "/account").then(function (account) { S.account = account; })
  ]).catch(failed);
})();
