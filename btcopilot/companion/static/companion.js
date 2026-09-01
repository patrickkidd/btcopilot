/* Companion page: chat + timeline picture, rendered from /companion/timeline.
   Strip (DRAWABILITY cartoon rule): line, dots, amber "?" only.
   Expanded view: linear inside an era, visibly compressed between eras —
   empty spans collapse into labeled bridges ("12 quiet years"), far-out eras
   render as labeled blocks, marks and per-mark year labels appear as you zoom.
   Pan: drag. Zoom: wheel/pinch, linear within eras. Double-tap an era fits it. */
(function () {
  "use strict";

  var SVGNS = "http://www.w3.org/2000/svg";
  var DAY = 86400000;
  var BRIDGE_W = 64;
  var ERA_PAD_DAYS = 240;
  var ERA_BLOCK_MIN = 110;
  var ROW_H = 56;
  var AXIS_H = 10;
  var HEAD_H = 22;
  var csrfToken = document.querySelector('meta[name="csrf-token"]').content;
  var state = { data: null, view: null };

  function css(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function el(name, attrs, parent) {
    var node = document.createElementNS(SVGNS, name);
    for (var k in attrs) node.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(node);
    return node;
  }

  function text(parent, x, y, str, size, color, anchor) {
    var t = el("text", { x: x, y: y, "text-anchor": anchor || "middle" }, parent);
    t.textContent = str;
    t.style.font = "500 " + size + "px " + css("--mono");
    t.style.fill = color;
    return t;
  }

  function parseDate(iso) {
    var p = iso.split("-");
    return new Date(+p[0], +p[1] - 1, +p[2]).getTime();
  }

  function mark(parent, tag, attrs, sentence) {
    var node = el(tag, attrs, parent);
    if (sentence) {
      node.dataset.sentence = sentence;
      node.style.cursor = "pointer";
    }
    return node;
  }

  /* ================= strip (unchanged vocabulary) ================= */

  function makeLinearX(axis, width, pad) {
    var t0 = parseDate(axis.min), t1 = parseDate(axis.max);
    if (t1 <= t0) t1 = t0 + 1;
    return function (iso) {
      return pad + ((parseDate(iso) - t0) / (t1 - t0)) * (width - 2 * pad);
    };
  }

  function laneY(v, vMin, vMax, top, bottom) {
    if (vMax === vMin) return (top + bottom) / 2;
    return bottom - ((v - vMin) / (vMax - vMin)) * (bottom - top);
  }

  function stepPath(coords, x, y) {
    var d = "";
    coords.forEach(function (c, i) {
      var px = x(c[0]), py = y(c[1]);
      if (i === 0) d += "M" + px + " " + py;
      else d += "H" + px + "V" + py;
    });
    return d;
  }

  function questionGlyph(parent, px, py, sentence) {
    var g = el("g", {}, parent);
    mark(g, "circle", {
      cx: px, cy: py, r: 6.5, fill: css("--card"),
      stroke: css("--unsure"), "stroke-width": 1.3
    }, sentence);
    var t = mark(g, "text", { x: px, y: py + 3, "text-anchor": "middle" }, sentence);
    t.textContent = "?";
    t.style.font = "500 9px " + css("--mono");
    t.style.fill = css("--unsure");
    return g;
  }

  function renderStrip() {
    var svg = document.getElementById("strip");
    var data = state.data;
    svg.innerHTML = "";
    var width = svg.parentNode.clientWidth - 16 || 320;
    var lanes = data.strip.lanes;
    var rowH = 34, height = Math.max(1, lanes.length) * rowH + 14;
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    svg.setAttribute("height", height);
    if (!data.axis || !lanes.length) {
      text(svg, width / 2, height / 2 + 4,
        "The picture appears here as you talk", 11, css("--muted"));
      return;
    }
    var x = makeLinearX(data.axis, width, 8);
    lanes.forEach(function (lane, i) {
      var top = i * rowH + 12, bottom = (i + 1) * rowH - 6;
      text(svg, 8, i * rowH + 9, lane.label, 8.5, css("--muted"), "start");
      function y(v) { return laneY(v, lane.v_min, lane.v_max, top, bottom); }
      if (lane.line) {
        el("path", {
          d: stepPath(lane.line, x, y), fill: "none",
          stroke: css("--draw"), "stroke-width": 1.6, "stroke-linejoin": "round"
        }, svg);
      }
      lane.marks.forEach(function (m) {
        el("circle", { cx: x(m.date), cy: y(m.value), r: 2.5, fill: css("--draw") }, svg);
      });
      var lastQ = -1e9;
      lane.questions.forEach(function (q) {
        var qx = x(q.date);
        if (qx - lastQ < 14) return;
        lastQ = qx;
        questionGlyph(svg, qx, (top + bottom) / 2, null);
      });
    });
    var y0 = +data.axis.min.slice(0, 4), y1 = +data.axis.max.slice(0, 4);
    var step = Math.max(1, Math.ceil((y1 - y0) / 5));
    for (var yr = y0; yr <= y1; yr += step) {
      var px = x(yr + "-01-01");
      text(svg, Math.max(2, px), height - 3, yr, 9, css("--muted"),
        px < 22 ? "start" : "middle");
    }
  }

  /* ================= expanded view: era-compressed time ================= */

  function buildView() {
    var eras = state.data.eras.map(function (e) {
      return {
        t0: parseDate(e.a) - ERA_PAD_DAYS * DAY,
        t1: parseDate(e.b) + ERA_PAD_DAYS * DAY,
        a: e.a, b: e.b, count: e.count
      };
    });
    var totalDays = eras.reduce(function (sum, e) {
      return sum + (e.t1 - e.t0) / DAY;
    }, 0);
    return { eras: eras, totalDays: totalDays, s: null, pan: 0, width: 0 };
  }

  function layout(view) {
    var x = 0;
    view.eras.forEach(function (e, i) {
      e.x0 = x;
      e.w = ((e.t1 - e.t0) / DAY) * view.s;
      x += e.w;
      if (i < view.eras.length - 1) {
        e.bridgeX = x;
        e.bridgeYears = Math.max(
          1, Math.round((view.eras[i + 1].t0 - e.t1) / DAY / 365)
        );
        x += BRIDGE_W;
      }
    });
    view.contentW = x;
  }

  function fitAll(view, width) {
    var bridges = (view.eras.length - 1) * BRIDGE_W;
    view.s = Math.max(0.0001, (width - bridges - 16) / view.totalDays);
    view.minS = view.s * 0.8;
    view.pan = -8;
    layout(view);
  }

  function xOf(view, tms) {
    for (var i = 0; i < view.eras.length; i++) {
      var e = view.eras[i];
      if (tms <= e.t1 || i === view.eras.length - 1) {
        var t = Math.max(e.t0, Math.min(tms, e.t1));
        return e.x0 + ((t - e.t0) / DAY) * view.s - view.pan;
      }
      if (tms < view.eras[i + 1].t0) {
        return e.x0 + e.w + BRIDGE_W / 2 - view.pan;
      }
    }
    return 0;
  }

  function tOf(view, px) {
    var cx = px + view.pan;
    for (var i = 0; i < view.eras.length; i++) {
      var e = view.eras[i];
      if (cx <= e.x0 + e.w || i === view.eras.length - 1) {
        return e.t0 + Math.max(0, Math.min(cx - e.x0, e.w)) / view.s * DAY;
      }
      if (cx < e.x0 + e.w + BRIDGE_W) return e.t1;
    }
    return view.eras[0].t0;
  }

  function eraAt(view, px) {
    var cx = px + view.pan;
    for (var i = 0; i < view.eras.length; i++) {
      var e = view.eras[i];
      if (cx >= e.x0 && cx <= e.x0 + e.w) return e;
    }
    return null;
  }

  function fitEra(view, era, width) {
    view.s = Math.max(view.minS, (width - 32) / ((era.t1 - era.t0) / DAY));
    layout(view);
    view.pan = era.x0 - 16;
    clampPan(view, width);
  }

  function clampPan(view, width) {
    view.pan = Math.max(-8, Math.min(view.pan, view.contentW - width + 8));
  }

  function zoomAt(view, px, factor, width) {
    var t = tOf(view, px);
    view.s = Math.max(view.minS, Math.min(30, view.s * factor));
    layout(view);
    view.pan = xOf({ eras: view.eras, s: view.s, pan: 0 }, t) - px;
    clampPan(view, width);
  }

  function renderExpanded() {
    var svg = document.getElementById("expanded");
    var data = state.data;
    svg.innerHTML = "";
    var width = svg.parentNode.clientWidth - 20 || 320;
    var lanes = data.lanes;
    var bondLanes = data.bond_lanes;
    var rows = lanes.length + bondLanes.length;
    var height = HEAD_H + Math.max(1, rows) * ROW_H + AXIS_H;
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    svg.setAttribute("height", height);
    if (!data.axis || !rows) {
      text(svg, width / 2, 30, "Nothing to draw yet", 11, css("--muted"));
      return;
    }
    var view = state.view;
    if (view.s === null || view.width !== width) {
      view.width = width;
      fitAll(view, width);
    }
    var x = function (iso) { return xOf(view, parseDate(iso)); };
    var openEra = function (iso) {
      var t = parseDate(iso);
      for (var i = 0; i < view.eras.length; i++) {
        var e = view.eras[i];
        if (t >= e.t0 - 1 && t <= e.t1 + 1) return e.w >= ERA_BLOCK_MIN;
      }
      return false;
    };

    /* top band: era labels, bridge labels, year ticks; gridlines below */
    view.eras.forEach(function (e) {
      var left = e.x0 - view.pan, right = left + e.w;
      var sameYear = e.a.slice(0, 4) === e.b.slice(0, 4);
      if (e.w < ERA_BLOCK_MIN) {
        var block = el("rect", {
          x: left, y: HEAD_H, width: e.w, height: height - HEAD_H - AXIS_H, rx: 8,
          fill: css("--bubu"), stroke: css("--hair"), "stroke-width": 1
        }, svg);
        block.style.cursor = "zoom-in";
        block.dataset.era = e.a;
        var cx = left + e.w / 2;
        var label = sameYear ? e.a.slice(0, 4)
          : e.a.slice(0, 4) + "\u2013" + e.b.slice(2, 4);
        if (e.w >= 46) label += " \u00b7 " + e.count;
        var t1 = text(svg, cx, 14, label, 8.5, css("--draw"));
        t1.dataset.era = e.a;
        t1.style.cursor = "zoom-in";
      } else {
        var span = (e.t1 - e.t0) / DAY / 365;
        var steps = [1, 2, 5, 10, 20, 50];
        var step = steps[steps.length - 1];
        for (var si = 0; si < steps.length; si++) {
          if ((e.w / span) * steps[si] >= 64) { step = steps[si]; break; }
        }
        var y0 = new Date(e.t0).getFullYear(), y1 = new Date(e.t1).getFullYear();
        for (var yr = Math.ceil(y0 / step) * step; yr <= y1; yr += step) {
          var gx = xOf(view, parseDate(yr + "-01-01"));
          if (gx < left - 1 || gx > right + 1 || gx < 0 || gx > width) continue;
          el("path", {
            d: "M" + gx + " " + HEAD_H + "V" + (height - AXIS_H),
            stroke: css("--hair"), "stroke-width": 1
          }, svg);
          text(svg, gx, 14, yr, 9, css("--muted"));
        }
      }
      if (e.bridgeX !== undefined) {
        var bx = e.bridgeX - view.pan;
        if (bx + BRIDGE_W >= 0 && bx <= width) {
          [0, 1].forEach(function (k) {
            var lx = bx + BRIDGE_W / 2 - 5 + k * 10;
            el("path", {
              d: "M" + lx + " " + HEAD_H + " L" + (lx - 6) + " " + (height - AXIS_H),
              stroke: css("--hair"), "stroke-width": 1.2,
              "stroke-dasharray": "3 3"
            }, svg);
          });
          text(svg, bx + BRIDGE_W / 2, 14, e.bridgeYears + "y quiet", 8,
            css("--unsure"));
        }
      }
    });

    var row = 0;
    el("path", {
      d: "M0 " + (height - AXIS_H + 0.5) + "H" + width,
      stroke: css("--hair"), "stroke-width": 1, opacity: 0
    }, svg);

    function rowSep(rowIdx) {
      if (rowIdx === 0) return;
      el("path", {
        d: "M0 " + (HEAD_H + rowIdx * ROW_H + 0.5) + "H" + width,
        stroke: css("--hair"), "stroke-width": 0.5, opacity: 0.6
      }, svg);
    }

    function yearLabels(entries, rowBottom) {
      var last = -1e9;
      entries.forEach(function (p) {
        if (!openEra(p.date)) return;
        var px = p._x;
        if (px < 0 || px > width || px - last < 30) return;
        last = px;
        text(svg, px, rowBottom + 1, p.date.slice(0, 4), 7.5, css("--muted"));
      });
    }

    lanes.forEach(function (lane) {
      rowSep(row);
      var top = HEAD_H + row * ROW_H + 17, bottom = HEAD_H + (row + 1) * ROW_H - 14;
      text(svg, 8, HEAD_H + row * ROW_H + 12, lane.label, 9, css("--ink"), "start");
      function y(v) { return laneY(v, lane.v_min, lane.v_max, top, bottom); }
      var all = lane.points.concat(lane.same_marks);
      all.forEach(function (p) { p._x = x(p.date); });

      all.forEach(function (p) {
        if (!openEra(p.date) || p.band_days <= 7) return;
        var x0 = xOf(view, parseDate(p.date) - p.band_days * DAY);
        var x1 = xOf(view, parseDate(p.date) + p.band_days * DAY);
        mark(svg, "rect", {
          x: x0, y: y(p.value) - 8, width: Math.max(2, x1 - x0), height: 16,
          rx: 3, fill: css("--bandfill")
        }, p.sentence);
      });
      var eraOf = function (iso) {
        var t = parseDate(iso);
        for (var i = 0; i < view.eras.length; i++) {
          if (t >= view.eras[i].t0 - 1 && t <= view.eras[i].t1 + 1) return i;
        }
        return -1;
      };
      lane.segments.forEach(function (s) {
        if (eraOf(s.a) !== eraOf(s.b)) return;
        if (!openEra(s.a) && !openEra(s.b)) return;
        el("path", {
          d: stepPath([[s.a, s.va], [s.b, s.vb]], x, y), fill: "none",
          stroke: s.gap ? css("--muted") : css("--draw"),
          "stroke-width": 1.6, "stroke-linejoin": "round",
          "stroke-dasharray": s.gap ? "2 4" : "none"
        }, svg);
      });
      lane.points.forEach(function (p) {
        if (!openEra(p.date)) return;
        mark(svg, "circle",
          { cx: p._x, cy: y(p.value), r: 3.2, fill: css("--draw") }, p.sentence);
      });
      lane.same_marks.forEach(function (p) {
        if (!openEra(p.date)) return;
        mark(svg, "path", {
          d: "M" + (p._x - 6) + " " + y(p.value) + "H" + (p._x + 6),
          stroke: css("--draw"), "stroke-width": 2.4, "stroke-linecap": "round"
        }, p.sentence);
      });
      yearLabels(all, bottom + 9);

      /* questions: one glyph per point, attached with a connector */
      var byPoint = {};
      data.questions.forEach(function (q) {
        if (q.lane !== lane.key) return;
        (byPoint[q.event_id] = byPoint[q.event_id] || []).push(q.sentence);
      });
      lane.points.forEach(function (p) {
        var qs = byPoint[p.event_id];
        if (!qs || !openEra(p.date)) return;
        var px = p._x, py = y(p.value);
        el("path", {
          d: "M" + (px + 3) + " " + (py - 3) + "L" + (px + 9) + " " + (py - 10),
          stroke: css("--unsure"), "stroke-width": 1
        }, svg);
        questionGlyph(svg, px + 13, py - 14, qs.join("\n\n"));
      });
      row++;
    });

    bondLanes.forEach(function (lane) {
      rowSep(row);
      var mid = HEAD_H + row * ROW_H + ROW_H / 2 + 2;
      text(svg, 8, HEAD_H + row * ROW_H + 12, lane.label, 9, css("--ink"), "start");
      el("path", {
        d: "M8 " + mid + "H" + (width - 8),
        stroke: css("--hair"), "stroke-width": 1
      }, svg);
      lane.marks.forEach(function (m) { m._x = x(m.date); });
      var lastWord = -1e9;
      lane.marks.forEach(function (m) {
        if (!openEra(m.date)) return;
        if (m.band_days > 7) {
          var x0 = xOf(view, parseDate(m.date) - m.band_days * DAY);
          var x1 = xOf(view, parseDate(m.date) + m.band_days * DAY);
          mark(svg, "rect", {
            x: x0, y: mid - 8, width: Math.max(2, x1 - x0), height: 16,
            rx: 3, fill: css("--bandfill")
          }, m.sentence);
        }
        mark(svg, "path", {
          d: "M" + m._x + " " + (mid - 7) + "V" + (mid + 7),
          stroke: css("--draw"), "stroke-width": 2.4, "stroke-linecap": "round"
        }, m.sentence);
        if (m._x - lastWord >= 44) {
          lastWord = m._x;
          var w = mark(svg, "text",
            { x: m._x, y: mid + 19, "text-anchor": "middle" }, m.sentence);
          w.textContent = m.kind;
          w.style.font = "400 8px " + css("--mono");
          w.style.fill = css("--muted");
        }
      });
      yearLabels(lane.marks, mid + 22);
      row++;
    });
  }

  /* pan / zoom / era-fit interactions */
  function bindExpanded() {
    var svg = document.getElementById("expanded");
    var pointers = {};
    var moved = false;

    svg.addEventListener("pointerdown", function (ev) {
      pointers[ev.pointerId] = { x: ev.clientX, y: ev.clientY };
      moved = false;
      svg.setPointerCapture(ev.pointerId);
    });
    svg.addEventListener("pointermove", function (ev) {
      var p = pointers[ev.pointerId];
      if (!p) return;
      var ids = Object.keys(pointers);
      if (ids.length === 1) {
        var dx = ev.clientX - p.x;
        if (Math.abs(dx) > 3) moved = true;
        state.view.pan -= dx;
        clampPan(state.view, state.view.width);
        p.x = ev.clientX; p.y = ev.clientY;
        renderExpanded();
      } else if (ids.length === 2) {
        moved = true;
        var other = pointers[ids[0] === String(ev.pointerId) ? ids[1] : ids[0]];
        var before = Math.abs(p.x - other.x) || 1;
        p.x = ev.clientX; p.y = ev.clientY;
        var after = Math.abs(p.x - other.x) || 1;
        var rect = svg.getBoundingClientRect();
        zoomAt(state.view, (p.x + other.x) / 2 - rect.left, after / before,
          state.view.width);
        renderExpanded();
      }
    });
    function up(ev) { delete pointers[ev.pointerId]; }
    svg.addEventListener("pointerup", up);
    svg.addEventListener("pointercancel", up);

    svg.addEventListener("wheel", function (ev) {
      ev.preventDefault();
      var rect = svg.getBoundingClientRect();
      var factor = Math.exp(-ev.deltaY * 0.0015);
      zoomAt(state.view, ev.clientX - rect.left, factor, state.view.width);
      renderExpanded();
    }, { passive: false });

    svg.addEventListener("dblclick", function (ev) {
      var rect = svg.getBoundingClientRect();
      var era = eraAt(state.view, ev.clientX - rect.left);
      if (era) { fitEra(state.view, era, state.view.width); renderExpanded(); }
    });
    svg.addEventListener("click", function (ev) {
      if (moved) return;
      var eraKey = ev.target.dataset && ev.target.dataset.era;
      if (eraKey) {
        var era = state.view.eras.find(function (e) { return e.a === eraKey; });
        if (era) { fitEra(state.view, era, state.view.width); renderExpanded(); }
      }
    });
  }

  function renderShelf() {
    var shelf = document.getElementById("shelf");
    var head = document.getElementById("shelf-head");
    shelf.innerHTML = "";
    var items = state.data.shelf;
    head.hidden = !items.length;
    items.forEach(function (item) {
      var chip = document.createElement("button");
      chip.type = "button";
      chip.className = "shelfchip";
      chip.textContent = item.label;
      chip.dataset.sentence = item.sentence;
      chip.dataset.ask = item.label;
      shelf.appendChild(chip);
    });
  }

  function renderFreshness() {
    var notes = {
      extracting: "Updating the picture from your conversation…",
      pending_review: "New details from your conversation are waiting to be added.",
      chat_ahead: "The picture may be a little behind the conversation."
    };
    document.getElementById("freshness").textContent =
      notes[state.data.extraction.state] || "";
  }

  function refresh() {
    return fetch("/companion/timeline", { headers: { Accept: "application/json" } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        state.data = data;
        state.view = buildView();
        renderStrip();
        renderFreshness();
        renderShelf();
        if (!document.getElementById("overlay").hidden) renderExpanded();
      });
  }

  /* ---- tap-a-mark bubble (with optional "ask next time" for shelf) ---- */
  var bubble = document.getElementById("bubble");
  var bubbleText = document.getElementById("bubble-text");
  var bubbleAsk = document.getElementById("bubble-ask");
  document.addEventListener("click", function (ev) {
    var target = ev.target.closest ? ev.target.closest("[data-sentence]") : null;
    if (target && target.dataset.sentence) {
      bubbleText.textContent = target.dataset.sentence;
      bubbleAsk.hidden = !target.dataset.ask;
      bubbleAsk.dataset.ask = target.dataset.ask || "";
      bubble.hidden = false;
      var bx = Math.min(ev.clientX, window.innerWidth - 280);
      var by = Math.min(ev.clientY + 14, window.innerHeight - 110);
      bubble.style.left = Math.max(8, bx) + "px";
      bubble.style.top = by + "px";
      ev.stopPropagation();
    } else if (!bubble.hidden && !ev.target.closest("#bubble")) {
      bubble.hidden = true;
    }
  }, true);

  bubbleAsk.addEventListener("click", function () {
    var input = document.getElementById("chat-input");
    input.value = "I want to come back to this sometime: " +
      bubbleAsk.dataset.ask;
    bubble.hidden = true;
    document.getElementById("overlay").hidden = true;
    input.focus();
  });

  /* ---- strip tap opens expanded view ---- */
  document.getElementById("strip-card").addEventListener("click", function (ev) {
    if (ev.target.closest && ev.target.closest("[data-sentence]")) return;
    document.getElementById("overlay").hidden = false;
    renderExpanded();
  });
  document.getElementById("overlay-close").addEventListener("click", function () {
    document.getElementById("overlay").hidden = true;
  });

  /* ---- chat ---- */
  var chatLog = document.getElementById("chat");
  var form = document.getElementById("chat-form");
  var input = document.getElementById("chat-input");
  var send = document.getElementById("chat-send");

  function addBubble(role, textStr) {
    var empty = chatLog.querySelector(".empty");
    if (empty) empty.remove();
    var div = document.createElement("div");
    div.className = "bub " + role;
    div.textContent = textStr;
    chatLog.appendChild(div);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    var textStr = input.value.trim();
    if (!textStr) return;
    addBubble("user", textStr);
    input.value = "";
    send.disabled = true;
    fetch("/companion/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
      body: JSON.stringify({ statement: textStr })
    })
      .then(function (r) {
        if (!r.ok) throw new Error("chat failed: " + r.status);
        return r.json();
      })
      .then(function (data) {
        addBubble("coach", data.statement);
        return refresh();
      })
      .catch(function (err) {
        addBubble("coach", "Sorry — that message didn't go through. Try again?");
        console.error(err);
      })
      .then(function () { send.disabled = false; input.focus(); });
  });

  window.addEventListener("resize", function () {
    if (state.data) {
      renderStrip();
      if (!document.getElementById("overlay").hidden) renderExpanded();
    }
  });

  bindExpanded();
  refresh();
  chatLog.scrollTop = chatLog.scrollHeight;
})();
