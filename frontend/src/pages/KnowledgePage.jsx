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
 * TWO KINDS OF CARD. A podcast episode has a link, so its whole card is one.
 * A film has no link worth giving (see the note in data/watch.js), and there
 * are sixty-five of them -- printing every description at once is a wall
 * nobody reads. Those render as title tiles that open on hover.
 *
 * NO LOADING STATE, deliberately. This is static reference content imported at
 * build time -- there is nothing to fetch, and a spinner over data already in
 * the bundle is a lie about what is happening.
 */

import { useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { KNOWLEDGE_SECTIONS } from '../data/knowledge';

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
 * A film or series: the title at rest, everything else on hover.
 *
 * HOVER IS NOT THE ONLY WAY IN. A hover-only disclosure is invisible on a
 * phone and unreachable from a keyboard, so the face is a real <button>:
 * clicking or tapping it pins the detail open, and `aria-expanded` says so.
 * Hover is the shortcut on top of that, not the mechanism.
 *
 * The detail is absolutely positioned over the tile and allowed to overhang
 * downwards. Growing the tile in place would reflow every card in the row on
 * a mouse-over, which looks broken even when it isn't.
 */
function TitleTile({ item }) {
  const [open, setOpen] = useState(false);

  return (
    <div
      className={`wt-tile${open ? ' is-open' : ''}`}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        className="wt-face"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        onKeyDown={(e) => { if (e.key === 'Escape') setOpen(false); }}
      >
        <span className="wt-name">{item.title}</span>
        <span className="wt-sub">
          {item.year}
          {item.year && item.tag ? ' · ' : ''}
          {item.tag}
        </span>
      </button>

      {/* The panel takes pointer events so the cursor can cross it without the
          tile losing hover and flickering. That means a second tap lands here
          rather than on the face, so closing has to live here too. */}
      <div className="wt-pop" onClick={() => setOpen(false)}>
        <span className="wt-name">{item.title}</span>
        <span className="wt-sub">
          {item.year}
          {item.year && item.tag ? ' · ' : ''}
          {item.tag}
        </span>

        {item.why && <p className="wt-why">{item.why}</p>}

        {item.forWhen && (
          <p className="wt-line">
            <span className="wt-line-label">Watch it when</span>
            {item.forWhen}
          </p>
        )}

        {item.ask && (
          <p className="wt-line">
            <span className="wt-line-label">Ask yourself after</span>
            {item.ask}
          </p>
        )}

        {/* Shown, not filed away. The films most likely to be misread are the
            ones most likely to be watched, so the warning travels with the
            title rather than living in a document nobody opens. */}
        {item.care && <p className="wt-care">{item.care}</p>}
      </div>
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
        <div className="fw-tabs" role="tablist" aria-label="What to watch">
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

      {tabs
        ? <Library items={active.items} empty={active.empty} variant={active.variant} />
        : <Library items={items} empty={empty} />}
    </div>
  );
}
