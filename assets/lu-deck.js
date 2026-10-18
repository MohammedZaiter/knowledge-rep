/* ==========================================================================
   LU Teaching Slides, Deck Runtime
   lu-deck.js · v1.0 · no dependencies, no build step, works from file://
   --------------------------------------------------------------------------
   Reads from <body>:
     data-deck-id      required. Namespace for saved progress + answers.
     data-course       course name shown in the slide header
     data-session      session label shown in the slide header
     data-duration     planned contact minutes, for the pacing indicator
     data-app-root     path from THIS page to the repo root ("./" or "../")
     data-unit         footer unit line (default "Lebanese University")
   Reads from each <section class="slide">:
     data-label        short title, used by the TOC, search and presenter view
     data-section      TOC group name
     data-minutes      planned minutes on this slide, for pacing
     data-notes        speaker notes (plain text; or use <template data-notes>)
     data-chrome="none"  suppress the injected header/footer frame
   ========================================================================== */
(function () {
  'use strict';

  /* ---------------------------------------------------------------- utils */
  var d = document;
  var qs = function (s, r) { return (r || d).querySelector(s); };
  var qsa = function (s, r) { return Array.prototype.slice.call((r || d).querySelectorAll(s)); };
  var el = function (tag, cls, txt) {
    var n = d.createElement(tag);
    if (cls) n.className = cls;
    if (txt != null) n.textContent = txt;
    return n;
  };
  var clamp = function (n, lo, hi) { return Math.max(lo, Math.min(hi, n)); };
  var pad = function (n) { return (n < 10 ? '0' : '') + n; };
  var mmss = function (s) {
    s = Math.max(0, Math.round(s));
    return pad(Math.floor(s / 60)) + ':' + pad(s % 60);
  };
  var norm = function (s) {
    return String(s == null ? '' : s).toLowerCase().replace(/[\u2018\u2019']/g, "'")
      .replace(/[^a-z0-9'+#.\- ]/g, ' ').replace(/\s+/g, ' ').trim();
  };

  var body = d.body;
  var DECK_ID = body.getAttribute('data-deck-id') || 'deck';
  var APP_ROOT = body.getAttribute('data-app-root') || './';
  var IS_PRESENTER = /[?&]presenter=1/.test(location.search);

  /* ------------------------------------------------------- scoped storage */
  var Store = {
    key: function (k) { return 'lu:' + DECK_ID + ':' + k; },
    get: function (k, fb) {
      try {
        var v = localStorage.getItem(Store.key(k));
        return v == null ? fb : JSON.parse(v);
      } catch (e) { return fb; }
    },
    set: function (k, v) {
      try { localStorage.setItem(Store.key(k), JSON.stringify(v)); } catch (e) {}
    }
  };
  var answers = Store.get('answers', {}) || {};
  var saveAnswer = function (qid, val) {
    if (!qid) return;
    answers[qid] = val;
    Store.set('answers', answers);
    Deck.refreshScores();
  };

  /* ------------------------------------------------------------- registry */
  /* Every graded component registers here so the end-of-deck self-check can
     report a score without knowing what kind of question it was. */
  var graded = [];
  var register = function (rec) { graded.push(rec); };

  /* ================================================================ TOAST */
  var toastNode = null, toastT = 0;
  function toast(msg) {
    if (!toastNode) { toastNode = el('div', 'lu-toast'); toastNode.setAttribute('role', 'status'); body.appendChild(toastNode); }
    toastNode.textContent = msg;
    toastNode.classList.add('is-shown');
    clearTimeout(toastT);
    toastT = setTimeout(function () { toastNode.classList.remove('is-shown'); }, 1800);
  }

  /* ================================================================= DECK */
  var Deck = {
    stage: null,
    slides: [],
    i: 0,
    step: 0,
    steps: [],
    chan: null,
    started: 0,
    running: false,
    elapsed: 0,

    init: function () {
      Deck.stage = qs('.deck__stage');
      if (!Deck.stage) return;
      Deck.slides = qsa('.slide', Deck.stage);
      if (!Deck.slides.length) return;

      Deck.frameSlides();
      Deck.buildChrome();
      Deck.bindKeys();
      Deck.bindChannel();
      Deck.fit();
      window.addEventListener('resize', Deck.fit);
      window.addEventListener('hashchange', Deck.fromHash);

      // Restore mode preferences before first paint of interactive bits.
      if (Store.get('selfstudy', false)) Deck.setSelfStudy(true, true);

      var start = Deck.hashTarget();
      if (!start && Store.get('pos', null) != null) {
        start = { i: clamp(Store.get('pos', 0), 0, Deck.slides.length - 1), step: 0 };
      }
      Deck.go(start ? start.i : 0, start ? start.step : 0, true);

      d.documentElement.classList.add('lu-ready');
      Deck.timerTick();
      setInterval(Deck.timerTick, 1000);
    },

    /* Wrap author content in the standard slide frame. */
    frameSlides: function () {
      var course = body.getAttribute('data-course') || '';
      var session = body.getAttribute('data-session') || '';
      var unit = body.getAttribute('data-unit') || 'Lebanese University';
      Deck.slides.forEach(function (s, n) {
        s.setAttribute('role', 'group');
        s.setAttribute('aria-roledescription', 'slide');
        s.setAttribute('aria-label', (n + 1) + ' of ' + Deck.slides.length + '. ' + (s.getAttribute('data-label') || ''));
        s.setAttribute('data-screen-label', pad(n + 1));
        s.id = s.id || 'slide-' + (n + 1);

        if (s.getAttribute('data-chrome') === 'none') return;

        var bodyWrap = qs(':scope > .slide__body', s);
        if (!bodyWrap) {
          bodyWrap = el('div', 'slide__body');
          while (s.firstChild) bodyWrap.appendChild(s.firstChild);
          s.appendChild(bodyWrap);
        }

        var head = el('div', 'slide__head');
        head.appendChild(el('div', 'slide__head-course', course));
        var meta = el('div', 'slide__head-meta');
        meta.textContent = [s.getAttribute('data-section'), session].filter(Boolean).join('  ·  ');
        head.appendChild(meta);
        s.insertBefore(head, bodyWrap);

        var foot = el('div', 'slide__foot');
        foot.appendChild(el('div', null, unit));
        foot.appendChild(el('div', null, pad(n + 1) + ' / ' + pad(Deck.slides.length)));
        s.appendChild(foot);

        var notes = Deck.notesFor(s);
        if (notes) {
          var pn = el('div', 'lu-print-notes');
          pn.innerHTML = '<b>Notes.</b> ' + notes;
          s.appendChild(pn);
        }
      });
    },

    notesFor: function (s) {
      var t = qs('template[data-notes]', s);
      if (t) return t.innerHTML.trim();
      var a = s.getAttribute('data-notes');
      return a ? a.replace(/&/g, '&amp;').replace(/</g, '&lt;') : '';
    },

    /* --------------------------------------------------------- navigation */
    buildSteps: function (s) {
      var nodes = qsa('[data-build]', s);
      var groups = {};
      nodes.forEach(function (n, idx) {
        var v = parseInt(n.getAttribute('data-build'), 10);
        if (isNaN(v)) v = idx + 1;
        (groups[v] = groups[v] || []).push(n);
      });
      return Object.keys(groups).map(Number).sort(function (a, b) { return a - b; })
        .map(function (k) { return groups[k]; });
    },

    go: function (i, step, silent) {
      i = clamp(i, 0, Deck.slides.length - 1);
      var s = Deck.slides[i];
      Deck.slides.forEach(function (x) { x.classList.remove('is-active'); });
      s.classList.add('is-active');
      Deck.i = i;
      Deck.steps = Deck.buildSteps(s);
      Deck.setStep(step == null ? 0 : step, true);
      Store.set('pos', i);
      Deck.paintChrome();
      if (!silent) Deck.hudFlash();
      Deck.broadcast();
      Deck.syncHash();
      if (!IS_PRESENTER) {
        var live = qs('#lu-live');
        if (live) live.textContent = 'Slide ' + (i + 1) + ' of ' + Deck.slides.length + '. ' + (s.getAttribute('data-label') || '');
      }
    },

    setStep: function (n, silent) {
      var total = Deck.steps.length;
      Deck.step = clamp(n, 0, total);
      var full = body.classList.contains('lu-selfstudy');
      Deck.steps.forEach(function (group, gi) {
        group.forEach(function (node) {
          node.classList.toggle('is-built', full || gi < Deck.step);
        });
      });
      if (!silent) { Deck.syncHash(); Deck.broadcast(); }
    },

    next: function () {
      if (Deck.step < Deck.steps.length) { Deck.setStep(Deck.step + 1); return; }
      if (Deck.i < Deck.slides.length - 1) Deck.go(Deck.i + 1, 0);
      if (!Deck.running) Deck.timerStart();
    },
    prev: function () {
      if (Deck.step > 0) { Deck.setStep(Deck.step - 1); return; }
      if (Deck.i > 0) {
        var target = Deck.i - 1;
        Deck.go(target, 0);
        Deck.setStep(Deck.buildSteps(Deck.slides[target]).length);
      }
    },

    hashTarget: function () {
      var m = /^#\/(\d+)(?:\/(\d+))?/.exec(location.hash || '');
      if (!m) return null;
      return { i: clamp(parseInt(m[1], 10) - 1, 0, Deck.slides.length - 1), step: parseInt(m[2] || '0', 10) };
    },
    fromHash: function () {
      var t = Deck.hashTarget();
      if (!t) return;
      if (t.i !== Deck.i || t.step !== Deck.step) Deck.go(t.i, t.step, true);
    },
    syncHash: function () {
      var h = '#/' + (Deck.i + 1) + (Deck.step > 0 ? '/' + Deck.step : '');
      if (location.hash !== h) history.replaceState(null, '', location.pathname + location.search + h);
    },

    /* ---------------------------------------------------------- scale fit */
    fit: function () {
      if (IS_PRESENTER || !Deck.stage) return;
      var k = Math.min(window.innerWidth / 1600, window.innerHeight / 900);
      Deck.stage.style.transform = 'translate(-50%, -50%) scale(' + k + ')';
    },

    /* ------------------------------------------------------------- chrome */
    buildChrome: function () {
      var live = el('div', 'lu-sr');
      live.id = 'lu-live';
      live.setAttribute('aria-live', 'polite');
      body.appendChild(live);

      var prog = el('div', 'lu-progress');
      prog.setAttribute('aria-hidden', 'true');
      prog.appendChild(el('span'));
      body.appendChild(prog);
      Deck.prog = prog.firstChild;

      var hud = el('div', 'lu-hud');
      hud.innerHTML =
        '<div class="lu-hud__btns">' +
        '<button class="lu-hud__btn" data-act="prev" aria-label="Previous slide">&#8592;</button>' +
        '<button class="lu-hud__btn" data-act="next" aria-label="Next slide">&#8594;</button>' +
        '<button class="lu-hud__btn" data-act="toc">Contents</button>' +
        '<button class="lu-hud__btn" data-act="search">Search</button>' +
        '<button class="lu-hud__btn" data-act="selfstudy" aria-pressed="false">Study mode</button>' +
        '<button class="lu-hud__btn" data-act="presenter">Presenter</button>' +
        '<button class="lu-hud__btn" data-act="print">Handout</button>' +
        '<button class="lu-hud__btn" data-act="help" aria-label="Keyboard shortcuts">?</button>' +
        '</div>' +
        '<span class="lu-hud__pace" data-pace="on">00:00</span>' +
        '<span class="lu-hud__count"></span>';
      body.appendChild(hud);
      Deck.hud = hud;
      Deck.count = qs('.lu-hud__count', hud);
      Deck.pace = qs('.lu-hud__pace', hud);

      hud.addEventListener('click', function (e) {
        var b = e.target.closest('[data-act]');
        if (!b) return;
        var a = b.getAttribute('data-act');
        if (a === 'prev') Deck.prev();
        else if (a === 'next') Deck.next();
        else if (a === 'toc') Overlay.open('toc');
        else if (a === 'search') Overlay.open('search');
        else if (a === 'help') Overlay.open('help');
        else if (a === 'selfstudy') Deck.setSelfStudy(!body.classList.contains('lu-selfstudy'));
        else if (a === 'presenter') Deck.openPresenter();
        else if (a === 'print') Deck.printHandout();
      });

      var show = function () { hud.classList.add('is-shown'); clearTimeout(Deck.hudT); Deck.hudT = setTimeout(function () { hud.classList.remove('is-shown'); }, 2600); };
      Deck.hudFlash = show;
      window.addEventListener('mousemove', show);
      window.addEventListener('keydown', show);
      show();

      Overlay.build();
    },

    paintChrome: function () {
      if (Deck.count) Deck.count.textContent = (Deck.i + 1) + ' / ' + Deck.slides.length;
      if (Deck.prog) Deck.prog.style.width = ((Deck.i + 1) / Deck.slides.length * 100) + '%';
      Overlay.markToc();
    },

    /* -------------------------------------------------------- timer/pace */
    timerStart: function () {
      if (Deck.running) return;
      Deck.running = true;
      Deck.started = Date.now() - Deck.elapsed * 1000;
    },
    timerToggle: function () {
      if (Deck.running) { Deck.running = false; toast('Timer paused'); }
      else { Deck.timerStart(); toast('Timer running'); }
    },
    timerTick: function () {
      if (Deck.running) Deck.elapsed = (Date.now() - Deck.started) / 1000;
      var planned = 0;
      for (var k = 0; k <= Deck.i; k++) planned += parseFloat(Deck.slides[k].getAttribute('data-minutes') || 0);
      var drift = Deck.elapsed / 60 - planned;
      var live = Deck.running || Deck.elapsed > 0;
      var state = (!planned || !live) ? 'on' : drift > 2 ? 'behind' : drift < -2 ? 'ahead' : 'on';
      var label = mmss(Deck.elapsed) + (planned && live ? '  ' + (drift >= 0 ? '+' : '\u2212') + Math.abs(Math.round(drift)) + 'm' : '');
      if (Deck.pace) { Deck.pace.textContent = label; Deck.pace.setAttribute('data-pace', state); }
      Deck.broadcast(true);
    },

    /* ---------------------------------------------------------- modes */
    setSelfStudy: function (on, quiet) {
      body.classList.toggle('lu-selfstudy', !!on);
      Store.set('selfstudy', !!on);
      var btn = qs('.lu-hud__btn[data-act="selfstudy"]');
      if (btn) btn.setAttribute('aria-pressed', on ? 'true' : 'false');
      qsa('.lu-reveal__btn').forEach(function (b) { if (on) Reveal.set(b, true); });
      qsa('.lu-term').forEach(function (t) { Term.inline(t, !!on); });
      Deck.setStep(on ? Deck.steps.length : Deck.step, true);
      if (!quiet) toast(on ? 'Study mode on, everything expanded' : 'Study mode off');
    },

    printHandout: function () {
      body.classList.add('lu-handout');
      Deck.setSelfStudy(true, true);
      setTimeout(function () { window.print(); }, 120);
      setTimeout(function () { body.classList.remove('lu-handout'); }, 900);
    },

    /* ------------------------------------------------------- presenter */
    openPresenter: function () {
      var url = location.pathname + '?presenter=1#/' + (Deck.i + 1);
      window.open(url, 'lu-presenter-' + DECK_ID, 'width=1280,height=800');
      Deck.timerStart();
    },
    bindChannel: function () {
      if (!('BroadcastChannel' in window)) return;
      Deck.chan = new BroadcastChannel('lu-deck-' + DECK_ID);
      Deck.chan.onmessage = function (e) {
        var m = e.data || {};
        if (m.t === 'cmd') {
          if (m.a === 'next') Deck.next();
          else if (m.a === 'prev') Deck.prev();
          else if (m.a === 'go') Deck.go(m.i, m.step);
          else if (m.a === 'timer') Deck.timerToggle();
        } else if (m.t === 'state' && IS_PRESENTER) {
          PV.paint(m);
        }
      };
    },
    broadcast: function (light) {
      if (!Deck.chan || IS_PRESENTER) return;
      Deck.chan.postMessage({
        t: 'state', i: Deck.i, step: Deck.step, steps: Deck.steps.length,
        elapsed: Deck.elapsed, running: Deck.running, light: !!light
      });
    },
    cmd: function (a, extra) {
      var m = Object.assign({ t: 'cmd', a: a }, extra || {});
      if (Deck.chan) Deck.chan.postMessage(m);
    },

    /* ------------------------------------------------------------ keys */
    bindKeys: function () {
      d.addEventListener('keydown', function (e) {
        var t = e.target;
        var typing = t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable);
        if (e.key === 'Escape') { Overlay.close(); Term.closeAll(); return; }
        if (typing) return;
        if (e.metaKey || e.ctrlKey || e.altKey) return;

        // A focused walkthrough owns the arrow keys.
        var walk = t && t.closest && t.closest('.lu-walk');
        if (walk && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) {
          Walk.nudge(walk, e.key === 'ArrowRight' ? 1 : -1);
          e.preventDefault(); return;
        }

        switch (e.key) {
          case 'ArrowRight': case 'PageDown': case ' ': case 'Spacebar':
            IS_PRESENTER ? Deck.cmd('next') : Deck.next(); e.preventDefault(); break;
          case 'ArrowLeft': case 'PageUp':
            IS_PRESENTER ? Deck.cmd('prev') : Deck.prev(); e.preventDefault(); break;
          case 'ArrowDown': IS_PRESENTER ? Deck.cmd('go', { i: Deck.i + 1, step: 0 }) : Deck.go(Deck.i + 1, 0); e.preventDefault(); break;
          case 'ArrowUp': IS_PRESENTER ? Deck.cmd('go', { i: Deck.i - 1, step: 0 }) : Deck.go(Deck.i - 1, 0); e.preventDefault(); break;
          case 'Home': Deck.go(0, 0); e.preventDefault(); break;
          case 'End': Deck.go(Deck.slides.length - 1, 0); e.preventDefault(); break;
          case 'o': case 'O': Overlay.open('toc'); e.preventDefault(); break;
          case '/': Overlay.open('search'); e.preventDefault(); break;
          case '?': Overlay.open('help'); e.preventDefault(); break;
          case 't': case 'T': Deck.timerToggle(); break;
          case 's': case 'S': Deck.setSelfStudy(!body.classList.contains('lu-selfstudy')); break;
          case 'p': case 'P': if (!IS_PRESENTER) Deck.openPresenter(); break;
          case 'f': case 'F':
            if (d.fullscreenElement) d.exitFullscreen();
            else if (d.documentElement.requestFullscreen) d.documentElement.requestFullscreen();
            break;
          default:
            if (/^[0-9]$/.test(e.key)) { Deck.jumpBuf = (Deck.jumpBuf || '') + e.key; clearTimeout(Deck.jumpT); Deck.jumpT = setTimeout(function () { Deck.go(parseInt(Deck.jumpBuf, 10) - 1, 0); Deck.jumpBuf = ''; }, 650); }
        }
      });
    },

    refreshScores: function () { qsa('[data-score]').forEach(Score.paint); }
  };

  /* ============================================================ OVERLAYS */
  var Overlay = {
    node: null, which: null, lastFocus: null,
    build: function () {
      var o = el('div', 'lu-overlay');
      o.hidden = true;
      o.setAttribute('role', 'dialog');
      o.setAttribute('aria-modal', 'true');
      o.innerHTML =
        '<div class="lu-panel">' +
        '<div class="lu-panel__head"><h2 class="lu-panel__title" id="lu-panel-title">Contents</h2>' +
        '<button class="lu-btn lu-btn--ghost lu-btn--sm lu-panel__close" data-close>Close <kbd>Esc</kbd></button></div>' +
        '<div class="lu-panel__body"></div></div>';
      o.setAttribute('aria-labelledby', 'lu-panel-title');
      body.appendChild(o);
      Overlay.node = o;
      Overlay.title = qs('.lu-panel__title', o);
      Overlay.bodyEl = qs('.lu-panel__body', o);
      o.addEventListener('click', function (e) {
        if (e.target === o || e.target.closest('[data-close]')) Overlay.close();
      });
      o.addEventListener('keydown', function (e) {
        if (e.key !== 'Tab') return;
        var f = qsa('button, input, [href], [tabindex]:not([tabindex="-1"])', o).filter(function (n) { return n.offsetParent !== null; });
        if (!f.length) return;
        var first = f[0], last = f[f.length - 1];
        if (e.shiftKey && d.activeElement === first) { last.focus(); e.preventDefault(); }
        else if (!e.shiftKey && d.activeElement === last) { first.focus(); e.preventDefault(); }
      });
    },

    open: function (which) {
      if (!Overlay.node) return;
      Overlay.lastFocus = d.activeElement;
      Overlay.which = which;
      Overlay.node.hidden = false;
      if (which === 'toc') { Overlay.title.textContent = 'Contents'; Overlay.renderToc(); }
      else if (which === 'search') { Overlay.title.textContent = 'Search this lecture'; Overlay.renderSearch(); }
      else { Overlay.title.textContent = 'Keyboard shortcuts'; Overlay.renderHelp(); }
      var f = qs('input, .lu-toc__item, button', Overlay.bodyEl) || qs('[data-close]', Overlay.node);
      if (f) f.focus();
    },
    close: function () {
      if (!Overlay.node || Overlay.node.hidden) return;
      Overlay.node.hidden = true;
      if (Overlay.lastFocus && Overlay.lastFocus.focus) Overlay.lastFocus.focus();
    },

    renderToc: function () {
      var wrap = el('div', 'lu-toc');
      var lastGroup = null, items = null;
      Deck.slides.forEach(function (s, n) {
        var g = s.getAttribute('data-section') || '';
        if (g !== lastGroup) {
          var grp = el('div', 'lu-toc__group');
          if (g) grp.appendChild(el('div', 'lu-toc__group-name', g));
          items = el('div', 'lu-toc__items');
          grp.appendChild(items);
          wrap.appendChild(grp);
          lastGroup = g;
        }
        var b = el('button', 'lu-toc__item');
        b.type = 'button';
        b.setAttribute('data-goto', n);
        b.appendChild(el('span', 'lu-toc__n', pad(n + 1)));
        b.appendChild(el('span', null, s.getAttribute('data-label') || 'Slide ' + (n + 1)));
        items.appendChild(b);
      });
      wrap.addEventListener('click', function (e) {
        var b = e.target.closest('[data-goto]');
        if (!b) return;
        var i = parseInt(b.getAttribute('data-goto'), 10);
        IS_PRESENTER ? Deck.cmd('go', { i: i, step: 0 }) : Deck.go(i, 0);
        Overlay.close();
      });
      Overlay.bodyEl.innerHTML = '';
      Overlay.bodyEl.appendChild(wrap);
      Overlay.markToc();
    },
    markToc: function () {
      qsa('.lu-toc__item').forEach(function (b) {
        b.setAttribute('aria-current', parseInt(b.getAttribute('data-goto'), 10) === Deck.i ? 'true' : 'false');
      });
    },

    index: null,
    buildIndex: function () {
      Overlay.index = Deck.slides.map(function (s, n) {
        var c = s.cloneNode(true);
        qsa('template, .lu-print-notes, .slide__head, .slide__foot', c).forEach(function (x) { x.remove(); });
        var text = (c.textContent || '').replace(/\s+/g, ' ').trim();
        return { n: n, label: s.getAttribute('data-label') || 'Slide ' + (n + 1), text: text, hay: norm(text + ' ' + (s.getAttribute('data-label') || '')) };
      });
    },
    renderSearch: function () {
      if (!Overlay.index) Overlay.buildIndex();
      Overlay.bodyEl.innerHTML =
        '<label class="lu-sr" for="lu-q">Search slide text</label>' +
        '<input id="lu-q" class="lu-search__field" type="search" placeholder="Search slide text, e.g. OWL profile" autocomplete="off">' +
        '<div class="lu-search__results" role="listbox" aria-label="Search results"></div>';
      var input = qs('#lu-q', Overlay.bodyEl);
      var out = qs('.lu-search__results', Overlay.bodyEl);
      var run = function () {
        var q = norm(input.value);
        out.innerHTML = '';
        if (q.length < 2) { out.appendChild(el('p', 'ds-note', 'Type at least two characters.')); return; }
        var hits = Overlay.index.filter(function (r) { return r.hay.indexOf(q) >= 0; });
        if (!hits.length) { out.appendChild(el('p', 'ds-note', 'No slide contains “' + input.value + '”.')); return; }
        hits.forEach(function (r) {
          var at = r.hay.indexOf(q);
          var snip = r.text.substr(Math.max(0, at - 60), 170);
          var b = el('button', 'lu-search__hit');
          b.type = 'button';
          b.setAttribute('data-goto', r.n);
          b.appendChild(el('span', 'lu-toc__n', pad(r.n + 1)));
          var col = el('span');
          col.appendChild(el('span', 'lu-search__hit-label', r.label));
          var snipEl = el('span', 'lu-search__hit-snip');
          snipEl.textContent = (at > 60 ? '…' : '') + snip + '…';
          col.appendChild(snipEl);
          b.appendChild(col);
          out.appendChild(b);
        });
      };
      input.addEventListener('input', run);
      out.addEventListener('click', function (e) {
        var b = e.target.closest('[data-goto]');
        if (!b) return;
        var i = parseInt(b.getAttribute('data-goto'), 10);
        IS_PRESENTER ? Deck.cmd('go', { i: i, step: 0 }) : Deck.go(i, 0);
        Overlay.close();
      });
      run();
    },

    renderHelp: function () {
      var rows = [
        ['&rarr; / Space', 'Next step or slide'], ['&larr;', 'Previous step or slide'],
        ['&darr; / &uarr;', 'Next / previous slide, skipping steps'],
        ['1&hellip;9', 'Jump to slide number'], ['Home / End', 'First / last slide'],
        ['O', 'Contents'], ['/', 'Search slide text'], ['T', 'Start or pause the session timer'],
        ['S', 'Study mode (expand every popup, answer and build)'],
        ['P', 'Open presenter view on a second screen'], ['F', 'Fullscreen'], ['Esc', 'Close a panel or popup']
      ];
      Overlay.bodyEl.innerHTML = '<div class="lu-keys">' + rows.map(function (r) {
        return '<div><kbd>' + r[0] + '</kbd><span>' + r[1] + '</span></div>';
      }).join('') + '</div><p class="ds-note" style="margin-top:24px">Your position, answers and study-mode choice are kept in this browser only. Nothing is sent anywhere.</p>';
    }
  };

  /* ======================================================= 1. TERM POPOVER */
  var Term = {
    open: null,
    init: function () {
      qsa('.lu-term').forEach(function (t, n) {
        if (t.tagName !== 'BUTTON') return;
        t.type = 'button';
        t.setAttribute('aria-expanded', 'false');
        t.id = t.id || 'lu-term-' + n;
        t.addEventListener('click', function (e) { e.stopPropagation(); Term.toggle(t); });
      });
      d.addEventListener('click', function (e) {
        if (Term.open && !e.target.closest('.lu-pop') && !e.target.closest('.lu-term')) Term.closeAll();
      });
    },
    body: function (t) {
      var tpl = qs('template', t);
      if (tpl) return tpl.innerHTML;
      return (t.getAttribute('data-def') || '').replace(/&/g, '&amp;').replace(/</g, '&lt;');
    },
    toggle: function (t) {
      if (Term.open && Term.open.trigger === t) { Term.closeAll(); return; }
      Term.closeAll();
      var pop = el('div', 'lu-pop');
      pop.setAttribute('role', 'dialog');
      pop.setAttribute('aria-label', (t.getAttribute('data-term') || t.textContent.trim()) + ' definition');
      pop.innerHTML =
        '<button class="lu-pop__close" aria-label="Close definition">&times;</button>' +
        (t.getAttribute('data-kind') ? '<div class="lu-pop__kind">' + t.getAttribute('data-kind') + '</div>' : '') +
        '<div class="lu-pop__title">' + (t.getAttribute('data-term') || t.textContent.trim().replace(/\?$/, '')) + '</div>' +
        '<div class="lu-pop__body">' + Term.body(t) + '</div>';
      (t.closest('.slide') || body).appendChild(pop);

      var host = t.closest('.slide') || body;
      var hb = host.getBoundingClientRect();
      var tb = t.getBoundingClientRect();
      var scale = hb.width / (host.offsetWidth || hb.width) || 1;
      var left = (tb.left - hb.left) / scale;
      var top = (tb.bottom - hb.top) / scale + 10;
      pop.style.left = '0px';
      var pw = pop.offsetWidth;
      pop.style.left = Math.round(clamp(left, 16, (host.offsetWidth || 1600) - pw - 16)) + 'px';
      var ph = pop.offsetHeight;
      if (top + ph > (host.offsetHeight || 900) - 16) top = Math.max(16, (tb.top - hb.top) / scale - ph - 10);
      pop.style.top = Math.round(top) + 'px';

      requestAnimationFrame(function () { pop.classList.add('is-open'); });
      t.setAttribute('aria-expanded', 'true');
      qs('.lu-pop__close', pop).addEventListener('click', function () { Term.closeAll(); t.focus(); });
      Term.open = { trigger: t, pop: pop };
    },
    closeAll: function () {
      if (!Term.open) return;
      Term.open.pop.remove();
      Term.open.trigger.setAttribute('aria-expanded', 'false');
      Term.open = null;
    },
    /* Study mode: definitions become inline notes instead of popovers. */
    inline: function (t, on) {
      var id = 'lu-inline-' + (t.id || '');
      var existing = t.parentNode && qs('#' + CSS.escape(id), t.closest('.slide') || d);
      if (!on) { if (existing) existing.remove(); return; }
      if (existing) return;
      var host = t.closest('li, p, .lu-p, .lu-lead, .lu-statement, dd, .lu-card') || t.parentNode;
      var note = el('div', 'lu-inline-def');
      note.id = id;
      note.innerHTML = '<b>' + (t.getAttribute('data-term') || t.textContent.trim().replace(/\?$/, '')) + '.</b> ' + Term.body(t);
      if (host.parentNode) host.parentNode.insertBefore(note, host.nextSibling);
    }
  };

  /* ====================================================== 2. CLICK REVEAL */
  var Reveal = {
    init: function () {
      qsa('.lu-reveal').forEach(function (r, n) {
        var btn = qs('.lu-reveal__btn', r);
        var panel = qs('.lu-reveal__panel', r);
        if (!btn || !panel) return;
        panel.id = panel.id || 'lu-reveal-' + n;
        btn.type = 'button';
        btn.setAttribute('aria-controls', panel.id);
        var open = body.classList.contains('lu-selfstudy');
        Reveal.set(btn, open);
        btn.addEventListener('click', function () {
          Reveal.set(btn, btn.getAttribute('aria-expanded') !== 'true');
        });
      });
    },
    set: function (btn, open) {
      var panel = d.getElementById(btn.getAttribute('aria-controls'));
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (panel) panel.hidden = !open;
    }
  };

  /* ======================================================== 3. MULTI CHOICE */
  var Mcq = {
    init: function () {
      qsa('.lu-mcq').forEach(function (m) { Mcq.wire(m); });
    },
    wire: function (m) {
      var qid = m.getAttribute('data-qid');
      var answer = (m.getAttribute('data-answer') || '').trim();
      var opts = qsa('.lu-mcq__opt', m);
      var fb = qs('.lu-mcq__fb', m) || (function () { var f = el('div', 'lu-mcq__fb'); f.hidden = true; m.appendChild(f); return f; })();
      var group = qs('.lu-mcq__opts', m);
      if (group) { group.setAttribute('role', 'group'); group.setAttribute('aria-label', 'Answer options'); }

      opts.forEach(function (o, idx) {
        o.type = 'button';
        var key = o.getAttribute('data-key') || String.fromCharCode(97 + idx);
        o.setAttribute('data-key', key);
        if (!qs('.lu-mcq__key', o)) {
          var k = el('span', 'lu-mcq__key', key.toUpperCase());
          k.setAttribute('aria-hidden', 'true');
          o.insertBefore(k, o.firstChild);
        }
        o.addEventListener('click', function () { Mcq.answer(m, key); });
      });

      register({
        qid: qid, kind: 'Multiple choice',
        label: m.getAttribute('data-label') || (qs('.lu-mcq__q', m) || {}).textContent || 'Question',
        slide: m.closest('.slide'),
        check: function () {
          var a = answers[qid];
          return a == null ? null : a === answer;
        }
      });

      if (answers[qid] != null) Mcq.answer(m, answers[qid], true);
      else if (body.classList.contains('lu-selfstudy')) Mcq.answer(m, answer, true);
    },
    answer: function (m, key, silent) {
      var answer = (m.getAttribute('data-answer') || '').trim();
      var ok = key === answer;
      qsa('.lu-mcq__opt', m).forEach(function (o) {
        var k = o.getAttribute('data-key');
        o.disabled = true;
        if (k === answer) o.setAttribute('data-verdict', 'correct');
        else if (k === key) o.setAttribute('data-verdict', 'wrong');
        else o.setAttribute('data-verdict', 'dim');
        var why = qs('.lu-mcq__why', o);
        if (why) why.hidden = false;
      });
      var fb = qs('.lu-mcq__fb', m);
      var chosen = qsa('.lu-mcq__opt', m).filter(function (o) { return o.getAttribute('data-key') === key; })[0];
      var note = m.getAttribute(ok ? 'data-fb-correct' : 'data-fb-wrong') || m.getAttribute('data-fb') || '';
      if (fb) {
        fb.hidden = false;
        fb.setAttribute('data-verdict', ok ? 'correct' : 'wrong');
        fb.innerHTML = '<b>' + (ok ? 'Correct.' : 'Not quite.') + '</b>' + note;
        if (!silent) fb.setAttribute('role', 'status');
      }
      if (!silent) saveAnswer(m.getAttribute('data-qid'), key);
      else Deck.refreshScores();
      if (chosen && !silent) chosen.focus();
    }
  };

  /* ==================================================== 4. WALKTHROUGH */
  var Walk = {
    init: function () {
      qsa('.lu-walk').forEach(function (w, wi) {
        var steps = qsa('[data-walk-step]', w);
        if (!steps.length) return;
        w.setAttribute('tabindex', '0');
        w.setAttribute('role', 'group');
        w.setAttribute('aria-label', (w.getAttribute('data-label') || 'Diagram') + ' walkthrough, ' + steps.length + ' steps. Use left and right arrow keys.');

        var bar = el('div', 'lu-walk__bar');
        var dots = el('div', 'lu-walk__dots');
        steps.forEach(function (s, i) {
          var b = el('button', 'lu-walk__dot');
          b.type = 'button';
          b.setAttribute('data-step', i);
          b.setAttribute('aria-label', 'Step ' + (i + 1) + ': ' + (s.getAttribute('data-caption-short') || s.getAttribute('data-walk-step') || ''));
          dots.appendChild(b);
        });
        var cap = el('div', 'lu-walk__cap');
        cap.setAttribute('aria-live', 'polite');
        var count = el('div', 'lu-walk__count');
        var nav = el('div', 'lu-walk__nav');
        nav.innerHTML =
          '<button class="lu-btn lu-btn--ghost lu-btn--sm" data-walk="-1" aria-label="Previous step">&#8592;</button>' +
          '<button class="lu-btn lu-btn--sm" data-walk="1" aria-label="Next step">Next step &#8594;</button>';
        bar.appendChild(dots); bar.appendChild(cap); bar.appendChild(count); bar.appendChild(nav);
        w.appendChild(bar);

        w._steps = steps; w._cap = cap; w._count = count; w._dots = dots; w._at = 0;
        bar.addEventListener('click', function (e) {
          var dot = e.target.closest('[data-step]');
          if (dot) { Walk.set(w, parseInt(dot.getAttribute('data-step'), 10)); return; }
          var nb = e.target.closest('[data-walk]');
          if (nb) Walk.nudge(w, parseInt(nb.getAttribute('data-walk'), 10));
        });
        Walk.set(w, 0);
      });
    },
    nudge: function (w, dir) {
      if (!w._steps) return;
      Walk.set(w, clamp(w._at + dir, 0, w._steps.length - 1));
    },
    set: function (w, i) {
      w._at = i;
      w._steps.forEach(function (s, si) { s.hidden = si !== i; });
      var s = w._steps[i];
      w._cap.innerHTML = s.getAttribute('data-caption') || '';
      w._count.textContent = (i + 1) + '/' + w._steps.length;
      qsa('.lu-walk__dot', w._dots).forEach(function (b, bi) { b.setAttribute('aria-current', bi === i ? 'true' : 'false'); });
      qsa('[data-walk="-1"]', w).forEach(function (b) { b.disabled = i === 0; });
      qsa('[data-walk="1"]', w).forEach(function (b) { b.disabled = i === w._steps.length - 1; });
    }
  };

  /* ======================================================== 5. SORTABLE */
  var Sort = {
    init: function () {
      qsa('.lu-sort').forEach(function (s) {
        var list = qs('.lu-sort__list', s);
        if (!list) return;
        var qid = s.getAttribute('data-qid');
        var items = qsa('.lu-sort__item', list);
        list.setAttribute('role', 'list');

        items.forEach(function (it) {
          it.setAttribute('role', 'listitem');
          it.draggable = true;
          if (!qs('.lu-sort__pos', it)) it.insertBefore(el('span', 'lu-sort__pos'), it.firstChild);
          if (!qs('.lu-sort__move', it)) {
            var mv = el('span', 'lu-sort__move');
            mv.innerHTML =
              '<button class="lu-btn lu-btn--ghost" data-mv="-1" aria-label="Move up">&#8593;</button>' +
              '<button class="lu-btn lu-btn--ghost" data-mv="1" aria-label="Move down">&#8595;</button>';
            it.appendChild(mv);
          }
          it.addEventListener('dragstart', function (e) {
            Sort.drag = it; it.classList.add('is-dragging');
            e.dataTransfer.effectAllowed = 'move';
            try { e.dataTransfer.setData('text/plain', ''); } catch (x) {}
          });
          it.addEventListener('dragend', function () { it.classList.remove('is-dragging'); qsa('.is-over', list).forEach(function (n) { n.classList.remove('is-over'); }); });
          it.addEventListener('dragover', function (e) {
            e.preventDefault();
            if (!Sort.drag || Sort.drag === it) return;
            it.classList.add('is-over');
          });
          it.addEventListener('dragleave', function () { it.classList.remove('is-over'); });
          it.addEventListener('drop', function (e) {
            e.preventDefault();
            it.classList.remove('is-over');
            if (!Sort.drag || Sort.drag === it) return;
            var nodes = qsa('.lu-sort__item', list);
            var from = nodes.indexOf(Sort.drag), to = nodes.indexOf(it);
            list.insertBefore(Sort.drag, from < to ? it.nextSibling : it);
            Sort.renumber(s);
          });
        });

        list.addEventListener('click', function (e) {
          var b = e.target.closest('[data-mv]');
          if (!b) return;
          var it = b.closest('.lu-sort__item');
          var dir = parseInt(b.getAttribute('data-mv'), 10);
          if (dir < 0 && it.previousElementSibling) list.insertBefore(it, it.previousElementSibling);
          if (dir > 0 && it.nextElementSibling) list.insertBefore(it.nextElementSibling, it);
          Sort.renumber(s);
          b.focus();
        });

        var bar = el('div', 'lu-row');
        bar.innerHTML = '<button class="lu-btn lu-btn--primary lu-btn--sm" data-sort-check>Check order</button>' +
          '<span class="lu-caption" data-sort-msg aria-live="polite"></span>';
        s.appendChild(bar);
        bar.addEventListener('click', function (e) { if (e.target.closest('[data-sort-check]')) Sort.check(s); });

        register({
          qid: qid, kind: 'Ordering',
          label: s.getAttribute('data-label') || 'Put the steps in order',
          slide: s.closest('.slide'),
          check: function () { var a = answers[qid]; return a == null ? null : !!a.ok; }
        });

        if (answers[qid] && answers[qid].order) Sort.restore(s, answers[qid].order);
        Sort.renumber(s);
        if (body.classList.contains('lu-selfstudy')) { Sort.solve(s); }
      });
    },
    renumber: function (s) {
      qsa('.lu-sort__item', s).forEach(function (it, i) {
        var p = qs('.lu-sort__pos', it);
        if (p) p.textContent = i + 1;
        it.removeAttribute('data-verdict');
      });
      var msg = qs('[data-sort-msg]', s);
      if (msg) msg.textContent = '';
    },
    restore: function (s, order) {
      var list = qs('.lu-sort__list', s);
      order.forEach(function (rank) {
        var node = qsa('.lu-sort__item', list).filter(function (n) { return n.getAttribute('data-rank') === String(rank); })[0];
        if (node) list.appendChild(node);
      });
    },
    solve: function (s) {
      var list = qs('.lu-sort__list', s);
      qsa('.lu-sort__item', list)
        .sort(function (a, b) { return +a.getAttribute('data-rank') - +b.getAttribute('data-rank'); })
        .forEach(function (n) { list.appendChild(n); });
      Sort.check(s);
    },
    check: function (s) {
      var items = qsa('.lu-sort__item', s);
      var ok = true;
      items.forEach(function (it, i) {
        var right = +it.getAttribute('data-rank') === i + 1;
        it.setAttribute('data-verdict', right ? 'correct' : 'wrong');
        if (!right) ok = false;
      });
      var msg = qs('[data-sort-msg]', s);
      if (msg) msg.textContent = ok ? 'Correct order.' : items.filter(function (i2) { return i2.getAttribute('data-verdict') === 'correct'; }).length + ' of ' + items.length + ' in the right place.';
      saveAnswer(s.getAttribute('data-qid'), { ok: ok, order: items.map(function (i2) { return +i2.getAttribute('data-rank'); }) });
    }
  };

  /* ==================================================== 6. FILL THE BLANK */
  var Blanks = {
    init: function () {
      qsa('.lu-blanks').forEach(function (g) {
        var qid = g.getAttribute('data-qid');
        var inputs = qsa('.lu-blank', g);
        inputs.forEach(function (inp, i) {
          inp.setAttribute('aria-label', inp.getAttribute('data-label') || 'Blank ' + (i + 1));
          inp.placeholder = inp.placeholder || '…';
          inp.addEventListener('input', function () { inp.removeAttribute('data-verdict'); });
          inp.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); Blanks.check(g); } });
        });
        var bar = el('div', 'lu-row');
        bar.innerHTML = '<button class="lu-btn lu-btn--primary lu-btn--sm" data-blank-check>Check</button>' +
          '<button class="lu-btn lu-btn--ghost lu-btn--sm" data-blank-show>Show answers</button>' +
          '<span class="lu-caption" data-blank-msg aria-live="polite"></span>';
        g.appendChild(bar);
        bar.addEventListener('click', function (e) {
          if (e.target.closest('[data-blank-check]')) Blanks.check(g);
          if (e.target.closest('[data-blank-show]')) Blanks.reveal(g);
        });
        register({
          qid: qid, kind: 'Fill in the blank',
          label: g.getAttribute('data-label') || 'Complete the statement',
          slide: g.closest('.slide'),
          check: function () { var a = answers[qid]; return a == null ? null : !!a.ok; }
        });
        var saved = answers[qid];
        if (saved && saved.vals) { inputs.forEach(function (inp, i) { inp.value = saved.vals[i] || ''; }); Blanks.check(g, true); }
        if (body.classList.contains('lu-selfstudy')) Blanks.reveal(g);
      });
    },
    accepts: function (inp) {
      return (inp.getAttribute('data-answer') || '').split('|').map(norm).filter(Boolean);
    },
    check: function (g, silent) {
      var inputs = qsa('.lu-blank', g);
      var right = 0;
      inputs.forEach(function (inp) {
        var ok = Blanks.accepts(inp).indexOf(norm(inp.value)) >= 0;
        inp.setAttribute('data-verdict', ok ? 'correct' : 'wrong');
        if (ok) right++;
      });
      var ok = right === inputs.length;
      var msg = qs('[data-blank-msg]', g);
      if (msg) msg.textContent = ok ? 'All correct.' : right + ' of ' + inputs.length + ' correct.';
      if (!silent) saveAnswer(g.getAttribute('data-qid'), { ok: ok, vals: inputs.map(function (i2) { return i2.value; }) });
      else Deck.refreshScores();
    },
    reveal: function (g) {
      qsa('.lu-blank', g).forEach(function (inp) {
        inp.value = (inp.getAttribute('data-answer') || '').split('|')[0];
        inp.setAttribute('data-verdict', 'correct');
      });
      var msg = qs('[data-blank-msg]', g);
      if (msg) msg.textContent = 'Answers shown.';
    }
  };

  /* ==================================================== 7. COMPARE SLIDER */
  var Compare = {
    init: function () {
      qsa('.lu-compare').forEach(function (c, n) {
        var stage = qs('.lu-compare__stage', c);
        if (!stage) return;
        if (!qs('.lu-compare__seam', stage)) stage.appendChild(el('div', 'lu-compare__seam'));
        var ta = c.getAttribute('data-a'), tb = c.getAttribute('data-b');
        if (ta && !qs('.lu-compare__tag--a', stage)) stage.appendChild(el('div', 'lu-compare__tag lu-compare__tag--a', ta));
        if (tb && !qs('.lu-compare__tag--b', stage)) stage.appendChild(el('div', 'lu-compare__tag lu-compare__tag--b', tb));

        var r = el('input', 'lu-compare__range');
        r.type = 'range'; r.min = 0; r.max = 100; r.value = c.getAttribute('data-start') || 50;
        r.id = 'lu-cmp-' + n;
        r.setAttribute('aria-label', 'Wipe between ' + (ta || 'A') + ' and ' + (tb || 'B'));
        c.appendChild(r);
        var set = function () { c.style.setProperty('--lu-wipe', r.value + '%'); };
        r.addEventListener('input', set);
        set();
      });
    }
  };

  /* ============================================== 8. CODE: copy + run JS */
  var Code = {
    init: function () {
      qsa('.lu-code').forEach(function (c, n) {
        var pre = qs('pre', c);
        if (!pre) return;
        var bar = qs('.lu-code__bar', c);
        if (!bar) { bar = el('div', 'lu-code__bar'); bar.appendChild(el('span', 'lu-code__name', c.getAttribute('data-name') || '')); c.insertBefore(bar, pre); }
        var tools = qs('.lu-code__tools', bar) || bar.appendChild(el('div', 'lu-code__tools'));

        var copy = el('button', 'lu-btn', 'Copy');
        copy.type = 'button';
        copy.addEventListener('click', function () {
          var txt = pre.innerText;
          var done = function () { copy.textContent = 'Copied'; setTimeout(function () { copy.textContent = 'Copy'; }, 1400); };
          if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(done, done);
          else {
            var ta = el('textarea'); ta.value = txt; body.appendChild(ta); ta.select();
            try { d.execCommand('copy'); } catch (x) {}
            ta.remove(); done();
          }
        });
        tools.appendChild(copy);

        if (c.getAttribute('data-run') === 'js') {
          var out = el('div', 'lu-query__msg');
          out.hidden = true;
          c.appendChild(out);
          var run = el('button', 'lu-btn', 'Run');
          run.type = 'button';
          run.addEventListener('click', function () {
            out.hidden = false;
            out.textContent = 'Running…';
            Code.run(pre.innerText, function (lines) {
              out.classList.remove('lu-query__msg--err');
              out.style.fontFamily = 'var(--lu-mono)';
              out.style.color = 'var(--lu-on-night-2)';
              out.textContent = lines.length ? lines.join('\n') : '(no output)';
              out.style.whiteSpace = 'pre-wrap';
            });
          });
          tools.appendChild(run);
        }
      });
    },
    /* Runs in a sandboxed, same-origin-blocked iframe. Console output only. */
    run: function (src, cb) {
      var f = d.createElement('iframe');
      f.setAttribute('sandbox', 'allow-scripts');
      f.style.cssText = 'position:absolute;width:0;height:0;border:0;left:-9999px';
      var token = 'lu' + Math.random().toString(36).slice(2);
      var lines = [];
      var onMsg = function (e) {
        if (!e.data || e.data.token !== token) return;
        if (e.data.done) { window.removeEventListener('message', onMsg); f.remove(); cb(lines); }
        else lines.push(e.data.line);
      };
      window.addEventListener('message', onMsg);
      var html = '<script>(function(){var T=' + JSON.stringify(token) + ';' +
        'var S=function(l){parent.postMessage({token:T,line:String(l)},"*")};' +
        'console.log=function(){S(Array.prototype.map.call(arguments,function(a){try{return typeof a==="object"?JSON.stringify(a):String(a)}catch(e){return String(a)}}).join(" "))};' +
        'console.error=console.warn=console.info=console.log;' +
        'try{' + src.replace(/<\/script/gi, '<\\/script') + '}catch(e){S("Error: "+e.message)}' +
        'parent.postMessage({token:T,done:1},"*")})()<\/script>';
      f.srcdoc = html;
      body.appendChild(f);
      setTimeout(function () { if (d.contains(f)) { window.removeEventListener('message', onMsg); f.remove(); cb(lines.concat(['(stopped after 3s)'])); } }, 3000);
    }
  };

  /* ==================================================== 9. QUERY SANDBOX */
  var Query = {
    init: function () {
      qsa('.lu-query').forEach(function (q, n) {
        var lang = (q.getAttribute('data-lang') || 'sparql').toLowerCase();
        var dataTpl = qs('template[data-data]', q);
        var qTpl = qs('template[data-query]', q);

        var left = el('div', 'lu-query__side');
        var bar = el('div', 'lu-query__bar');
        bar.innerHTML = '<span class="lu-query__label">' + (lang === 'sparql' ? 'SPARQL' : 'SQL') + '</span>' +
          '<button class="lu-btn lu-btn--sm lu-btn--ghost" data-q-reset>Reset</button>' +
          '<button class="lu-btn lu-btn--primary lu-btn--sm" data-q-run>Run query</button>';
        var ta = el('textarea', 'lu-query__editor');
        ta.id = 'lu-q-' + n;
        ta.spellcheck = false;
        ta.setAttribute('aria-label', 'Query editor');
        var seed = qTpl ? qTpl.innerHTML.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&').trim() : '';
        ta.value = Store.get('q:' + n, seed) || seed;
        left.appendChild(bar); left.appendChild(ta);

        var right = el('div', 'lu-query__side');
        var rbar = el('div', 'lu-query__bar');
        rbar.innerHTML = '<span class="lu-query__label">Result</span><span class="lu-caption" data-q-note></span>';
        var out = el('div', 'lu-query__out');
        out.setAttribute('aria-live', 'polite');
        out.appendChild(el('div', 'lu-query__msg', 'Run the query to see results.'));
        right.appendChild(rbar); right.appendChild(out);

        q.appendChild(left); q.appendChild(right);

        var raw = dataTpl ? dataTpl.innerHTML.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&') : '';
        var store = null;
        var run = function () {
          Store.set('q:' + n, ta.value);
          out.innerHTML = '';
          if (lang !== 'sparql' || !window.LUSparql) {
            out.appendChild(el('div', 'lu-query__msg lu-query__msg--err',
              lang === 'sparql' ? 'sparql-lite.js is not loaded.' : 'SQL mode needs an engine vendored into assets/. See AGENTS.md.'));
            return;
          }
          try {
            if (!store) store = window.LUSparql.parse(raw);
            var res = window.LUSparql.query(store, ta.value);
            out.appendChild(Query.table(res));
            var note = qs('[data-q-note]', rbar);
            if (note) note.textContent = res.rows.length + (res.rows.length === 1 ? ' row' : ' rows') + ' · ' + store.triples.length + ' triples';
          } catch (err) {
            out.appendChild(el('div', 'lu-query__msg lu-query__msg--err', String(err && err.message || err)));
          }
        };
        bar.addEventListener('click', function (e) {
          if (e.target.closest('[data-q-run]')) run();
          if (e.target.closest('[data-q-reset]')) { ta.value = seed; run(); }
        });
        ta.addEventListener('keydown', function (e) {
          if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { run(); e.preventDefault(); }
        });
        if (q.getAttribute('data-autorun') !== 'false') run();
      });
    },
    table: function (res) {
      if (!res.rows.length) return el('div', 'lu-query__msg', 'No rows matched. The query is valid; the pattern found nothing.');
      var t = el('table', 'lu-table lu-table--mono');
      var thead = el('thead'), tr = el('tr');
      res.vars.forEach(function (v) { tr.appendChild(el('th', null, '?' + v)); });
      thead.appendChild(tr); t.appendChild(thead);
      var tb = el('tbody');
      res.rows.slice(0, 60).forEach(function (r) {
        var row = el('tr');
        res.vars.forEach(function (v) { row.appendChild(el('td', null, r[v] == null ? '\u00b7' : r[v])); });
        tb.appendChild(row);
      });
      t.appendChild(tb);
      return t;
    }
  };

  /* ======================================================= 10. TIMED POLL */
  var Poll = {
    init: function () {
      qsa('.lu-poll').forEach(function (p) {
        var secs = parseInt(p.getAttribute('data-seconds') || '60', 10);
        var answer = (p.getAttribute('data-answer') || '').trim();
        var qid = p.getAttribute('data-qid');
        var opts = qsa('.lu-mcq__opt', p);

        var timer = el('div', 'lu-poll__timer');
        timer.innerHTML = '<span data-poll-clock>' + mmss(secs) + '</span><span class="lu-poll__track"><span class="lu-poll__fill"></span></span>';
        var ctrl = el('div', 'lu-row');
        ctrl.innerHTML = '<button class="lu-btn lu-btn--primary lu-btn--sm" data-poll-start>Start ' + secs + 's</button>' +
          '<button class="lu-btn lu-btn--ghost lu-btn--sm" data-poll-reveal>Reveal answer</button>' +
          '<span class="lu-caption" data-poll-msg aria-live="polite"></span>';
        var opsNode = qs('.lu-mcq__opts', p);
        p.insertBefore(timer, opsNode);
        p.appendChild(ctrl);

        var bars = el('div', 'lu-poll__bars');
        bars.hidden = true;
        p.appendChild(bars);

        opts.forEach(function (o, idx) {
          o.type = 'button';
          var key = o.getAttribute('data-key') || String.fromCharCode(97 + idx);
          o.setAttribute('data-key', key);
          if (!qs('.lu-mcq__key', o)) {
            var k = el('span', 'lu-mcq__key', key.toUpperCase());
            k.setAttribute('aria-hidden', 'true');
            o.insertBefore(k, o.firstChild);
          }
          o.addEventListener('click', function () {
            qsa('.lu-mcq__opt', p).forEach(function (x) { x.removeAttribute('data-verdict'); });
            o.setAttribute('data-verdict', 'correct');
            saveAnswer(qid, key);
            qs('[data-poll-msg]', p).textContent = 'Your answer: ' + key.toUpperCase() + '. Locked in.';
          });

          var bar = el('div', 'lu-poll__bar');
          bar.setAttribute('data-key', key);
          if (key === answer) bar.setAttribute('data-correct', 'true');
          bar.innerHTML = '<span class="lu-mcq__key" aria-hidden="true">' + key.toUpperCase() + '</span>' +
            '<span class="lu-poll__meter"><span></span></span>' +
            '<span class="lu-row" style="gap:4px"><button class="lu-btn lu-btn--ghost" data-tally="-1" aria-label="Fewer for ' + key.toUpperCase() + '" style="min-height:34px;min-width:34px;padding:0">&minus;</button>' +
            '<span class="lu-poll__n" data-n>0</span>' +
            '<button class="lu-btn lu-btn--ghost" data-tally="1" aria-label="More for ' + key.toUpperCase() + '" style="min-height:34px;min-width:34px;padding:0">+</button></span>';
          bars.appendChild(bar);
        });

        var tally = {};
        bars.addEventListener('click', function (e) {
          var b = e.target.closest('[data-tally]');
          if (!b) return;
          var bar = b.closest('.lu-poll__bar');
          var key = bar.getAttribute('data-key');
          tally[key] = Math.max(0, (tally[key] || 0) + parseInt(b.getAttribute('data-tally'), 10));
          var total = Object.keys(tally).reduce(function (a, k) { return a + tally[k]; }, 0) || 1;
          qsa('.lu-poll__bar', bars).forEach(function (x) {
            var k = x.getAttribute('data-key');
            qs('[data-n]', x).textContent = tally[k] || 0;
            qs('.lu-poll__meter > span', x).style.width = ((tally[k] || 0) / total * 100) + '%';
          });
        });

        var t = null, left = secs;
        var paint = function () {
          qs('[data-poll-clock]', p).textContent = mmss(left);
          qs('.lu-poll__fill', p).style.width = (left / secs * 100) + '%';
        };
        ctrl.addEventListener('click', function (e) {
          if (e.target.closest('[data-poll-start]')) {
            clearInterval(t); left = secs; p.classList.remove('is-up'); paint();
            t = setInterval(function () {
              left--; paint();
              if (left <= 0) { clearInterval(t); p.classList.add('is-up'); qs('[data-poll-msg]', p).textContent = 'Time. Show the room.'; }
            }, 1000);
          }
          if (e.target.closest('[data-poll-reveal]')) {
            bars.hidden = false;
            qsa('.lu-mcq__opt', p).forEach(function (o) {
              o.setAttribute('data-verdict', o.getAttribute('data-key') === answer ? 'correct' : 'dim');
              var w = qs('.lu-mcq__why', o); if (w) w.hidden = false;
            });
            qs('[data-poll-msg]', p).textContent = 'Answer: ' + answer.toUpperCase() + '. Tally the room with the plus buttons.';
          }
        });

        register({
          qid: qid, kind: 'Poll',
          label: p.getAttribute('data-label') || (qs('.lu-mcq__q', p) || {}).textContent || 'Poll',
          slide: p.closest('.slide'),
          check: function () { var a = answers[qid]; return a == null ? null : a === answer; }
        });
        if (answers[qid]) {
          var mine = qsa('.lu-mcq__opt', p).filter(function (o) { return o.getAttribute('data-key') === answers[qid]; })[0];
          if (mine) mine.setAttribute('data-picked', 'true');
        }
        paint();
      });
    }
  };

  /* ==================================================== 11. SELF-CHECK */
  var Score = {
    init: function () { qsa('[data-score]').forEach(Score.paint); },
    paint: function (host) {
      var rows = graded.filter(function (g) { return g.qid; });
      var done = rows.filter(function (g) { return g.check() !== null; });
      var right = rows.filter(function (g) { return g.check() === true; }).length;

      host.classList.add('lu-score');
      host.innerHTML = '';
      var big = el('div', 'lu-score__big');
      big.appendChild(el('div', 'lu-score__num', String(right)));
      big.appendChild(el('div', 'lu-score__of', 'of ' + rows.length + ' correct · ' + done.length + ' attempted'));
      host.appendChild(big);

      var list = el('div', 'lu-score__list');
      rows.forEach(function (g) {
        var v = g.check();
        var row = el('div', 'lu-score__row');
        row.setAttribute('data-ok', v === null ? 'none' : String(v));
        row.appendChild(el('span', 'lu-score__mark', v === null ? '·' : v ? '✓' : '✕'));
        var mid = el('span');
        mid.appendChild(el('span', null, String(g.label).trim().slice(0, 110)));
        mid.appendChild(el('span', 'lu-caption', '  ' + g.kind));
        row.appendChild(mid);
        var n = g.slide ? Deck.slides.indexOf(g.slide) : -1;
        if (n >= 0) {
          var go = el('button', 'lu-btn lu-btn--ghost lu-btn--sm lu-score__go', 'Slide ' + (n + 1));
          go.type = 'button';
          go.addEventListener('click', function () { Deck.go(n, 0); });
          row.appendChild(go);
        }
        list.appendChild(row);
      });
      host.appendChild(list);

      var bar = el('div', 'lu-row');
      var reset = el('button', 'lu-btn lu-btn--ghost lu-btn--sm', 'Clear my answers');
      reset.type = 'button';
      reset.addEventListener('click', function () {
        answers = {};
        Store.set('answers', {});
        location.reload();
      });
      bar.appendChild(reset);
      bar.appendChild(el('span', 'lu-caption', 'Saved in this browser only.'));
      host.appendChild(bar);
    }
  };

  /* ================================================== PRESENTER VIEW */
  var PV = {
    build: function () {
      body.classList.add('lu-presenter');
      var slides = qsa('.slide', qs('.deck__stage'));
      var wrap = el('div', 'lu-pv');
      wrap.innerHTML =
        '<div class="lu-pv__top">' +
        '<div class="lu-pv__clock" data-pv-clock>00:00</div>' +
        '<div class="lu-pv__elapsed" data-pv-time>00:00</div>' +
        '<div class="lu-pv__pace" data-pv-pace>on plan</div>' +
        '</div>' +
        '<div class="lu-pv__notes"><h3 data-pv-label>Slide</h3><div data-pv-notes></div></div>' +
        '<div class="lu-pv__side">' +
        '<div class="lu-pv__thumb" data-pv-now><span class="lu-pv__thumb-label">Now</span><div class="lu-pv__thumb-inner"></div></div>' +
        '<div class="lu-pv__thumb" data-pv-next><span class="lu-pv__thumb-label">Next</span><div class="lu-pv__thumb-inner"></div></div>' +
        '</div>' +
        '<div class="lu-pv__bottom">' +
        '<button class="lu-btn lu-btn--night lu-btn--sm" data-pv="prev">&#8592; Back</button>' +
        '<button class="lu-btn lu-btn--night lu-btn--sm" data-pv="next">Forward &#8594;</button>' +
        '<button class="lu-btn lu-btn--night lu-btn--sm" data-pv="timer">Start / pause timer</button>' +
        '<button class="lu-btn lu-btn--night lu-btn--sm" data-pv="toc">Contents</button>' +
        '<span class="lu-pv__meta" data-pv-meta></span>' +
        '</div>';
      body.appendChild(wrap);
      PV.wrap = wrap;
      PV.slides = slides;

      wrap.addEventListener('click', function (e) {
        var b = e.target.closest('[data-pv]');
        if (!b) return;
        var a = b.getAttribute('data-pv');
        if (a === 'toc') Overlay.open('toc');
        else Deck.cmd(a);
      });

      setInterval(function () {
        var now = new Date();
        qs('[data-pv-clock]', wrap).textContent = pad(now.getHours()) + ':' + pad(now.getMinutes());
      }, 1000);

      PV.paint({ i: Deck.hashTarget() ? Deck.hashTarget().i : 0, step: 0, elapsed: 0 });
      // Ask the presenting window for current state.
      Deck.cmd('ping');
    },

    thumb: function (hostSel, idx) {
      var host = qs(hostSel + ' .lu-pv__thumb-inner', PV.wrap);
      if (!host) return;
      host.innerHTML = '';
      var s = PV.slides[idx];
      if (!s) { host.appendChild(el('div', 'lu-query__msg', 'End of lecture')); return; }
      var stage = el('div', 'deck__stage');
      var c = s.cloneNode(true);
      qsa('[id]', c).forEach(function (n) { n.removeAttribute('id'); });
      qsa('[data-build]', c).forEach(function (n) { n.classList.add('is-built'); });
      c.classList.add('is-active');
      stage.appendChild(c);
      host.appendChild(stage);
      var w = host.clientWidth || 400;
      stage.style.transform = 'scale(' + (w / 1600) + ')';
      host.style.height = Math.round(900 * (w / 1600)) + 'px';
    },

    paint: function (m) {
      var i = m.i || 0;
      if (!m.light || PV.at !== i) {
        PV.at = i;
        var s = PV.slides[i];
        qs('[data-pv-label]', PV.wrap).textContent = 'Slide ' + (i + 1) + ' \u00b7 ' + ((s && s.getAttribute('data-label')) || '');
        var notes = s ? Deck.notesFor(s) : '';
        qs('[data-pv-notes]', PV.wrap).innerHTML = notes || '<p style="opacity:.6">No notes for this slide.</p>';
        qs('[data-pv-meta]', PV.wrap).textContent =
          [(s && s.getAttribute('data-section')) || '', (s && s.getAttribute('data-minutes')) ? s.getAttribute('data-minutes') + ' min planned' : '', (i + 1) + ' of ' + PV.slides.length].filter(Boolean).join('  ·  ');
        PV.thumb('[data-pv-now]', i);
        PV.thumb('[data-pv-next]', i + 1);
      }
      var planned = 0;
      for (var k = 0; k <= i; k++) planned += parseFloat(PV.slides[k].getAttribute('data-minutes') || 0);
      var drift = (m.elapsed || 0) / 60 - planned;
      var pe = qs('[data-pv-pace]', PV.wrap);
      qs('[data-pv-time]', PV.wrap).textContent = mmss(m.elapsed || 0) + (m.running ? '' : ' (paused)');
      if (planned) {
        pe.textContent = (drift > 0 ? 'behind by ' : drift < 0 ? 'ahead by ' : 'on plan ') + Math.abs(Math.round(drift)) + 'm';
        pe.setAttribute('data-pace', drift > 2 ? 'behind' : drift < -2 ? 'ahead' : 'on');
      } else { pe.textContent = 'no plan set'; }
    }
  };

  /* ====================================================== PWA / OFFLINE */
  function registerSW() {
    if (!('serviceWorker' in navigator)) return;
    if (location.protocol !== 'http:' && location.protocol !== 'https:') return;
    try {
      navigator.serviceWorker.register(new URL(APP_ROOT + 'sw.js', location.href).href, {
        scope: new URL(APP_ROOT, location.href).href,
        // Never let the HTTP cache answer for sw.js itself, or a fixed worker
        // can take a day to reach a browser that already has the old one.
        updateViaCache: 'none'
      }).then(function (reg) { if (reg && reg.update) reg.update(); })
        .catch(function () { /* offline cache is a bonus, never a blocker */ });
    } catch (e) {}
  }

  /* Authoring guard. A .slide is a fixed box with overflow:hidden, so content
     that does not fit is silently cut off the bottom with no scrollbar and no
     error. Report it once, loudly, to whoever is writing the lecture. */
  function auditOverflow() {
    setTimeout(function () {
      var bad = [];
      qsa('.slide').forEach(function (s, i) {
        var body = qs('.slide__body', s);
        if (!body) return;
        var over = body.scrollHeight - body.clientHeight;
        if (over > 4) bad.push('  slide ' + (i + 1) + ' ("' + (s.getAttribute('data-label') || '') + '") overflows by ' + over + 'px');
      });
      if (bad.length) {
        console.warn('[lu-deck] ' + bad.length + ' slide(s) overflow the slide box and are being clipped:\n' + bad.join('\n') +
          '\nContent below the cut is invisible to students and cannot be scrolled to. Shorten the slide or split it in two.');
      }
    }, 1200);
  }

  /* ================================================================ BOOT */
  function boot() {
    Term.init();
    Reveal.init();
    Mcq.init();
    Walk.init();
    Sort.init();
    Blanks.init();
    Compare.init();
    Code.init();
    Query.init();
    Poll.init();
    Deck.init();
    Score.init();
    if (IS_PRESENTER) PV.build();
    registerSW();
    auditOverflow();
    window.LUDeck = { deck: Deck, go: function (n) { Deck.go(n - 1, 0); }, toast: toast, store: Store };
  }

  if (d.readyState === 'loading') d.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
