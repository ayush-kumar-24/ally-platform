import { useEffect } from 'react';
import { Link } from 'react-router-dom';

const SECTIONS = [
  {
    id: 'overview',
    title: '1. Overview',
    content: `GoXL Consulting Solutions Pvt. Ltd. ("GoXL", "we", "us", "our") operates the Ally platform ("Platform"). This Privacy Policy explains how we collect, use, store, disclose, and protect your personal data when you access or use the Platform. This policy is written to meet India's Digital Personal Data Protection Act, 2023 ("DPDP Act") and applicable provisions of the Information Technology Act, 2000. It describes the commitments we make to you; it is not by itself a certification that every operational control behind those commitments has been independently verified.`,
  },
  {
    id: 'data-collected',
    title: '2. Data We Collect',
    // (a) rewritten when sign-in moved off Google/LinkedIn OAuth. It declared a
    // profile photo obtained via OAuth -- the email + one-time-code flow supplies
    // no photo and no OAuth profile, so the policy was describing a collection
    // that no longer happens, by a mechanism that no longer exists. Name is now
    // self-declared by the founder at sign-up; email is verified by one-time code.
    content: `We collect the following categories of personal data: (a) Identity & Contact Data — your email address, verified by a one-time code sent to it, and the name you provide when creating your account; (b) Business Diagnostic Data — your responses to diagnostic questions about your business, including financial health, team dynamics, growth challenges, and strategic decisions; (c) Usage & Technical Data — IP address, browser type, device identifiers, pages visited, session duration, and click-path data; (d) Communication Data — any messages or queries you send us via email or the in-platform support feature; (e) Consent Records — timestamps and version numbers of the consents you have provided.`,
  },
  {
    id: 'legal-basis',
    title: '3. Legal Basis for Processing',
    content: `Under the DPDP Act you are the "Data Principal" and GoXL is the "Data Fiduciary". The Act allows personal data to be processed on your consent, or for one of the specific "legitimate uses" it lists in Section 7 — it does not have a general "legitimate interests" basis of the kind found in European law. (a) Consent — this is our primary basis. You give it explicitly at sign-up, in two separate ticks: one for these documents, and one, entirely optional, for processing your business diagnostic answers. You may withdraw either at any time, which stops further processing from that point without making earlier processing unlawful; (b) Legitimate uses under Section 7 — for the limited purposes the Act itself permits, including complying with a legal obligation or a court order. Improving our models is NOT one of these and we do not claim it as one. Where we improve our models, we do so using data that has been aggregated and stripped of anything that identifies you; data in that state is no longer personal data and falls outside the Act. If we ever wanted to use your identifiable data for model improvement, we would come back and ask you for separate consent.`,
  },
  {
    id: 'how-we-use',
    title: '4. How We Use Your Data',
    content: `Your data is used to: (a) create and maintain your account; (b) generate your Founder DNA Report and Business DNA analysis; (c) personalise AI-generated recommendations and action plans; (d) provide customer support and respond to your queries; (e) improve the accuracy and reliability of our AI models using anonymised data; (f) send transactional emails related to your account and reports; (g) comply with legal obligations, including data preservation requirements. We do not use your personal data for targeted advertising.`,
  },
  {
    id: 'sharing',
    title: '5. Data Sharing & Disclosure',
    content: `We do not sell or rent your personal data. We may share data with: (a) Cloud Infrastructure and Service Providers — to host and run the platform, bound by data processing agreements. These are: Amazon Web Services (hosting and database, Mumbai region), Supabase (sign-in), Razorpay (payments), our email delivery provider, and an error-monitoring service. A current list is available on request; (b) AI Processing Services — the answers you give Ally, and the content of your conversations with it, are sent to third-party large language model providers so that Ally can respond. These providers are located OUTSIDE India, primarily in the United States, so this involves a cross-border transfer of your data. They process it only to generate a response for you, under contractual terms that prohibit using it to train their models. Your data is stored in India; this processing step is the exception, and we are naming it here rather than leaving it implied; (c) Analytics Providers — pseudonymised usage data for platform improvements; (d) Legal Authorities — where required by law, court order, or government authority. In all cases, we share the minimum data necessary and ensure adequate contractual protections are in place.`,
  },
  {
    id: 'retention',
    title: '6. Data Retention',
    content: `We retain your personal data for as long as your account is active or as necessary to provide services. If you delete your account, there is a 30-day window in which you can change your mind and cancel. Once that window closes, we erase or anonymise your identifiable data within 30 days of it closing, except where retention is required by law (e.g., financial records retained for 7 years as required under applicable Indian law). Anonymised, aggregated diagnostic data that cannot be linked back to you may be retained indefinitely to improve our AI models.`,
  },
  {
    id: 'rights',
    title: '7. Your Rights Under the DPDP Act',
    content: `As a Data Principal, you have the following rights under the DPDP Act, 2023: (a) Right to Access — you may request a summary of the personal data we hold about you; (b) Right to Correction — you may request correction of inaccurate or incomplete personal data; (c) Right to Erasure — you may request deletion of your personal data (subject to legal retention obligations); (d) Right to Grievance Redressal — you may raise a complaint with our Grievance Officer (see Section 10); (e) Right to Withdraw Consent — you may withdraw consent at any time; (f) Right to Nominate — you may nominate another individual to exercise your rights in the event of your death or incapacity.

The fastest way to exercise most of these is inside your account, under Profile → Privacy Centre. From there you can download everything we hold about you or a portable copy of what you gave us, see a summary of what we store, request a correction, withdraw your consent, pause processing of your data, and delete your account — each of which takes effect immediately or, for deletion, after a 30-day window in which you can change your mind. You do not need to email anyone or wait for us to action it. If you would rather write to us, or you cannot sign in, email privacy@goxl.in or info@goxl.in and we will action it for you.`,
  },
  {
    id: 'security',
    title: '8. Data Security',
    content: `We protect your data with the following measures: all traffic between you and the Platform travels over encrypted connections (TLS); our database is not reachable from the public internet and is accessible only to our own server-side code, never directly from a browser; it is encrypted at rest by our cloud database provider; access by our personnel is restricted to those who need it and is logged; and we operate the breach procedure described below. We describe here only the controls we actually operate — where an independent audit or penetration test has been carried out, we will say so specifically rather than claim it in general terms. No system is completely secure, and we do not claim otherwise.

If a personal data breach affects your data, we will inform the Data Protection Board of India and every affected person, in the form and manner the DPDP Act requires. We do not apply our own severity threshold before telling you: the obligation under Section 8(6) of the Act applies to a personal data breach, not only to a serious one.`,
  },
  {
    id: 'cookies',
    title: '9. Cookies & Tracking',
    content: `We use cookies and similar technologies to operate the Platform and, with your consent, to analyse usage patterns. Essential cookies are required for Platform functionality and cannot be disabled. Optional analytics and marketing cookies are only set with your explicit consent via our cookie preference centre. You can update your cookie preferences at any time through the cookie banner. For full details, see our Cookie Notice within the Platform.`,
  },
  {
    id: 'grievance',
    title: '10. Grievance Officer',
    content: '',
    isGrievance: true,
  },
  {
    id: 'changes',
    title: '11. Changes to This Policy',
    content: `We may update this Privacy Policy from time to time. Material changes will be communicated via the Platform or email at least 7 days before they take effect. Your continued use of the Platform after the effective date constitutes your acceptance of the updated policy. The current version number and effective date are always shown at the top of this page.`,
  },
  {
    id: 'contact-privacy',
    title: '12. Contact Us',
    content: `For any privacy-related questions not addressed by this policy, please contact us at info@goxl.in. For formal complaints or data rights requests, please use the Grievance Officer contact in Section 10.`,
  },
];

/* Split a section body on blank lines. Kept here rather than reaching for a
   Markdown renderer: these strings are plain prose and the only structure
   they carry is the paragraph break. */
const paragraphs = (text) => String(text || "").split(/\n\s*\n/)
  .map((t) => t.trim())
  .filter(Boolean);

export default function PrivacyPolicy() {
  useEffect(() => {
    document.title = 'Privacy Policy — Ally by GoXL';
    window.scrollTo(0, 0);
  }, []);

  return (
    <div className="legal-page">
      {/* Background orbs */}
      <span className="legal-orb legal-orb-1" aria-hidden="true" />
      <span className="legal-orb legal-orb-2" aria-hidden="true" />

      {/* Header */}
      <header className="legal-header">
        <Link to="/" className="legal-logo" aria-label="GoXL — home">
          <img className="legal-logo-mark" src="/ally-logo-mark-on-dark.png" alt="" width="512" height="512" decoding="async" />
          <div className="lnl-mark">Go<span className="x">XL</span></div>
          <span className="legal-logo-sub">Ally Platform</span>
        </Link>
        <nav className="legal-nav-links" aria-label="Legal pages">
          <Link to="/terms" className="legal-nav-link">Terms of Service</Link>
          <Link to="/privacy" className="legal-nav-link active">Privacy Policy</Link>
        </nav>
      </header>

      <main className="legal-main" id="main-content">
        {/* Hero */}
        <div className="legal-hero">
          <div className="legal-badge">Legal & Privacy</div>
          <h1 className="legal-title">Privacy Policy</h1>
          <p className="legal-subtitle">
            We are committed to protecting your data and your right to privacy.
          </p>
          <div className="legal-meta-row">
            <span className="legal-meta-item">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
              Effective: 29 September 2026
            </span>
            <span className="legal-meta-item">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M9 12h6m-3-3v6"/><circle cx="12" cy="12" r="9"/></svg>
              Version 1.1
            </span>
            <span className="legal-meta-item">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              Written for the DPDP Act, 2023
            </span>
          </div>
        </div>

        {/* Two-column layout */}
        <div className="legal-layout">
          {/* Sticky TOC */}
          <aside className="legal-toc" aria-label="Table of contents">
            <p className="legal-toc-label">On this page</p>
            <nav>
              <ul className="legal-toc-list">
                {SECTIONS.map((s) => (
                  <li key={s.id}>
                    <a href={`#${s.id}`} className="legal-toc-link">
                      {s.title}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          </aside>

          {/* Content */}
          <article className="legal-content">
            {SECTIONS.map((s) =>
              s.isGrievance ? (
                <section key={s.id} id={s.id} className="legal-section">
                  <h2 className="legal-section-title">{s.title}</h2>
                  {/* DPDP-mandated Grievance Officer card */}
                  <div className="grievance-card">
                    <div className="grievance-card-header">
                      <span className="grievance-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
                      </span>
                      <div>
                        <p className="grievance-role">Grievance Officer</p>
                        <p className="grievance-notice">
                          In accordance with the Information Technology Act, 2000 and the Digital Personal Data Protection Act, 2023, the details of the Grievance Officer are provided below:
                        </p>
                      </div>
                    </div>
                    <div className="grievance-details">
                      <div className="grievance-row">
                        <span className="grievance-label">Name</span>
                        <span className="grievance-value">Ayush Kumar</span>
                      </div>
                      <div className="grievance-row">
                        <span className="grievance-label">Designation</span>
                        <span className="grievance-value">Founder & Chief Data Officer</span>
                      </div>
                      <div className="grievance-row">
                        <span className="grievance-label">Organisation</span>
                        <span className="grievance-value">GoXL Consulting Solutions Pvt. Ltd.</span>
                      </div>
                      <div className="grievance-row">
                        <span className="grievance-label">Address</span>
                        <span className="grievance-value">GoXL Consulting Solutions Pvt. Ltd.,<br />513, National Plaza, RC Dutt Road, Alkapuri,<br />Vadodara, Gujarat, India — 390007</span>
                      </div>
                      <div className="grievance-row">
                        <span className="grievance-label">Email</span>
                        <span className="grievance-value">
                          <a href="mailto:privacy@goxl.in" className="grievance-email">privacy@goxl.in</a>
                        </span>
                      </div>
                      <div className="grievance-row">
                        <span className="grievance-label">Response Time</span>
                        <span className="grievance-value">We aim to acknowledge all complaints within 48 hours and resolve within 30 days. The fastest way to reach us is Privacy Center → Raise a privacy complaint inside your account, which records your complaint and its time directly with our team. You can also write to the address above.</span>
                      </div>
                    </div>
                    <p className="grievance-footer-note">
                      If you are not satisfied with the resolution provided by the Grievance Officer, you may approach the Data Protection Board of India as constituted under the DPDP Act, 2023.
                    </p>
                  </div>
                </section>
              ) : (
                <section key={s.id} id={s.id} className="legal-section">
                  <h2 className="legal-section-title">{s.title}</h2>
                  {/* One <p> per paragraph. A single <p> collapses the blank lines in
                      these strings into a space, which turned the longer sections into
                      one unbroken wall of text. */}
                  {paragraphs(s.content).map((para, i) => (
                    <p className="legal-section-body" key={i}>{para}</p>
                  ))}
                </section>
              )
            )}
          </article>
        </div>

        {/* Footer strip */}
        <div className="legal-footer-strip">
          <p>
            Have a privacy concern?{' '}
            <a href="mailto:privacy@goxl.in" className="legal-footer-link">Email our Grievance Officer at privacy@goxl.in</a>
          </p>
          <div className="legal-footer-strip-links">
            <Link to="/terms" className="legal-footer-link">Terms of Service →</Link>
          </div>
        </div>
      </main>
    </div>
  );
}
