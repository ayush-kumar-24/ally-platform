/**
 * One component for all three KNOWLEDGE libraries -- read, watch, learn.
 *
 * WHY ONE COMPONENT AND NOT THREE PAGES. The three differ only in their words
 * and their list; the layout, the empty state and the card are identical. Three
 * copies would drift the moment one of them got a fix, and the section that did
 * not get it would be the one nobody noticed.
 *
 * The section is chosen by the route (`/app/knowledge/:section`), and an
 * unknown one renders "not found" rather than an empty page pretending to be a
 * real section.
 *
 * ONE SECTION HAS TABS. "Things to watch" splits into podcasts, series and
 * films, because those are three different sizes of commitment and one mixed
 * list is unreadable. The tab lives in the URL query (`?tab=series`) rather
 * than component state, so a founder can be sent straight to one and the back
 * button behaves.
 *
 * TWO KINDS OF CARD, both links. A podcast episode links to the episode. A film
 * or a book has no durable link we could give -- streaming availability differs
 * by country and by month, and a bookshop link would be us picking a shop -- so
 * it links to a search for itself, which is what a founder would type anyway,
 * and which lands on the panel with the cover, the editions and where to get it.
 *
 * NO LOADING STATE, deliberately. This is static reference content imported at
 * build time -- there is nothing to fetch, and a spinner over data already in
 * the bundle is a lie about what is happening.
 */

import { useMemo, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { KNOWLEDGE_SECTIONS } from '../data/knowledge';
import COVERS from '../data/covers.json';

function ResourceCard({ item }) {
  /* An entry with a link opens it; one without is still worth showing. Not
     every recommendation is a URL -- a book has no canonical page we would want
     to send a founder to, and inventing an affiliate link would be worse. */
  const Wrapper = item.url ? 'a' : 'article';
  const linkProps = item.url
    ? { href: item.url, target: '_blank', rel: 'noopener noreferrer' }
    : {};

  return (
    <Wrapper className={`fw-card${item.url ? ' fw-card-link' : ''}`} {...linkProps}>
      <h3>{item.title}</h3>
      {item.why && <p className="fw-tagline">{item.why}</p>}

      {(item.by || item.when || item.length || item.forWhen) && (
        <div className="fw-meta">
          {item.by && (
            <div className="fw-meta-row">
              <span className="fw-meta-label">From</span>
              <span className="fw-meta-value">{item.by}</span>
            </div>
          )}
          {item.when && (
            <div className="fw-meta-row">
              <span className="fw-meta-label">Published</span>
              <span className="fw-meta-value">{item.when}</span>
            </div>
          )}
          {item.length && (
            <div className="fw-meta-row">
              <span className="fw-meta-label">Length</span>
              <span className="fw-meta-value">{item.length}</span>
            </div>
          )}
          {item.forWhen && (
            <div className="fw-meta-row">
              <span className="fw-meta-label">For when</span>
              <span className="fw-meta-value">{item.forWhen}</span>
            </div>
          )}
        </div>
      )}

      {/* Said plainly rather than hidden. Two episodes could not be pinned to a
          durable URL, and a founder who lands on a show index deserves to know
          that was deliberate rather than think the link is broken. */}
      {item.note && <p className="fw-card-note">{item.note}</p>}
    </Wrapper>
  );
}

/**
 * The search a founder would have typed anyway.
 *
 * Title alone is not enough for half of these -- "Air", "Joy", "Chef" and
 * "Corporate" are all ordinary words, and a bare search lands nowhere useful.
 * The year and the kind are what make the search resolve to the right thing.
 */
function searchUrl(item) {
  const tag = (item.tag || '').toLowerCase();
  /* A book is identified by its author, a film by its year. Both need the word
     for what they are: "Drive" and "Range" and "Flow" and "Air" and "Joy" are
     all ordinary words, and a bare title search lands nowhere useful. */
  const q = item.by
    ? [item.title, item.by, 'book']
    : [item.title, item.year, tag.includes('series') ? 'series'
      : tag.includes('documentary') ? 'documentary' : 'film'];
  return `https://www.google.com/search?q=${encodeURIComponent(q.filter(Boolean).join(' '))}`;
}

/**
 * A film, a series or a book: the title at rest, the detail on hover, the
 * search on click.
 *
 * THE WHOLE TILE IS THE LINK, panel included. The panel takes pointer events
 * so the cursor can cross it without the tile losing hover and flickering,
 * which means a click lands on the panel rather than the face -- so the anchor
 * has to wrap both rather than sit inside one of them.
 *
 * The panel is absolutely positioned over the tile and allowed to overhang
 * downwards. Growing the tile in place would reflow every card in the row on a
 * mouse-over, which looks broken even when it isn't.
 */
function TitleTile({ item }) {
  /* Built by joining rather than hard-coded, because the same tile carries a
     film ("2016 · Global film") and a book ("Carol Dweck · Indian"). */
  const meta = (
    <span className="wt-sub">
      {[item.year, item.by, item.tag].filter(Boolean).join(' · ')}
    </span>
  );

  /* The cover, if we have one for this id. See data/covers.json and the
     script that fills it.

     HOT-LINKED, NOT HOSTED. Cover art is copyrighted; Open Library publishes
     these for third parties to display, which is what makes pointing at their
     CDN the ordinary posture and copying 128 covers into our own bucket a
     different one. This file already refuses to reproduce anything from
     INSIDE the books for the same family of reasons.

     ANY FAILURE FALLS BACK TO THE TILE AS IT IS TODAY. Coverage will never be
     complete -- several of these are Indian editions nobody has scanned -- so
     a missing entry renders nothing at all, and an entry whose image 404s or
     is blocked hides itself onError. A broken-image glyph in a reading list
     looks like a bug; no picture just looks like a card. */
  const cover = COVERS[item.id];

  return (
    <a
      className="wt-tile"
      href={searchUrl(item)}
      target="_blank"
      rel="noopener noreferrer"
    >
      <span className="wt-face">
        {item.pick && <span className="wt-pick">Start here</span>}
        <span className="wt-name">{item.title}</span>
        {meta}
      </span>

      <span className="wt-pop">
        {/* Title and cover together on one row: a portrait cover above a short
            panel would push "Look it up" off the bottom on the tiles that
            carry `care` as well. Width and height are fixed so the panel does
            not jump when the image lands. */}
        <span className={`wt-pop-head${cover ? ' has-cover' : ''}`}>
          {cover && (
            <img
              className="wt-cover"
              src={cover}
              alt=""
              width="56"
              height="84"
              loading="lazy"
              referrerPolicy="no-referrer"
              onError={(e) => { e.currentTarget.style.display = 'none'; }}
            />
          )}
          <span className="wt-pop-title">
            <span className="wt-name">{item.title}</span>
            {meta}
          </span>
        </span>

        {item.why && <span className="wt-why">{item.why}</span>}

        {item.forWhen && (
          <span className="wt-line">
            <span className="wt-line-label">
              {item.by ? 'Read it when' : 'Watch it when'}
            </span>
            {item.forWhen}
          </span>
        )}

        {item.ask && (
          <span className="wt-line">
            <span className="wt-line-label">Ask yourself after</span>
            {item.ask}
          </span>
        )}

        {/* Shown, not filed away. The films most likely to be misread are the
            ones most likely to be watched, so the warning travels with the
            title rather than living in a document nobody opens. */}
        {item.care && <span className="wt-care">{item.care}</span>}

        <span className="wt-more">Look it up ›</span>
      </span>
    </a>
  );
}

/**
 * The glossary: a searchable list, not a grid of tiles.
 *
 * WHY THIS IS A DIFFERENT SHAPE FROM THE OTHER SECTIONS. A film or a book is a
 * title you leave the page for; a definition is the content itself, and there
 * is nowhere better to send anyone. Tiles would hide the only thing of value
 * behind a hover, and 180-odd of them would be unreadable either way.
 *
 * SEARCH IS THE PRIMARY WAY IN, because that is how a glossary gets used --
 * somebody hears "liquidation preference" in a meeting and wants it now. It
 * matches the term, the meaning and the mistake, so "who gets paid first" finds
 * the entry even though those words are not in its name.
 *
 * Each term shows what it MEANS first, then what it is USED FOR. The source
 * calls the meaning column the one that matters most, so the card leads with
 * it; the situation is the supporting line rather than the headline.
 */
function Glossary({ sections }) {
  const [q, setQ] = useState('');
  const query = q.trim().toLowerCase();

  const total = useMemo(
    () => sections.reduce((n, s) => n + s.terms.length, 0),
    [sections],
  );

  const shown = useMemo(() => {
    if (!query) return sections;
    const hit = (t) => `${t.term} ${t.full || ''} ${t.usedFor || ''} ${t.means}`
      .toLowerCase().includes(query);
    return sections
      .map((s) => ({ ...s, terms: s.terms.filter(hit) }))
      .filter((s) => s.terms.length > 0);
  }, [sections, query]);

  const found = shown.reduce((n, s) => n + s.terms.length, 0);

  return (
    <div className="gl">
      <div className="gl-bar">
        <input
          type="search"
          className="gl-search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search — try churn, ESOP, runway, GST"
          aria-label="Search the glossary"
        />
        <span className="gl-count" aria-live="polite">
          {query ? `${found} of ${total}` : `${total} terms`}
        </span>
      </div>

      {/* Jump links while browsing. They would be noise during a search, where
          the filtered list is already short. */}
      {!query && (
        <nav className="gl-jump" aria-label="Glossary sections">
          {sections.map((s) => (
            <a key={s.slug} className="gl-chip" href={`#gl-${s.slug}`}>
              {s.title}
              <span className="gl-chip-n">{s.terms.length}</span>
            </a>
          ))}
        </nav>
      )}

      {found === 0 && (
        <p className="fw-empty">
          Nothing matches “{q}”. It may simply not be in here yet — the glossary
          covers the vocabulary founders are expected to know, not everything.
        </p>
      )}

      {shown.map((s) => (
        /* Each section is its own panel with a numbered header, because as one
           continuous run of 182 rows the sections were invisible and the whole
           thing read as an undifferentiated wall.

           The number comes from the full list, not from the filtered one. A
           search for "esop" returns sections 5 and 8; numbering them 1 and 2
           because they happen to be the only two showing would make the number
           mean nothing. */
        <section className="gl-section" key={s.slug} id={`gl-${s.slug}`}>
          <header className="gl-head">
            <span className="gl-num">
              {sections.findIndex((x) => x.slug === s.slug) + 1}
            </span>
            <div className="gl-head-text">
              <h2 className="gl-h">{s.title}</h2>
              {s.blurb && <p className="gl-blurb">{s.blurb}</p>}
            </div>
            <span className="gl-h-n">{s.terms.length}</span>
          </header>

          {/* Shown, not filed. Several of these facts have already moved once
              inside a year, and a founder reading a stale rate here would be
              relying on us for it. */}
          {s.note && <p className="gl-note">{s.note}</p>}

          {/* The document's own four columns, kept in its order and with its
              headings. A founder who has seen the Word version should not have
              to work out that this is the same thing.

              Horizontally scrollable on narrow screens rather than reflowed:
              four columns of prose collapsed into a phone width stops being a
              table and stops being comparable, which is the whole point of a
              table. */}
          <div className="gl-tablewrap">
            <table className="gl-table">
              <thead>
                <tr>
                  <th className="gl-c-term">Term</th>
                  <th className="gl-c-full">Full Form</th>
                  <th className="gl-c-used">What It Is Used For</th>
                  <th className="gl-c-means">What It Actually Means</th>
                </tr>
              </thead>
              <tbody>
                {s.terms.map((t) => (
                  <tr key={t.term}>
                    <td className="gl-c-term">{t.term}</td>
                    {/* The em dash is the document's own convention for a term
                        that is not an acronym, so it is shown rather than left
                        blank -- a blank cell reads as missing data. */}
                    <td className="gl-c-full">{t.full || '—'}</td>
                    <td className="gl-c-used">{t.usedFor}</td>
                    <td className="gl-c-means">{t.means}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}

function Library({ items, empty, variant }) {
  if (!items || items.length === 0) return <p className="fw-empty">{empty}</p>;

  if (variant === 'titles') {
    return (
      <div className="wt-grid">
        {items.map((item) => <TitleTile key={item.id} item={item} />)}
      </div>
    );
  }

  return (
    <div className="fw-grid">
      {items.map((item) => <ResourceCard key={item.id} item={item} />)}
    </div>
  );
}

export default function KnowledgePage() {
  const { section: slug } = useParams();
  const [params, setParams] = useSearchParams();
  const section = KNOWLEDGE_SECTIONS[slug];

  if (!section) {
    return (
      <div className="fw-page">
        <h1>That section does not exist.</h1>
        <p className="fw-sub">Try Frameworks, or one of the reading, watching or learning lists.</p>
      </div>
    );
  }

  const { kicker, title, sub, empty, items, tabs } = section;
  /* An unknown ?tab= falls back to the first rather than showing nothing --
     a stale bookmark should still land somewhere real. */
  const active = tabs
    ? (tabs.find((t) => t.slug === params.get('tab')) ?? tabs[0])
    : null;

  return (
    <div className="fw-page">
      <div className="fw-kicker">{kicker}</div>
      <h1>{title}</h1>
      <p className="fw-sub">{sub}</p>

      {tabs && (
        /* role="tablist" and the arrow-key behaviour browsers give buttons in
           one: these are real buttons, not links, because they swap content on
           the same page rather than navigating. */
        <div className="fw-tabs" role="tablist" aria-label={`${kicker} sections`}>
          {tabs.map((tab) => {
            const isActive = tab.slug === active.slug;
            return (
              <button
                key={tab.slug}
                type="button"
                role="tab"
                aria-selected={isActive}
                className={`fw-tab${isActive ? ' is-active' : ''}`}
                onClick={() => setParams(
                  tab.slug === tabs[0].slug ? {} : { tab: tab.slug },
                  { replace: true },
                )}
              >
                {tab.label}
                {tab.items.length > 0 && (
                  <span className="fw-tab-count">{tab.items.length}</span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* One caveat that applies to a whole list, said once. Repeating it on
          every card would turn it into wallpaper. */}
      {active?.standing && <p className="fw-standing">{active.standing}</p>}

      {section.variant === 'glossary'
        ? <Glossary sections={section.glossary} />
        : tabs
          ? <Library items={active.items} empty={active.empty} variant={active.variant} />
          : <Library items={items} empty={empty} />}
    </div>
  );
}
