/* ==========================================================================
   LU Teaching Slides, flow diagrams
   lu-flow.js · v1.2.1 · no dependencies, works from file://
   --------------------------------------------------------------------------
   Why it exists: in hand-drawn SVG, blocks and arrows are positioned
   separately, so they drift apart. Here every arrow names its two blocks and
   is computed from their geometry, so an arrow always touches its blocks.

   Markup, inside an .lu-walk so the existing step bar, dots and arrow keys
   drive it (see design-system.html, section 7, "Flow diagram"):

     <div class="lu-walk" data-label="...">
       <div class="lu-walk__view">
         <div class="lu-flow"><script type="application/json" class="lu-flow__spec">{...}</script></div>
         <div data-walk-step="1" data-caption="..."></div>   one empty div per step
       </div>
     </div>

   Spec:
     width, height          canvas in slide px (1448 is a full content width)
     nodes[]  id, label ("\n" breaks a line), kind, x, y (centre), w, h,
              flag ("top" | "bottom" | "right": where its status badge sits)
     edges[]  id, from, to, label, kind ("inferred" | "conflict"), both,
              route ("elbow"), sides ([fromSide, toSide])
     steps[]  show: ids to reveal, run: edge ids whose dots move,
              set: { nodeId: "idle" | "active" | "inferred" | "impossible" }
     legend   false to hide it, or { kind: "label" } to rename entries
     flags    optional { state: "badge text" } to rename a state's badge for
              this diagram, e.g. { "impossible": "no rate" } before an
              ontology exists (Session 1). Colour still comes from the state.
   Steps accumulate. Colours live in lu.css (8d), never in this file.
   Nothing is measured from the DOM, so hidden slides, study mode and the
   printed handout all render; print shows the last step.
   ========================================================================== */
(function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';
  var KIND_LABEL = {
    ours: 'Our ontology', reused: 'Reused ontology', upper: 'BFO, upper ontology',
    individual: 'Individual', literal: 'Value', builtin: 'OWL built-in'
  };
  var STATE_LABEL = { inferred: 'Inferred', impossible: 'Impossible' };
  var FLAG_TEXT = { inferred: 'inferred', impossible: 'impossible' };
  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function mk(tag, attrs, parent) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }

  /* ---------------------------------------------------------------- geometry */
  function sidePoint(n, s) {
    if (s === 'top') return [n.x, n.y - n.h / 2];
    if (s === 'bottom') return [n.x, n.y + n.h / 2];
    if (s === 'left') return [n.x - n.w / 2, n.y];
    return [n.x + n.w / 2, n.y];
  }
  function autoSides(a, b) {
    var dx = b.x - a.x, dy = b.y - a.y;
    if (Math.abs(dx) / (a.w / 2 + b.w / 2) >= Math.abs(dy) / (a.h / 2 + b.h / 2)) return dx > 0 ? ['right', 'left'] : ['left', 'right'];
    return dy > 0 ? ['bottom', 'top'] : ['top', 'bottom'];
  }
  function horiz(s) { return s === 'left' || s === 'right'; }
  function route(e, a, b) {
    var s = e.sides || autoSides(a, b), p = sidePoint(a, s[0]), q = sidePoint(b, s[1]);
    if (e.route !== 'elbow') return [p, q];
    if (horiz(s[0]) && !horiz(s[1])) return [p, [q[0], p[1]], q];
    if (!horiz(s[0]) && horiz(s[1])) return [p, [p[0], q[1]], q];
    if (horiz(s[0])) { var mx = (p[0] + q[0]) / 2; return [p, [mx, p[1]], [mx, q[1]], q]; }
    var my = (p[1] + q[1]) / 2; return [p, [p[0], my], [q[0], my], q];
  }
  function lengths(pts) {
    var seg = [], total = 0;
    for (var i = 1; i < pts.length; i++) {
      var d = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
      seg.push(d); total += d;
    }
    return { seg: seg, total: total };
  }
  function pointAt(pts, L, t) {
    var d = t * L.total;
    for (var i = 0; i < L.seg.length; i++) {
      if (d <= L.seg[i] || i === L.seg.length - 1) {
        var f = L.seg[i] ? d / L.seg[i] : 0;
        return [pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f];
      }
      d -= L.seg[i];
    }
    return pts[pts.length - 1];
  }
  function head(from, to, parent) {
    var ang = Math.atan2(to[1] - from[1], to[0] - from[0]), L = 15, W = 7.5;
    var p2 = [to[0] - L * Math.cos(ang) + W * Math.sin(ang), to[1] - L * Math.sin(ang) - W * Math.cos(ang)];
    var p3 = [to[0] - L * Math.cos(ang) - W * Math.sin(ang), to[1] - L * Math.sin(ang) + W * Math.cos(ang)];
    return mk('polygon', { 'class': 'lu-flow__head', points: to.join(',') + ' ' + p2.join(',') + ' ' + p3.join(',') }, parent);
  }
  function labelSpot(pts) {
    var best = 1, bl = -1;
    for (var i = 1; i < pts.length; i++) {
      var l = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
      if (l > bl) { bl = l; best = i; }
    }
    var a = pts[best - 1], b = pts[best], mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
    if (Math.abs(b[1] - a[1]) < 1) return { x: mx, y: my - 16, anchor: 'middle' };
    return { x: mx + 14, y: my, anchor: 'start' };
  }

  /* ------------------------------------------------------------------ render */
  function build(host) {
    var specEl = host.querySelector('.lu-flow__spec');
    if (!specEl) return;
    var spec = JSON.parse(specEl.textContent);
    var byId = {};
    spec.nodes.forEach(function (n) { byId[n.id] = n; });
    var walk = host.closest('.lu-walk');

    var svg = mk('svg', { 'class': 'lu-svg', viewBox: '0 0 ' + spec.width + ' ' + spec.height, role: 'img',
      'aria-label': (walk && walk.getAttribute('data-label')) || 'Diagram' });
    var gEdges = mk('g', {}, svg), gNodes = mk('g', {}, svg), gDots = mk('g', { 'aria-hidden': 'true' }, svg);
    var parts = {};

    spec.edges.forEach(function (e) {
      var pts = route(e, byId[e.from], byId[e.to]);
      var g = mk('g', { 'class': 'lu-flow__edge', 'data-kind': e.kind || null }, gEdges);
      mk('polyline', { 'class': 'lu-flow__line', points: pts.map(function (p) { return p.join(','); }).join(' ') }, g);
      head(pts[pts.length - 2], pts[pts.length - 1], g);
      if (e.both) head(pts[1], pts[0], g);
      var ls = labelSpot(pts);
      var lab = mk('text', { 'class': 'lu-flow__elabel', x: ls.x, y: ls.y, 'text-anchor': ls.anchor, 'dominant-baseline': 'middle' }, g);
      lab.textContent = e.label || '';
      parts[e.id] = { type: 'edge', e: e, g: g, pts: pts, L: lengths(pts) };
    });

    spec.nodes.forEach(function (n) {
      var kind = n.kind || 'builtin';
      var pill = kind === 'individual';
      var rx = pill ? n.h / 2 : 8;
      var g = mk('g', { 'class': 'lu-flow__node', 'data-kind': kind }, gNodes);
      mk('rect', { 'class': 'lu-flow__ring', x: n.x - n.w / 2 - 7, y: n.y - n.h / 2 - 7, width: n.w + 14, height: n.h + 14, rx: pill ? (n.h + 14) / 2 : rx + 7 }, g);
      mk('rect', { 'class': 'lu-flow__box', x: n.x - n.w / 2, y: n.y - n.h / 2, width: n.w, height: n.h, rx: rx }, g);
      var lines = String(n.label).split('\n');
      var t = mk('text', { 'class': 'lu-flow__label', 'text-anchor': 'middle' }, g);
      lines.forEach(function (ln, i) {
        mk('tspan', { x: n.x, y: n.y + (i - (lines.length - 1) / 2) * 27, 'dominant-baseline': 'middle' }, t).textContent = ln;
      });
      // Status badge. Its place is per node, so it never sits on an arrow.
      var fp = n.flag || 'top', fy = fp === 'bottom' ? n.y + n.h / 2 : fp === 'right' ? n.y : n.y - n.h / 2;
      var flag = mk('g', { 'class': 'lu-flow__flag' }, g);
      var fbox = mk('rect', { 'class': 'lu-flow__flag-box', y: fy - 14, height: 28, rx: 14 }, flag);
      var ftxt = mk('text', fp === 'right'
        ? { 'class': 'lu-flow__flag-text', x: n.x + n.w / 2 + 22, y: fy, 'text-anchor': 'start', 'dominant-baseline': 'middle' }
        : { 'class': 'lu-flow__flag-text', x: n.x + n.w / 2 - 22, y: fy, 'text-anchor': 'end', 'dominant-baseline': 'middle' }, flag);
      parts[n.id] = { type: 'node', n: n, g: g, fbox: fbox, ftxt: ftxt };
    });

    host.appendChild(svg);
    if (spec.legend !== false) host.appendChild(legend(spec));
    host._flow = { spec: spec, parts: parts, dots: gDots, running: [], t0: 0 };
  }

  function legend(spec) {
    var names = typeof spec.legend === 'object' ? spec.legend : {};
    var box = document.createElement('div');
    box.className = 'lu-flow__legend';
    var kinds = [], states = [];
    spec.nodes.forEach(function (n) { var k = n.kind || 'builtin'; if (kinds.indexOf(k) < 0) kinds.push(k); });
    spec.steps.forEach(function (s) {
      Object.keys(s.set || {}).forEach(function (id) { var v = s.set[id]; if (STATE_LABEL[v] && states.indexOf(v) < 0) states.push(v); });
    });
    var add = function (attr, key, text) {
      var k = document.createElement('span');
      k.className = 'lu-flow__key';
      k.setAttribute(attr, key);
      k.innerHTML = '<span class="lu-flow__swatch" aria-hidden="true"></span>';
      k.appendChild(document.createTextNode(text));
      box.appendChild(k);
    };
    kinds.forEach(function (k) { add('data-kind', k, names[k] || KIND_LABEL[k] || k); });
    states.forEach(function (s) { add('data-state', s, names[s] || STATE_LABEL[s]); });
    return box;
  }

  /* ------------------------------------------------------------------ states */
  function apply(host, idx) {
    var F = host._flow, spec = F.spec, shown = {}, state = {}, run = [];
    spec.nodes.forEach(function (n) { state[n.id] = 'idle'; });
    for (var i = 0; i <= idx && i < spec.steps.length; i++) {
      var s = spec.steps[i];
      (s.show || []).forEach(function (id) { shown[id] = true; });
      for (var k in (s.set || {})) state[k] = s.set[k];
      if (i === idx) run = s.run || [];
    }
    Object.keys(F.parts).forEach(function (id) {
      var p = F.parts[id];
      p.g.setAttribute('data-shown', shown[id] ? 'true' : 'false');
      if (p.type === 'edge') { p.g.setAttribute('data-run', run.indexOf(id) >= 0 ? 'true' : 'false'); return; }
      var st = state[id];
      p.g.setAttribute('data-state', st);
      var text = (spec.flags && spec.flags[st]) || FLAG_TEXT[st] || '';
      p.ftxt.textContent = text;
      var w = text.length * 12.4 + 26, n = p.n;
      p.fbox.setAttribute('width', w);
      p.fbox.setAttribute('x', n.flag === 'right' ? n.x + n.w / 2 + 10 : n.x + n.w / 2 - 10 - w);
    });
    while (F.dots.firstChild) F.dots.removeChild(F.dots.firstChild);
    F.running = reduced ? [] : run.map(function (id) {
      var p = F.parts[id];
      var dots = [0, 1, 2].map(function () {
        return mk('circle', { 'class': 'lu-flow__dot', 'data-kind': p.e.kind || null, r: 7, cx: p.pts[0][0], cy: p.pts[0][1], opacity: 0 }, F.dots);
      });
      return { p: p, dots: dots };
    });
    F.t0 = performance.now();
  }

  /* ---------------------------------------------------------------- animation */
  var hosts = [];
  function tick(now) {
    hosts.forEach(function (h) {
      var F = h._flow;
      if (!F.running.length || !h.offsetParent) return;      // off screen: no work
      var t = ((now - F.t0) % 1700) / 1700;
      F.running.forEach(function (r) {
        r.dots.forEach(function (d, i) {
          var u = (t + i / 3) % 1, pt = pointAt(r.p.pts, r.p.L, u);
          d.setAttribute('cx', pt[0]); d.setAttribute('cy', pt[1]);
          d.setAttribute('opacity', String(Math.min(1, Math.min(u, 1 - u) * 8)));
        });
      });
    });
    requestAnimationFrame(tick);
  }

  /* --------------------------------------------------------- walkthrough hook */
  function currentStep(walk) {
    var at = 0;
    walk.querySelectorAll('[data-walk-step]').forEach(function (s, i) { if (!s.hidden) at = i; });
    return at;                                                 // several visible (print, study): the last
  }
  function init() {
    var printing = window.matchMedia ? window.matchMedia('print') : null;
    document.querySelectorAll('.lu-flow').forEach(function (host) {
      build(host);
      if (!host._flow) return;
      hosts.push(host);
      var walk = host.closest('.lu-walk');
      var last = host._flow.spec.steps.length - 1;
      var sync = function () { apply(host, !walk || (printing && printing.matches) ? last : currentStep(walk)); };
      sync();
      if (walk) new MutationObserver(sync).observe(walk, { attributes: true, subtree: true, attributeFilter: ['hidden'] });
      if (printing && printing.addEventListener) printing.addEventListener('change', sync);
      window.addEventListener('beforeprint', function () { apply(host, last); });
      window.addEventListener('afterprint', sync);
    });
    if (hosts.length && !reduced) requestAnimationFrame(tick);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
