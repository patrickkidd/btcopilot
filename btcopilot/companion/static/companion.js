/* Companion page: chat + timeline picture. Renders SVG from /companion/timeline
   JSON. Strip vocabulary (DRAWABILITY "cartoon rule"): line, dots, amber "?" only.
   Bands, gap-dashes, same-marks, shelf live in the expanded view. */
(function () {
  "use strict";

  var SVGNS = "http://www.w3.org/2000/svg";
  var csrfToken = document.querySelector('meta[name="csrf-token"]').content;
  var state = { data: null, visible: null };

  function css(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function el(name, attrs, parent) {
    var node = document.createElementNS(SVGNS, name);
    for (var k in attrs) node.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(node);
    return node;
  }

  function parseDate(iso) {
    var p = iso.split("-");
    return new Date(+p[0], +p[1] - 1, +p[2]).getTime();
  }

  function makeX(axis, width, padL, padR) {
    var t0 = parseDate(axis.min), t1 = parseDate(axis.max);
    if (t1 <= t0) t1 = t0 + 1;
    return function (iso) {
      return padL + ((parseDate(iso) - t0) / (t1 - t0)) * (width - padL - padR);
    };
  }

  function makeXDays(x, axis) {
    var DAY = 86400000;
    var t0 = parseDate(axis.min);
    return function (iso, days) {
      var shifted = new Date(parseDate(iso) + days * DAY);
      var isoShifted = shifted.getFullYear() + "-" +
        String(shifted.getMonth() + 1).padStart(2, "0") + "-" +
        String(shifted.getDate()).padStart(2, "0");
      return x(isoShifted);
    };
  }

  function yearTicks(axis, x, svg, y, cls) {
    var y0 = +axis.min.slice(0, 4), y1 = +axis.max.slice(0, 4);
    var span = Math.max(1, y1 - y0);
    var step = Math.max(1, Math.ceil(span / 5));
    for (var yr = y0; yr <= y1; yr += step) {
      var iso = yr + "-01-01";
      var t = el("text", { x: x(iso), y: y, "text-anchor": "middle", class: cls }, svg);
      t.textContent = yr;
      t.style.font = "500 9px " + css("--mono");
      t.style.fill = css("--muted");
    }
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

  function laneY(v, vMin, vMax, top, bottom) {
    if (vMax === vMin) return (top + bottom) / 2;
    return bottom - ((v - vMin) / (vMax - vMin)) * (bottom - top);
  }

  function mark(parent, tag, attrs, sentence) {
    var node = el(tag, attrs, parent);
    if (sentence) {
      node.dataset.sentence = sentence;
      node.style.cursor = "pointer";
    }
    return node;
  }

  function questionGlyph(parent, px, py, sentence) {
    var g = el("g", {}, parent);
    mark(g, "circle", {
      cx: px, cy: py, r: 6.5, fill: "none",
      stroke: css("--unsure"), "stroke-width": 1.3
    }, sentence);
    var t = mark(g, "text", { x: px, y: py + 3, "text-anchor": "middle" }, sentence);
    t.textContent = "?";
    t.style.font = "500 9px " + css("--mono");
    t.style.fill = css("--unsure");
  }

  /* ---- strip: line, dots, "?" only ---- */
  function renderStrip() {
    var svg = document.getElementById("strip");
    var data = state.data;
    svg.innerHTML = "";
    var width = svg.parentNode.clientWidth - 16 || 320;
    var lanes = data.strip.lanes;
    var rowH = 34, axisH = 14;
    var height = Math.max(1, lanes.length) * rowH + axisH;
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    svg.setAttribute("height", height);
    if (!data.axis || !lanes.length) {
      var t = el("text", { x: width / 2, y: height / 2 + 4, "text-anchor": "middle" }, svg);
      t.textContent = "The picture appears here as you talk";
      t.style.font = "400 11px " + css("--mono");
      t.style.fill = css("--muted");
      return;
    }
    var x = makeX(data.axis, width, 8, 8);
    lanes.forEach(function (lane, i) {
      var top = i * rowH + 12, bottom = (i + 1) * rowH - 6;
      var label = el("text", { x: 8, y: i * rowH + 9 }, svg);
      label.textContent = lane.label;
      label.style.font = "500 8.5px " + css("--mono");
      label.style.fill = css("--muted");
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
      lane.questions.forEach(function (q) {
        questionGlyph(svg, x(q.date), (top + bottom) / 2, null);
      });
    });
    yearTicks(data.axis, x, svg, height - 3, "ax");
  }

  /* ---- expanded: labels, bands, gaps, same-marks, bond stamps, shelf ---- */
  function renderExpanded() {
    var svg = document.getElementById("expanded");
    var data = state.data;
    svg.innerHTML = "";
    var width = svg.parentNode.clientWidth - 20 || 320;
    var lanes = data.lanes.filter(function (l) { return state.visible.has("p" + l.person); });
    var bondLanes = data.bond_lanes.filter(function (l) { return state.visible.has("b" + l.pair_bond); });
    var rowH = 54, axisH = 18;
    var rows = lanes.length + bondLanes.length;
    var height = Math.max(1, rows) * rowH + axisH;
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    svg.setAttribute("height", height);
    if (!data.axis || !rows) {
      var t = el("text", { x: width / 2, y: 30, "text-anchor": "middle" }, svg);
      t.textContent = "Nothing to draw yet";
      t.style.font = "400 11px " + css("--mono");
      t.style.fill = css("--muted");
      return;
    }
    var x = makeX(data.axis, width, 8, 8);
    var xd = makeXDays(x, data.axis);
    var row = 0;

    lanes.forEach(function (lane) {
      var top = row * rowH + 18, bottom = (row + 1) * rowH - 10;
      var label = el("text", { x: 8, y: row * rowH + 12 }, svg);
      label.textContent = lane.label;
      label.style.font = "500 9px " + css("--mono");
      label.style.fill = css("--ink");
      function y(v) { return laneY(v, lane.v_min, lane.v_max, top, bottom); }

      lane.points.concat(lane.same_marks).forEach(function (p) {
        if (p.band_days > 7) {
          mark(svg, "rect", {
            x: xd(p.date, -p.band_days), y: y(p.value) - 8,
            width: Math.max(2, xd(p.date, p.band_days) - xd(p.date, -p.band_days)),
            height: 16, rx: 3, fill: css("--bandfill")
          }, p.sentence);
        }
      });
      lane.segments.forEach(function (s) {
        var attrs = {
          d: stepPath([[s.a, s.va], [s.b, s.vb]], x, y), fill: "none",
          stroke: css("--draw"), "stroke-width": 1.6, "stroke-linejoin": "round"
        };
        if (s.gap) {
          attrs.stroke = css("--muted");
          attrs["stroke-dasharray"] = "2 4";
        }
        el("path", attrs, svg);
      });
      lane.points.forEach(function (p) {
        mark(svg, "circle", { cx: x(p.date), cy: y(p.value), r: 3.2, fill: css("--draw") }, p.sentence);
      });
      lane.same_marks.forEach(function (p) {
        mark(svg, "path", {
          d: "M" + (x(p.date) - 6) + " " + y(p.value) + "H" + (x(p.date) + 6),
          stroke: css("--draw"), "stroke-width": 2.4, "stroke-linecap": "round"
        }, p.sentence);
      });
      data.questions.forEach(function (q) {
        if (q.lane === lane.key) questionGlyph(svg, x(q.date), top - 4, q.sentence);
      });
      row++;
    });

    bondLanes.forEach(function (lane) {
      var top = row * rowH + 18, mid = row * rowH + rowH / 2 + 4;
      var label = el("text", { x: 8, y: row * rowH + 12 }, svg);
      label.textContent = lane.label;
      label.style.font = "500 9px " + css("--mono");
      label.style.fill = css("--ink");
      el("path", {
        d: "M8 " + mid + "H" + (width - 8),
        stroke: css("--hair"), "stroke-width": 1
      }, svg);
      lane.marks.forEach(function (m) {
        if (m.band_days > 7) {
          mark(svg, "rect", {
            x: xd(m.date, -m.band_days), y: mid - 8,
            width: Math.max(2, xd(m.date, m.band_days) - xd(m.date, -m.band_days)),
            height: 16, rx: 3, fill: css("--bandfill")
          }, m.sentence);
        }
        mark(svg, "path", {
          d: "M" + x(m.date) + " " + (mid - 7) + "V" + (mid + 7),
          stroke: css("--draw"), "stroke-width": 2.4, "stroke-linecap": "round"
        }, m.sentence);
        var t = mark(svg, "text", { x: x(m.date), y: mid + 20, "text-anchor": "middle" }, m.sentence);
        t.textContent = m.kind;
        t.style.font = "400 8px " + css("--mono");
        t.style.fill = css("--muted");
      });
      row++;
    });

    yearTicks(data.axis, x, svg, height - 4, "ax");
    renderShelf();
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
      shelf.appendChild(chip);
    });
  }

  function renderPicker() {
    var pick = document.getElementById("lane-pick");
    pick.innerHTML = "";
    var entries = state.data.people.map(function (p) {
      return { key: "p" + p.id, label: p.name };
    }).concat(state.data.pair_bonds.map(function (b) {
      return { key: "b" + b.id, label: b.label };
    }));
    entries.forEach(function (e) {
      var chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chp";
      chip.textContent = e.label;
      chip.setAttribute("aria-pressed", state.visible.has(e.key));
      chip.addEventListener("click", function () {
        if (state.visible.has(e.key)) state.visible.delete(e.key);
        else state.visible.add(e.key);
        chip.setAttribute("aria-pressed", state.visible.has(e.key));
        renderExpanded();
      });
      pick.appendChild(chip);
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
        if (!state.visible) {
          state.visible = new Set();
          data.people.forEach(function (p) { state.visible.add("p" + p.id); });
          data.pair_bonds.forEach(function (b) { state.visible.add("b" + b.id); });
        }
        renderStrip();
        renderFreshness();
        renderPicker();
        if (!document.getElementById("overlay").hidden) renderExpanded();
      });
  }

  /* ---- tap-a-mark bubble ---- */
  var bubble = document.getElementById("bubble");
  document.addEventListener("click", function (ev) {
    var target = ev.target.closest ? ev.target.closest("[data-sentence]") : null;
    if (target && target.dataset.sentence) {
      bubble.textContent = target.dataset.sentence;
      bubble.hidden = false;
      var bx = Math.min(ev.clientX, window.innerWidth - 280);
      var by = Math.min(ev.clientY + 14, window.innerHeight - 90);
      bubble.style.left = Math.max(8, bx) + "px";
      bubble.style.top = by + "px";
      ev.stopPropagation();
    } else if (!bubble.hidden) {
      bubble.hidden = true;
    }
  }, true);

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

  function addBubble(role, text) {
    var div = document.createElement("div");
    div.className = "bub " + role;
    div.textContent = text;
    chatLog.appendChild(div);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    var text = input.value.trim();
    if (!text) return;
    addBubble("user", text);
    input.value = "";
    send.disabled = true;
    fetch("/companion/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
      body: JSON.stringify({ statement: text })
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

  refresh();
  chatLog.scrollTop = chatLog.scrollHeight;
})();
