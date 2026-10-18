/* ==========================================================================
   sparql-lite.js, a teaching-sized SPARQL engine, in the browser, offline.
   --------------------------------------------------------------------------
   PURPOSE
     Lets a slide ship a real query sandbox with no server and no CDN, so a
     lecture works on GitHub Pages and from a USB stick alike.

   SUPPORTED
     Turtle input:  @prefix / PREFIX, IRIs, prefixed names, `a`, literals
                    (plain, "…"@lang, "…"^^xsd:type), integers, decimals,
                    booleans, the `;` and `,` shortcuts, # comments.
     Query:         PREFIX, SELECT (DISTINCT) with ?vars, * and
                    (COUNT(?v) AS ?n) / (COUNT(DISTINCT ?v) AS ?n),
                    WHERE with a basic graph pattern, OPTIONAL blocks,
                    FILTER, GROUP BY, ORDER BY (ASC/DESC), LIMIT, OFFSET.
     Filters:       && || ! , = != < <= > >= , regex(), contains(),
                    strstarts(), strends(), bound(), str(), lang(),
                    isIRI(), isLiteral(), numbers and string literals.

   NOT SUPPORTED (deliberately, say so in class rather than pretend)
     UNION, MINUS, property paths, subqueries, named graphs, BIND, VALUES,
     CONSTRUCT/ASK/DESCRIBE, federation, entailment of any kind.
     A query that uses them raises a readable error.
   ========================================================================== */
(function () {
  'use strict';

  var XSD = 'http://www.w3.org/2001/XMLSchema#';
  var RDF = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#';

  /* --------------------------------------------------------------- terms */
  function iri(v) { return { t: 'iri', v: v }; }
  function lit(v, dt, lang) { return { t: 'lit', v: v, dt: dt || null, lang: lang || null }; }
  function vr(n) { return { t: 'var', v: n }; }
  function key(term) {
    if (!term) return '';
    if (term.t === 'iri') return '<' + term.v + '>';
    return '"' + term.v + '"' + (term.dt ? '^^' + term.dt : '') + (term.lang ? '@' + term.lang : '');
  }
  function num(term) {
    if (!term || term.t !== 'lit') return null;
    if (term.dt && !/integer|decimal|double|float|int|long|short|byte/i.test(term.dt)) return null;
    var n = parseFloat(term.v);
    return isNaN(n) ? null : n;
  }

  /* ------------------------------------------------------------- lexing */
  var TOK = /("""[\s\S]*?"""|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(<[^>\s]*>)|(#[^\n]*)|(\?[A-Za-z_][\w]*)|([A-Za-z_][\w.\-]*:[\w.\-%]*|:[\w.\-%]*)|(@[A-Za-z][\w\-]*)|(\^\^)|([-+]?\d*\.\d+[eE][-+]?\d+|[-+]?\d+[eE][-+]?\d+|[-+]?\d*\.\d+|[-+]?\d+)|([(){}\[\];,.])|([A-Za-z_][\w]*)|(\S)/g;

  function lex(src) {
    var out = [], m;
    TOK.lastIndex = 0;
    while ((m = TOK.exec(src))) {
      if (m[3]) continue;                                   // comment
      if (m[1]) out.push({ k: 'str', v: unquote(m[1]) });
      else if (m[2]) out.push({ k: 'iri', v: m[2].slice(1, -1) });
      else if (m[4]) out.push({ k: 'var', v: m[4].slice(1) });
      else if (m[5]) out.push({ k: 'pname', v: m[5] });
      else if (m[6]) out.push({ k: 'lang', v: m[6].slice(1) });
      else if (m[7]) out.push({ k: '^^' });
      else if (m[8]) out.push({ k: 'num', v: m[8] });
      else if (m[9]) out.push({ k: m[9] });
      else if (m[10]) out.push({ k: 'word', v: m[10] });
      else out.push({ k: 'other', v: m[11] });
    }
    return out;
  }
  function unquote(s) {
    if (s.slice(0, 3) === '"""') s = s.slice(3, -3);
    else s = s.slice(1, -1);
    return s.replace(/\\n/g, '\n').replace(/\\t/g, '\t').replace(/\\"/g, '"').replace(/\\\\/g, '\\');
  }

  /* ----------------------------------------------------- turtle parsing */
  function parse(src) {
    var toks = lex(src || '');
    var prefixes = { rdf: RDF, rdfs: 'http://www.w3.org/2000/01/rdf-schema#', xsd: XSD, owl: 'http://www.w3.org/2002/07/owl#' };
    var triples = [];
    var i = 0;
    var bnode = 0;

    function expand(pn) {
      var at = pn.indexOf(':');
      var pre = pn.slice(0, at), loc = pn.slice(at + 1);
      if (!(pre in prefixes)) throw new Error('Unknown prefix "' + pre + ':" in the data.');
      return prefixes[pre] + loc;
    }
    function term(t) {
      if (!t) throw new Error('Unexpected end of data.');
      if (t.k === 'iri') return iri(t.v);
      if (t.k === 'pname') return iri(expand(t.v));
      if (t.k === 'num') return lit(t.v, XSD + (t.v.indexOf('.') >= 0 || /e/i.test(t.v) ? 'decimal' : 'integer'));
      if (t.k === 'word') {
        if (t.v === 'a') return iri(RDF + 'type');
        if (t.v === 'true' || t.v === 'false') return lit(t.v, XSD + 'boolean');
        throw new Error('Unexpected keyword "' + t.v + '" in the data.');
      }
      if (t.k === 'str') {
        var l = lit(t.v);
        if (toks[i] && toks[i].k === '^^') { i++; var dt = toks[i++]; l.dt = dt.k === 'iri' ? dt.v : expand(dt.v); }
        else if (toks[i] && toks[i].k === 'lang') { l.lang = toks[i++].v; }
        return l;
      }
      throw new Error('Cannot read "' + (t.v || t.k) + '" as a term.');
    }

    while (i < toks.length) {
      var t = toks[i];
      // @prefix p: <iri> .   /  PREFIX p: <iri>
      if ((t.k === 'lang' && t.v === 'prefix') || (t.k === 'word' && /^prefix$/i.test(t.v))) {
        i++;
        var pn = toks[i++], ir = toks[i++];
        prefixes[pn.v.slice(0, -1)] = ir.v;
        if (toks[i] && toks[i].k === '.') i++;
        continue;
      }
      if ((t.k === 'lang' && t.v === 'base') || (t.k === 'word' && /^base$/i.test(t.v))) { i += 2; if (toks[i] && toks[i].k === '.') i++; continue; }
      if (t.k === '.') { i++; continue; }

      var subj = term(toks[i++]);
      var guard = 0;
      while (i < toks.length && guard++ < 5000) {
        var pred = term(toks[i++]);
        while (i < toks.length) {
          var obj = term(toks[i++]);
          triples.push([subj, pred, obj]);
          if (toks[i] && toks[i].k === ',') { i++; continue; }
          break;
        }
        if (toks[i] && toks[i].k === ';') {
          i++;
          if (toks[i] && (toks[i].k === '.' || toks[i].k === undefined)) break;
          continue;
        }
        break;
      }
      if (toks[i] && toks[i].k === '.') i++;
    }

    return { triples: triples, prefixes: prefixes, shorten: shortener(prefixes) };
  }

  function shortener(prefixes) {
    var pairs = Object.keys(prefixes).map(function (p) { return [p, prefixes[p]]; })
      .sort(function (a, b) { return b[1].length - a[1].length; });
    return function (term) {
      if (!term) return '';
      if (term.t === 'lit') return term.v;
      for (var j = 0; j < pairs.length; j++) {
        if (term.v.indexOf(pairs[j][1]) === 0) return pairs[j][0] + ':' + term.v.slice(pairs[j][1].length);
      }
      return '<' + term.v + '>';
    };
  }

  /* ---------------------------------------------------- query structure */
  function stripBlock(body, kw) {
    // Pull `KW { ... }` blocks out of a WHERE body, brace-matched.
    var blocks = [], re = new RegExp('\\b' + kw + '\\s*\\{', 'gi'), m;
    while ((m = re.exec(body))) {
      var start = m.index, open = m.index + m[0].length - 1, depth = 0, j = open;
      for (; j < body.length; j++) {
        if (body[j] === '{') depth++;
        else if (body[j] === '}') { depth--; if (!depth) break; }
      }
      blocks.push(body.slice(open + 1, j));
      body = body.slice(0, start) + ' ' + body.slice(j + 1);
      re.lastIndex = 0;
    }
    return { body: body, blocks: blocks };
  }
  function stripCalls(body, kw) {
    var out = [], re = new RegExp('\\b' + kw + '\\s*\\(', 'gi'), m;
    while ((m = re.exec(body))) {
      var start = m.index, open = m.index + m[0].length - 1, depth = 0, j = open;
      for (; j < body.length; j++) {
        if (body[j] === '(') depth++;
        else if (body[j] === ')') { depth--; if (!depth) break; }
      }
      out.push(body.slice(open + 1, j));
      body = body.slice(0, start) + ' ' + body.slice(j + 1);
      re.lastIndex = 0;
    }
    return { body: body, exprs: out };
  }

  function parseBGP(text, prefixes) {
    var toks = lex(text);
    var i = 0, pats = [];
    function expand(pn) {
      var at = pn.indexOf(':');
      var pre = pn.slice(0, at), loc = pn.slice(at + 1);
      if (!(pre in prefixes)) throw new Error('Unknown prefix "' + pre + ':", add a PREFIX line.');
      return prefixes[pre] + loc;
    }
    function term(t) {
      if (!t) throw new Error('Unexpected end of the WHERE clause.');
      if (t.k === 'var') return vr(t.v);
      if (t.k === 'iri') return iri(t.v);
      if (t.k === 'pname') return iri(expand(t.v));
      if (t.k === 'num') return lit(t.v, XSD + (t.v.indexOf('.') >= 0 ? 'decimal' : 'integer'));
      if (t.k === 'str') {
        var l = lit(t.v);
        if (toks[i] && toks[i].k === '^^') { i++; var dt = toks[i++]; l.dt = dt.k === 'iri' ? dt.v : expand(dt.v); }
        else if (toks[i] && toks[i].k === 'lang') l.lang = toks[i++].v;
        return l;
      }
      if (t.k === 'word') {
        if (t.v === 'a') return iri(RDF + 'type');
        if (/^(union|minus|service|bind|values|graph)$/i.test(t.v)) {
          throw new Error(t.v.toUpperCase() + ' is not supported by sparql-lite. Use a real endpoint for that.');
        }
        throw new Error('Unexpected "' + t.v + '" in the WHERE clause.');
      }
      throw new Error('Cannot read "' + (t.v || t.k) + '".');
    }
    while (i < toks.length) {
      if (toks[i].k === '.' || toks[i].k === '{' || toks[i].k === '}') { i++; continue; }
      var s = term(toks[i++]);
      var guard = 0;
      while (i < toks.length && guard++ < 2000) {
        if (toks[i].k === '.') { i++; break; }
        var p = term(toks[i++]);
        while (i < toks.length) {
          var o = term(toks[i++]);
          pats.push([s, p, o]);
          if (toks[i] && toks[i].k === ',') { i++; continue; }
          break;
        }
        if (toks[i] && toks[i].k === ';') { i++; continue; }
        if (toks[i] && toks[i].k === '.') { i++; }
        break;
      }
    }
    return pats;
  }

  /* --------------------------------------------------- filter evaluator */
  function makeFilter(src) {
    var toks = lex(src.replace(/</g, ' < ').replace(/>/g, ' > ').replace(/ < = /g, ' <= ').replace(/ > = /g, ' >= '));
    // Re-lex operators that the crude split broke apart.
    var flat = [], i;
    for (i = 0; i < toks.length; i++) {
      var t = toks[i];
      if (t.k === 'other' && (t.v === '<' || t.v === '>' || t.v === '=' || t.v === '!' || t.v === '&' || t.v === '|')) {
        var nx = toks[i + 1];
        if (nx && nx.k === 'other') {
          var two = t.v + nx.v;
          if (two === '<=' || two === '>=' || two === '!=' || two === '&&' || two === '||' || two === '==') {
            flat.push({ k: 'op', v: two === '==' ? '=' : two }); i++; continue;
          }
        }
        flat.push({ k: 'op', v: t.v }); continue;
      }
      flat.push(t);
    }

    var p = 0;
    function peek() { return flat[p]; }
    function eat(k, v) {
      var t = flat[p];
      if (!t) return null;
      if (t.k === k && (v == null || (t.v || '').toLowerCase() === v)) { p++; return t; }
      return null;
    }
    /* Boolean coercion happens at the boolean operators and at the top level
       only, so a function argument such as bound(?cq) still receives the raw
       binding rather than a truth value. */
    function truthy(v) {
      if (v === true) return true;
      if (v === false || v == null) return false;
      if (typeof v === 'number') return v !== 0;
      if (typeof v === 'string') return v.length > 0;
      if (v.t === 'lit') return v.v !== 'false' && v.v !== '';
      return true;
    }
    function orExpr() {
      var l = andExpr();
      while (peek() && peek().k === 'op' && peek().v === '||') {
        p++;
        l = (function (a, b) { return function (row) { return truthy(a(row)) || truthy(b(row)); }; })(l, andExpr());
      }
      return l;
    }
    function andExpr() {
      var l = cmpExpr();
      while (peek() && peek().k === 'op' && peek().v === '&&') {
        p++;
        l = (function (a, b) { return function (row) { return truthy(a(row)) && truthy(b(row)); }; })(l, cmpExpr());
      }
      return l;
    }
    function cmpExpr() {
      if (peek() && peek().k === 'op' && peek().v === '!') { p++; var inner = cmpExpr(); return function (row) { return !truthy(inner(row)); }; }
      var l = valExpr();
      var t = peek();
      if (t && t.k === 'op' && ['=', '!=', '<', '<=', '>', '>='].indexOf(t.v) >= 0) {
        p++;
        var r = valExpr(), op = t.v;
        return function (row) {
          var a = l(row), b = r(row);
          var an = typeof a === 'number' ? a : num(a), bn = typeof b === 'number' ? b : num(b);
          if (an != null && bn != null) {
            switch (op) { case '=': return an === bn; case '!=': return an !== bn; case '<': return an < bn; case '<=': return an <= bn; case '>': return an > bn; case '>=': return an >= bn; }
          }
          var as = str(a), bs = str(b);
          switch (op) { case '=': return as === bs; case '!=': return as !== bs; case '<': return as < bs; case '<=': return as <= bs; case '>': return as > bs; case '>=': return as >= bs; }
        };
      }
      return l;
    }
    function str(x) {
      if (x == null) return '';
      if (typeof x === 'string' || typeof x === 'number') return String(x);
      if (x.t === 'iri') return x.v;
      return x.v;
    }
    function valExpr() {
      var t = flat[p];
      if (!t) throw new Error('Unfinished FILTER expression.');
      if (t.k === '(') { p++; var e = orExpr(); eat(')'); return e; }
      if (t.k === 'var') { p++; return function (row) { return row[t.v]; }; }
      if (t.k === 'str') { p++; return function () { return t.v; }; }
      if (t.k === 'num') { p++; var n = parseFloat(t.v); return function () { return n; }; }
      if (t.k === 'iri') { p++; return function () { return iri(t.v); }; }
      if (t.k === 'pname') { p++; return function () { return t.v; }; }
      if (t.k === 'word') {
        var fn = t.v.toLowerCase(); p++;
        if (fn === 'true') return function () { return true; };
        if (fn === 'false') return function () { return false; };
        if (!eat('(')) throw new Error('Unknown value "' + t.v + '" in FILTER.');
        var args = [];
        if (!eat(')')) {
          for (;;) { args.push(orExpr()); if (eat(',')) continue; eat(')'); break; }
        }
        return function (row) {
          var a = args.map(function (f) { return f(row); });
          switch (fn) {
            case 'bound': return a[0] !== undefined && a[0] !== null;
            case 'str': return str(a[0]);
            case 'lang': return (a[0] && a[0].lang) || '';
            case 'isiri': case 'isuri': return !!(a[0] && a[0].t === 'iri');
            case 'isliteral': return !!(a[0] && a[0].t === 'lit');
            case 'contains': return str(a[0]).indexOf(str(a[1])) >= 0;
            case 'strstarts': return str(a[0]).indexOf(str(a[1])) === 0;
            case 'strends': return str(a[0]).slice(-str(a[1]).length) === str(a[1]);
            case 'strlen': return str(a[0]).length;
            case 'ucase': return str(a[0]).toUpperCase();
            case 'lcase': return str(a[0]).toLowerCase();
            case 'regex': try { return new RegExp(str(a[1]), str(a[2] || '')).test(str(a[0])); } catch (e) { return false; }
            case 'abs': return Math.abs(parseFloat(str(a[0])));
            case 'round': return Math.round(parseFloat(str(a[0])));
            default: throw new Error('FILTER function ' + fn.toUpperCase() + '() is not supported by sparql-lite.');
          }
        };
      }
      throw new Error('Cannot read "' + (t.v || t.k) + '" in FILTER.');
    }
    var f = orExpr();
    return function (row) { try { return truthy(f(row)); } catch (e) { return false; } };
  }

  /* ---------------------------------------------------------- evaluation */
  function match(store, pat, rows) {
    var out = [];
    for (var r = 0; r < rows.length; r++) {
      var row = rows[r];
      for (var i = 0; i < store.triples.length; i++) {
        var tr = store.triples[i], bind = null, ok = true;
        for (var slot = 0; slot < 3; slot++) {
          var pt = pat[slot], val = tr[slot];
          if (pt.t === 'var') {
            var have = (bind && bind[pt.v] !== undefined) ? bind[pt.v] : row[pt.v];
            if (have !== undefined) { if (key(have) !== key(val)) { ok = false; break; } }
            else { bind = bind || {}; bind[pt.v] = val; }
          } else if (key(pt) !== key(val)) { ok = false; break; }
        }
        if (!ok) continue;
        if (!bind) out.push(row);
        else { var nr = Object.assign({}, row); for (var k in bind) nr[k] = bind[k]; out.push(nr); }
      }
    }
    return out;
  }

  function evalBGP(store, pats, rows) {
    // Cheap but effective: run the most selective pattern first.
    var order = pats.map(function (p, idx) {
      var bound = p.filter(function (t) { return t.t !== 'var'; }).length;
      return { p: p, idx: idx, bound: bound };
    }).sort(function (a, b) { return b.bound - a.bound || a.idx - b.idx; });
    var cur = rows;
    for (var i = 0; i < order.length; i++) {
      cur = match(store, order[i].p, cur);
      if (!cur.length) return [];
      if (cur.length > 50000) throw new Error('That pattern produced more than 50,000 intermediate rows. Add a more selective triple or a FILTER.');
    }
    return cur;
  }

  function query(store, qsrc) {
    var src = String(qsrc || '');
    if (/^\s*(construct|ask|describe)\b/i.test(src)) throw new Error('sparql-lite runs SELECT queries only.');

    // PREFIX declarations
    var prefixes = Object.assign({}, store.prefixes);
    src.replace(/\bPREFIX\s+([\w.\-]*):\s*<([^>]*)>/gi, function (_, p, u) { prefixes[p] = u; return ''; });
    var head = src.replace(/\bPREFIX\s+[\w.\-]*:\s*<[^>]*>/gi, ' ');

    var wm = /\bSELECT\b([\s\S]*?)\bWHERE\b\s*\{([\s\S]*)\}([\s\S]*)$/i.exec(head)
      || /\bSELECT\b([\s\S]*?)\{([\s\S]*)\}([\s\S]*)$/i.exec(head);
    if (!wm) throw new Error('Could not find SELECT … WHERE { … }.');

    var selRaw = wm[1].trim(), bodyRaw = wm[2], tail = wm[3] || '';

    var distinct = /^\s*distinct\b/i.test(selRaw);
    selRaw = selRaw.replace(/^\s*(distinct|reduced)\b/i, '').trim();

    // Projection: ?vars, *, and (COUNT(?v) AS ?n)
    var proj = [], aggs = [];
    if (selRaw === '*' || selRaw === '') proj = null;
    else {
      var re = /\(([^()]*\([^()]*\)[^()]*|[^()]*)\)|\?([A-Za-z_]\w*)/g, mm;
      while ((mm = re.exec(selRaw))) {
        if (mm[2]) proj.push(mm[2]);
        else {
          var am = /(count|sum|avg|min|max)\s*\(\s*(distinct\s+)?(\*|\?[A-Za-z_]\w*)\s*\)\s*as\s*\?([A-Za-z_]\w*)/i.exec(mm[1]);
          if (!am) throw new Error('Cannot read the SELECT expression "(' + mm[1] + ')".');
          aggs.push({ fn: am[1].toLowerCase(), distinct: !!am[2], on: am[3].replace('?', ''), as: am[4] });
          proj.push(am[4]);
        }
      }
    }

    // Pull OPTIONAL blocks and FILTERs out before parsing the BGP.
    var o = stripBlock(bodyRaw, 'OPTIONAL');
    var f = stripCalls(o.body, 'FILTER');
    if (/\bunion\b|\bminus\b|\bservice\b|\bbind\b|\bvalues\b/i.test(f.body)) {
      throw new Error('UNION, MINUS, BIND, VALUES and SERVICE are not supported by sparql-lite.');
    }

    var pats = parseBGP(f.body, prefixes);
    if (!pats.length && !o.blocks.length) throw new Error('The WHERE clause has no triple patterns.');

    var rows = evalBGP(store, pats, [{}]);

    // OPTIONAL = left join
    o.blocks.forEach(function (blk) {
      var of_ = stripCalls(blk, 'FILTER');
      var opats = parseBGP(of_.body, prefixes);
      var ofilters = of_.exprs.map(makeFilter);
      rows = rows.reduce(function (acc, row) {
        var got = evalBGP(store, opats, [row]).filter(function (r) { return ofilters.every(function (fn) { return fn(r); }); });
        return acc.concat(got.length ? got : [row]);
      }, []);
    });

    // FILTERs
    f.exprs.map(makeFilter).forEach(function (fn) { rows = rows.filter(fn); });

    // GROUP BY + aggregates
    var groupBy = [];
    var gm = /\bGROUP\s+BY\b([\s\S]*?)(?=\bORDER\b|\bLIMIT\b|\bOFFSET\b|\bHAVING\b|$)/i.exec(tail);
    if (gm) groupBy = (gm[1].match(/\?[A-Za-z_]\w*/g) || []).map(function (s) { return s.slice(1); });

    var vars = proj;
    if (aggs.length || groupBy.length) {
      var buckets = {}, order = [];
      rows.forEach(function (r) {
        var gk = groupBy.map(function (v) { return key(r[v]); }).join('\u0001');
        if (!buckets[gk]) { buckets[gk] = { row: r, members: [] }; order.push(gk); }
        buckets[gk].members.push(r);
      });
      rows = order.map(function (gk) {
        var b = buckets[gk], out = {};
        groupBy.forEach(function (v) { out[v] = b.row[v]; });
        aggs.forEach(function (a) {
          var vals = b.members.map(function (m) { return a.on === '*' ? 1 : m[a.on]; }).filter(function (x) { return x !== undefined; });
          if (a.distinct) {
            var seen = {}, ded = [];
            vals.forEach(function (v) { var k = key(v); if (!seen[k]) { seen[k] = 1; ded.push(v); } });
            vals = ded;
          }
          var nums = vals.map(function (v) { return typeof v === 'number' ? v : num(v); }).filter(function (n) { return n != null; });
          var res;
          if (a.fn === 'count') res = vals.length;
          else if (a.fn === 'sum') res = nums.reduce(function (x, y) { return x + y; }, 0);
          else if (a.fn === 'avg') res = nums.length ? nums.reduce(function (x, y) { return x + y; }, 0) / nums.length : 0;
          else if (a.fn === 'min') res = nums.length ? Math.min.apply(null, nums) : '';
          else res = nums.length ? Math.max.apply(null, nums) : '';
          out[a.as] = lit(String(a.fn === 'avg' ? Math.round(res * 1000) / 1000 : res), XSD + 'decimal');
        });
        return out;
      });
      if (!vars) vars = groupBy.concat(aggs.map(function (a) { return a.as; }));
    }

    if (!vars) {
      var seenV = {};
      vars = [];
      pats.forEach(function (p) { p.forEach(function (t) { if (t.t === 'var' && !seenV[t.v]) { seenV[t.v] = 1; vars.push(t.v); } }); });
      o.blocks.forEach(function (b) {
        (b.match(/\?[A-Za-z_]\w*/g) || []).forEach(function (s) { var v = s.slice(1); if (!seenV[v]) { seenV[v] = 1; vars.push(v); } });
      });
    }

    // ORDER BY
    var om = /\bORDER\s+BY\b([\s\S]*?)(?=\bLIMIT\b|\bOFFSET\b|$)/i.exec(tail);
    if (om) {
      var keys = [];
      om[1].replace(/(asc|desc)\s*\(\s*\?(\w+)\s*\)|\?(\w+)/gi, function (_, dir, v1, v2) {
        keys.push({ v: v1 || v2, desc: /desc/i.test(dir || '') });
        return '';
      });
      rows.sort(function (a, b) {
        for (var i = 0; i < keys.length; i++) {
          var k = keys[i], av = a[k.v], bv = b[k.v];
          var an = num(av), bn = num(bv), c;
          if (an != null && bn != null) c = an - bn;
          else c = String(av ? av.v : '').localeCompare(String(bv ? bv.v : ''));
          if (c) return k.desc ? -c : c;
        }
        return 0;
      });
    }

    // DISTINCT on the projection
    if (distinct) {
      var seenR = {}, ded = [];
      rows.forEach(function (r) {
        var k = vars.map(function (v) { return key(r[v]); }).join('\u0001');
        if (!seenR[k]) { seenR[k] = 1; ded.push(r); }
      });
      rows = ded;
    }

    var off = /\bOFFSET\s+(\d+)/i.exec(tail);
    var lim = /\bLIMIT\s+(\d+)/i.exec(tail);
    if (off) rows = rows.slice(parseInt(off[1], 10));
    if (lim) rows = rows.slice(0, parseInt(lim[1], 10));

    var shorten = store.shorten || shortener(prefixes);
    return {
      vars: vars,
      rows: rows.map(function (r) {
        var out = {};
        vars.forEach(function (v) { out[v] = r[v] === undefined ? null : shorten(r[v]); });
        return out;
      })
    };
  }

  window.LUSparql = { parse: parse, query: query };
})();
