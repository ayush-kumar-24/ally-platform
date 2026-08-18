import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Ally's replies, rendered as markdown.
 *
 * The model has always answered in markdown -- headings, bold, bullets, code
 * -- and the chat rendered it as a raw string, so founders saw literal `**`
 * and `##` in a single unbroken wall of text.
 *
 * react-markdown builds React elements rather than HTML strings and does NOT
 * pass raw HTML through (no rehype-raw here, deliberately), so a reply can
 * never inject markup into the page. Anything HTML-looking in a reply is
 * shown as text, which is the correct outcome for a chat surface.
 *
 * Only used for Ally's side. A founder's own message is shown verbatim --
 * running their text through a markdown parser would mangle it (a lone
 * asterisk or underscore is far likelier to be punctuation than formatting).
 */
export default function Markdown({ children }) {
  return (
    <div className="md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Fenced blocks get their own scroll container so a wide snippet
          // can never stretch the bubble past the chat column.
          pre: ({ node, ...props }) => <pre className="md-pre" {...props} />,
          /* No inline/block branch here on purpose: react-markdown v9+
             dropped the `inline` prop, so branching on it silently treated
             every inline `snippet` as a code block. CSS distinguishes them
             structurally instead (is the <code> inside a <pre>?), which
             cannot drift with the library version. */
          // Links from a model are untrusted by default: never let one take
          // over this tab, and never leak the app URL as a referrer.
          a: ({ node, ...props }) => (
            <a target="_blank" rel="noopener noreferrer nofollow" {...props} />
          ),
          table: ({ node, ...props }) => (
            <div className="md-table-wrap"><table {...props} /></div>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
