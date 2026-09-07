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
 * NO LOADING STATE, deliberately. This is static reference content imported at
 * build time -- there is nothing to fetch, and a spinner over data already in
 * the bundle is a lie about what is happening.
 */

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

function Library({ items, empty }) {
  if (!items || items.length === 0) return <p className="fw-empty">{empty}</p>;
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

      {tabs
        ? <Library items={active.items} empty={active.empty} />
        : <Library items={items} empty={empty} />}
    </div>
  );
}
