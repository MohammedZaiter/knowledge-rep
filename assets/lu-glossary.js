/* lu-glossary.js v1.0 · automatic glossary links
 *
 * Reads window.LU_GLOSSARY (assets/glossary.js, generated from GLOSSARY.md by
 * scripts/build-glossary.py) and turns the first use of each term on a slide
 * into the standard .lu-term popover button. lu-deck.js then wires the
 * buttons exactly like hand-written ones, including study mode (S).
 *
 * Load order matters: both glossary scripts must come BEFORE lu-deck.js
 * (all three with defer), because lu-deck wires .lu-term buttons at boot.
 *
 * A slide can opt out with data-glossary="off" on the slide or on any element.
 * The deck's session number is the first number in <body data-session> ("Session 3 of 8") or in the
 * file name (kr-session-03.html -> 3); terms marked once per deck are only
 * linked from their own session onwards.
 */
(function () {
  'use strict';
  var G = window.LU_GLOSSARY;
  if (!G || !G.length || !document.querySelector('section.slide')) return;

  var SKIP = [
    'h1', 'h2', 'header', 'footer', 'code', 'pre', 'kbd', 'button', 'a', 'svg',
    'template', 'script', 'style', 'label', 'input', 'textarea', 'select', 'th',
    'dt', 'figcaption', '[data-glossary="off"]', '.lu-term', '.lu-pop',
    '[class^="lu-display"]', '[class*=" lu-display"]', '.lu-eyebrow', '.lu-code',
    '.lu-mono', '.lu-query', '.lu-mcq__opt', '.lu-sort', '.lu-walk__cap',
    '.lu-walk__bar', '.lu-card__label', '.lu-callout__label', '.lu-tag',
    '.lu-pipeline', '.lu-flow', '.lu-node', '.lu-edge-label', '.lu-layers__name',
    '.lu-lockup', '.lu-blank', '.lu-blanks', '.lu-poll', '.deck__chrome',
    '.lu-h1', '.lu-h2'
  ].join(',');

  var m = /(\d+)/.exec(document.body.getAttribute('data-session') || '') ||
          /session-0*(\d+)/.exec(location.pathname);
  var session = m ? parseInt(m[1], 10) : 99;

  function esc(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

  /* One pattern per visible form: plural endings allowed, word separators
   * may be a space or a hyphen, common words accept either case on the first
   * letter of each word; acronyms and names match exactly. */
  function pattern(form) {
    var words = form.text.split(/\s+/).map(function (w, i, all) {
      var last = i === all.length - 1;
      var body = esc(w);
      if (!form.fixed && /^[a-z]/i.test(w)) {
        body = '[' + w[0].toUpperCase() + w[0].toLowerCase() + ']' + esc(w.slice(1));
      }
      if (last && /[a-z]$/i.test(w)) {
        if (/y$/.test(w) && !form.fixed) body = body.slice(0, -1) + '(?:y|ies)';
        else body += '(?:e?s)?';
      }
      return body;
    });
    return words.join('[\\s\\u00A0-]+');
  }

  var entries = [];
  G.forEach(function (e, i) {
    if (e.link === false || !e.forms) return;
    if (e.scope === 'deck' && e.session > session) return;
    e.forms.forEach(function (f) { entries.push({ id: i, e: e, src: pattern(f), len: f.text.length }); });
  });
  if (!entries.length) return;
  entries.sort(function (a, b) { return b.len - a.len; });   // longest match first

  var edge = '(?<![\\w:/@#-])';
  var tail = '(?![\\w:/@-])';
  var re;
  try {
    re = new RegExp(edge + '(' + entries.map(function (x) { return '(' + x.src + ')'; }).join('|') + ')' + tail, 'g');
  } catch (err) { return; }                                   // very old browser: leave slides as they are

  function which(match) {
    for (var k = 0; k < entries.length; k++) {
      if (match[k + 2] !== undefined) return entries[k];
    }
    return null;
  }

  function skipped(node) {
    var p = node.parentElement;
    return !p || !!p.closest(SKIP);
  }

  function button(entry, text) {
    var b = document.createElement('button');
    b.className = 'lu-term lu-term--auto';
    b.type = 'button';
    b.setAttribute('data-term', entry.e.term);
    b.setAttribute('data-kind', 'Glossary · Session ' + entry.e.session);
    var w = document.createElement('span');
    w.className = 'lu-term-word';
    w.textContent = text;
    var t = document.createElement('template');
    t.innerHTML = entry.e.def;
    b.appendChild(w);
    b.appendChild(t);
    return b;
  }

  var deckUsed = {};

  function norm(s) { return (s || '').toLowerCase().replace(/[\s\u00A0-]+/g, ' ').trim(); }

  document.querySelectorAll('section.slide').forEach(function (slide) {
    if (slide.getAttribute('data-glossary') === 'off') return;
    var used = {};

    /* Terms the author already explains on this slide count as used. */
    var authored = {};
    slide.querySelectorAll('.lu-term[data-term], .lu-term-word, dt').forEach(function (el) {
      authored[norm(el.getAttribute('data-term') || el.textContent)] = true;
    });
    G.forEach(function (e, i) {
      if (authored[norm(e.term)]) used[i] = true;
      (e.forms || []).forEach(function (f) { if (authored[norm(f.text)]) used[i] = true; });
    });

    /* Visible text first, then text inside closed reveals and answers, so the
     * link lands on the first words a student actually sees. */
    [false, true].forEach(function (hiddenPass) {
      var walker = document.createTreeWalker(slide, NodeFilter.SHOW_TEXT, null);
      var nodes = [], n;
      while ((n = walker.nextNode())) {
        if (!n.nodeValue.trim() || skipped(n)) continue;
        var inHidden = !!n.parentElement.closest('[hidden]');
        if (inHidden === hiddenPass) nodes.push(n);
      }
      nodes.forEach(function (node) {
        var text = node.nodeValue, out = null, last = 0, hit;
        re.lastIndex = 0;
        while ((hit = re.exec(text))) {
          var entry = which(hit);
          if (!entry) continue;
          var key = entry.id;
          if (used[key] || (entry.e.scope === 'deck' && deckUsed[key])) continue;
          used[key] = true;
          if (entry.e.scope === 'deck') deckUsed[key] = true;
          out = out || document.createDocumentFragment();
          out.appendChild(document.createTextNode(text.slice(last, hit.index)));
          out.appendChild(button(entry, hit[0]));
          last = hit.index + hit[0].length;
        }
        if (!out) return;
        out.appendChild(document.createTextNode(text.slice(last)));
        node.parentNode.replaceChild(out, node);
      });
    });
  });
})();
