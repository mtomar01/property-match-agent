// Collects Spitogatos result cards and listing pages in the browser, following docs/collecting.md (D68, D69).
// Run it in a Spitogatos tab: it installs window.PM. The script holds no data; what it collects is saved
// with a Blob download (one cards_ and one pages_ file per area) and moved into data/private/collect/.
//
//   PM.area({slug: 'aigaleo', path: '/pwliseis-katoikies/aigaleo', seen: '2026-10-23', exclude: []})
//   PM.run({resultPages: 7, listings: 200, pages: 200})   // returns at once; the run goes on in the tab
//   await PM.wait(45)                                      // counts and problems only, never page text
//   PM.save()                                              // the two files for this area, into ~/Downloads
//   PM.only([...ids]); PM.run({resultPages: 0, listings: 0, pages: N}); PM.save({pagesOnly: true})   // refetch known pages
//
// Pages are fetched, not opened: the six sections are in the server's HTML. Each one is shown in a hidden
// same-origin frame without its scripts or images, so innerText lays out with the site's own inline CSS
// exactly as on the live page (the parsers read it line by line).
(() => {
  const BASE = 'https://www.spitogatos.gr';
  const SECTIONS = ['Περιγραφή', 'Χαρακτηριστικά', 'Εσωτερικό', 'Εξωτερικά χαρακτηριστικά', 'Κατασκευή', 'Κατάλληλο για'];
  const FEATURE_LISTS = new Set(SECTIONS.slice(2));
  const TITLE = /^.+?,\s*[\d.,]+\s*τ\.μ\.$/;
  const PRICE = /^€\s*[\d.]+$/;

  // Contact details are replaced before anything is kept: the same three rules as core/pii.py.
  const W = '[\\p{L}\\p{N}_]';
  const EMAIL = /[\p{L}\p{N}_.+-]+@[\p{L}\p{N}_-]+(?:\.[\p{L}\p{N}_-]+)+/gu;
  const PHONE = /(?:\+|00)?(?:\d[\s.\/-]?){8,}\d/g;
  const PHONE_LABEL = new RegExp(`(?<!${W})(τηλ${W}*|tel${W}*|phone|κιν\\.?)\\s*[:.]?\\s*(?:[\\p{L}_]+\\s*){0,2}[:.]?\\s*(?:\\+|00)?\\d[\\d\\s.\\/-]{4,}`, 'giu');
  const digits = s => (s.match(/\d/g) || []).length;
  const scrub = t => (t == null ? t : t
    .replace(EMAIL, '[removed]')
    .replace(PHONE_LABEL, (m, label) => `${label} [removed]`)
    .replace(PHONE, m => (digits(m) >= 9 ? '[removed]' : m)));
  const leftover = t => !!t && (new RegExp(EMAIL.source, 'u').test(t) || [...t.matchAll(PHONE)].some(m => digits(m[0]) >= 9));

  class Stop extends Error {}
  const S = {area: null, running: false, stopped: null, requests: 0, lastAt: 0, frame: null};
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // One request at a time, 4 to 7 seconds (random) after the previous response.
  async function pace() {
    const wait = S.lastAt + 4000 + Math.random() * 3000 - Date.now();
    if (wait > 0) await sleep(wait);
  }

  async function get(url) {
    await pace();
    let res, html;
    try {
      res = await fetch(url, {credentials: 'same-origin'});
      html = await res.text();
    } finally {
      S.requests++;
      S.lastAt = Date.now();
    }
    if (res.status === 403 || res.status === 429) throw new Stop(`HTTP ${res.status} on ${url}`);
    const head = new DOMParser().parseFromString(html.slice(0, 30000), 'text/html');
    const words = `${head.title} ${(head.body?.textContent || '').slice(0, 2000)}`;
    if (/captcha|access denied|attention required|just a moment|are you a robot|ρομπότ/i.test(words)) throw new Stop(`a captcha or access-denied page on ${url}`);
    if (res.status === 200 && html.length < 30000 && !/property__title|ordered-element/.test(html)) {
      throw new Stop(`a ${html.length}-byte page with no listing content on ${url} (looks like a bot check)`);
    }
    return {res, html};
  }

  async function render(html) {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    doc.querySelectorAll('script, noscript, iframe, video, audio, object, embed, link[rel=preload], link[rel=prefetch], link[rel=modulepreload]')
      .forEach(e => e.remove());
    doc.querySelectorAll('img, source').forEach(e => {
      for (const a of ['src', 'srcset', 'data-src', 'data-srcset']) {
        if (e.hasAttribute(a)) { e.setAttribute(`data-pm-${a}`, e.getAttribute(a)); e.removeAttribute(a); }
      }
    });
    doc.querySelectorAll('[style*="url("]').forEach(e => { e.style.backgroundImage = 'none'; });
    const base = doc.createElement('base');
    base.href = `${BASE}/`;
    doc.head.prepend(base);
    if (!S.frame || !S.frame.isConnected) {
      S.frame = document.createElement('iframe');
      S.frame.setAttribute('aria-hidden', 'true');
      S.frame.tabIndex = -1;
      S.frame.style.cssText = 'position:fixed;left:-20000px;top:0;width:1280px;height:1000px;border:0';
      document.body.append(S.frame);
    }
    await new Promise(resolve => { S.frame.onload = resolve; S.frame.srcdoc = `<!doctype html>${doc.documentElement.outerHTML}`; });
    return S.frame.contentDocument;
  }

  // Step 1: one record per result card; promoted mini cards (no title, sub-area or price) are skipped.
  function cardsOf(doc, slug, seen) {
    const cards = [];
    let skipped = 0;
    for (const art of doc.querySelectorAll('article.ordered-element')) {
      art.querySelectorAll('.tile__logo').forEach(e => e.remove()); // the agency's logo and name stay out
      const href = art.querySelector('a[href*="/aggelia/"]')?.getAttribute('href') || '';
      const id = (href.match(/\/aggelia\/(\d+)/) || [])[1];
      const text = art.innerText;
      const lines = text.split('\n').map(s => s.trim());
      if (!id || !lines.some(l => TITLE.test(l)) || !lines.some(l => /\(.+\)$/.test(l)) || !lines.some(l => PRICE.test(l))) {
        skipped++;
        continue;
      }
      const src = art.querySelector('img')?.getAttribute('data-pm-src') || '';
      cards.push({source: 'spitogatos', source_id: id, url: `${BASE}/aggelia/${id}`, area_query: slug,
                  card_text: scrub(text), photo_url: src.startsWith('https://') ? src : null, seen});
    }
    return {cards, skipped};
  }

  // Step 2: one record per listing page: the six sections, ticked features in sections, crossed ones apart,
  // plus the title, the area line under it and the bedroom and bathroom badges (not the floor badge or street).
  function pageOf(doc, id, seen, slug) {
    const h1 = doc.querySelector('h1.property__title');
    if (!h1) return null;
    const sections = {};
    const crossed = {};
    for (const h of doc.querySelectorAll('h3.property__subheading')) {
      const name = h.textContent.trim();
      const body = h.nextElementSibling;
      if (!SECTIONS.includes(name) || !body) continue;
      if (FEATURE_LISTS.has(name)) {
        const ticked = [];
        const out = [];
        for (const li of body.querySelectorAll('li')) {
          const use = li.querySelector('use');
          const icon = (use?.getAttribute('href') || use?.getAttribute('xlink:href') || '').split('#')[1];
          const label = li.innerText.trim();
          if (icon === 'i-correct') ticked.push(label);
          else if (icon === 'i-negative') out.push(label.replace(/\s+/g, ' ').replace(/\s*\(.*\)$/, ''));
        }
        sections[name] = scrub(ticked.join('\n'));
        if (out.length) crossed[name] = out.map(scrub);
      } else {
        if (name === 'Περιγραφή') { // "read more": the whole text is in the page, only clamped
          body.querySelectorAll('.property__description__more').forEach(e => e.remove());
          body.querySelectorAll('.sliced').forEach(e => e.classList.remove('sliced'));
        }
        sections[name] = scrub(body.innerText.trim());
      }
    }
    if (!sections['Χαρακτηριστικά']) return null;
    const gallery = doc.querySelector('.property__gallery, [class*="gallery"]') || doc;
    const photo = [...gallery.querySelectorAll('img')].map(i => i.getAttribute('data-pm-src') || i.getAttribute('data-pm-data-src') || '')
      .find(s => /^https:\/\/\S+\.(jpe?g|png|webp)(\?|$)/i.test(s)) || null;
    const location = doc.querySelector('.property__address')?.innerText.trim() || null;
    const rooms = [...doc.querySelectorAll('ul.property__info > li')]
      .filter(li => /#i-icon-(bedroom|bathroom)$/.test(li.querySelector('use')?.getAttribute('href') || li.querySelector('use')?.getAttribute('xlink:href') || ''))
      .map(li => li.innerText.replace(/\s+/g, ' ').trim());
    return {source_id: id, url: `${BASE}/aggelia/${id}`, seen, photo_url: photo, sections, crossed,
            title: scrub(h1.innerText.trim()), location: scrub(location), rooms: rooms.length ? scrub(rooms.join('\n')) : null, area_query: slug};
  }

  function failed(why) {
    const A = S.area;
    A.failures.push(why);
    A.streak++;
    if (A.streak >= 3) throw new Stop(`three failed pages in a row (last: ${why})`);
  }

  async function run(limits) {
    const A = S.area;
    S.running = true;
    S.stopped = null;
    try {
      while (A.resultPagesDone < limits.resultPages && A.cards.length < limits.listings && !A.resultsEnded) {
        const n = A.resultPagesDone + 1;
        const url = `${BASE}${A.path}${n > 1 ? `/selida_${n}` : ''}`;
        A.resultPagesDone++;
        let got;
        try { got = await get(url); } catch (e) { if (e instanceof Stop) throw e; failed(`results page ${n}: ${e.message}`); continue; }
        if (got.res.status !== 200 || !new URL(got.res.url).pathname.startsWith(A.path)) { failed(`results page ${n}: HTTP ${got.res.status} at ${new URL(got.res.url).pathname}`); continue; }
        const {cards, skipped} = cardsOf(await render(got.html), A.slug, A.seen);
        A.skipped += skipped;
        if (!cards.length) { A.resultsEnded = true; failed(`results page ${n}: no cards`); continue; }
        A.streak = 0;
        for (const card of cards) {
          if (A.cards.length >= limits.listings) break;
          if (A.ids.has(card.source_id) || A.exclude.has(card.source_id)) { A.dupes++; continue; }
          A.ids.add(card.source_id);
          A.cards.push(card);
        }
      }
      while (A.pageIndex < Math.min(A.cards.length, limits.pages)) {
        const card = A.cards[A.pageIndex];
        A.pageIndex++;
        let got;
        try { got = await get(card.url); } catch (e) { if (e instanceof Stop) throw e; failed(`listing ${card.source_id}: ${e.message}`); continue; }
        const record = got.res.status === 200 ? pageOf(await render(got.html), card.source_id, A.seen, A.slug) : null;
        if (!record) { failed(`listing ${card.source_id}: ${got.res.status === 200 ? 'no title or details' : `HTTP ${got.res.status}`}`); continue; }
        A.streak = 0;
        A.pages.push(record);
      }
    } catch (e) {
      S.stopped = e instanceof Stop ? e.message : `script error: ${e.message}`;
    } finally {
      S.running = false;
      A.endedAt = new Date().toISOString();
    }
  }

  function status() {
    const A = S.area;
    if (!A) return {area: null};
    const texts = [...A.cards.map(c => c.card_text),
                   ...A.pages.flatMap(p => [...Object.values(p.sections), ...Object.values(p.crossed).flat(), p.title, p.location, p.rooms])];
    return {
      area: A.slug, running: S.running, stopped: S.stopped, requests: S.requests,
      minutes: Math.round((Date.now() - A.startedMs) / 6000) / 10,
      resultPages: A.resultPagesDone, cards: A.cards.length, skippedMini: A.skipped, dupes: A.dupes,
      pagesTried: A.pageIndex, pages: A.pages.length, failures: A.failures.length, lastFailures: A.failures.slice(-5),
      cardPhotos: A.cards.filter(c => c.photo_url).length, pagePhotos: A.pages.filter(p => p.photo_url).length,
      contactLeftovers: texts.filter(leftover).length,
    };
  }

  // JSON leaves U+0085, U+2028 and U+2029 raw inside strings, but Python's splitlines() breaks lines on them.
  const line = r => JSON.stringify(r).replace(/[\u0085\u2028\u2029]/g, c => `\\u${c.charCodeAt(0).toString(16).padStart(4, '0')}`);

  function download(name, rows) {
    const blob = new Blob([rows.map(line).join('\n') + (rows.length ? '\n' : '')], {type: 'application/x-ndjson'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 60000);
  }

  window.PM = {
    area({slug, path, seen, exclude = []}) {
      S.area = {slug, path, seen, exclude: new Set(exclude.map(String)), ids: new Set(), cards: [], pages: [], failures: [],
                resultPagesDone: 0, resultsEnded: false, pageIndex: 0, skipped: 0, dupes: 0, streak: 0,
                startedAt: new Date().toISOString(), startedMs: Date.now(), endedAt: null};
      S.stopped = null;
      return status();
    },
    run(limits) {
      if (S.running) return {error: 'already running'};
      run(limits);
      return status();
    },
    status,
    // A refetch of known listings (D70): queue these ids as the area's listings, then PM.run({resultPages: 0, listings: 0,
    // pages: ids.length}) reads only their pages, and PM.save({pagesOnly: true}) writes only the pages file.
    only(ids) {
      const A = S.area;
      for (const raw of ids) {
        const id = String(raw);
        if (A.ids.has(id)) continue;
        A.ids.add(id);
        A.cards.push({source: 'spitogatos', source_id: id, url: `${BASE}/aggelia/${id}`, area_query: A.slug, card_text: '', photo_url: null, seen: A.seen, refetch: true});
      }
      return status();
    },
    async wait(seconds = 45) {
      const until = Date.now() + seconds * 1000;
      while (S.running && Date.now() < until) await sleep(1000);
      return status();
    },
    save({pagesOnly = false} = {}) {
      const A = S.area;
      if (status().contactLeftovers) return {error: 'contact details left after the scrub; nothing saved'};
      if (!pagesOnly) download(`cards_${A.slug}_${A.seen}.jsonl`, A.cards);
      download(`pages_${A.slug}_${A.seen}.jsonl`, A.pages);
      return {saved: [`cards_${A.slug}_${A.seen}.jsonl`, `pages_${A.slug}_${A.seen}.jsonl`], cards: A.cards.length, pages: A.pages.length,
              startedAt: A.startedAt, endedAt: A.endedAt, failures: A.failures};
    },
    // Checks for the first page only: the same card read live and from fetched HTML, and a page's shape.
    _test: {cardsOf, pageOf, render, scrub},
  };
  return 'PM installed';
})();
