import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import '../styles/legal.css';

const SECTIONS = [
  {
    id: 'overview',
    title: '1. Overview',
    content: `GoXL Consulting Solutions Pvt. Ltd. ("GoXL", "we", "us", "our") operates the Ally platform ("Platform"). This Privacy Policy explains how we collect, use, store, disclose, and protect your personal data when you access or use the Platform. This policy is compliant with India's Digital Personal Data Protection Act, 2023 ("DPDP Act"), and applicable provisions of the Information Technology Act, 2000.`,
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
    content: `We process your personal data on the following legal bases: (a) Consent — you provide explicit consent at the onboarding stage, which you may withdraw at any time without affecting prior processing; (b) Contract — processing is necessary to deliver the Platform services you have requested; (c) Legitimate Interests — to improve our AI models using anonymised, aggregated insights; (d) Legal Obligation — to comply with applicable Indian laws and regulatory requirements. Under the DPDP Act, you are the "Data Principal" and GoXL is the "Data Fiduciary" with respect to your personal data.`,
  },
  {
    id: 'how-we-use',
    title: '4. How We Use Your Data',
    content: `Your data is used to: (a) create and maintain your account; (b) generate your Founder DNA Report and Business DNA analysis; (c) personalise AI-generated recommendations and action plans; (d) provide customer support and respond to your queries; (e) improve the accuracy and reliability of our AI models using anonymised data; (f) send transactional emails related to your account and reports; (g) comply with legal obligations, including data preservation requirements. We do not use your personal data for targeted advertising.`,
  },
  {
    id: 'sharing',
    title: '5. Data Sharing & Disclosure',
    content: `We do not sell or rent your personal data. We may share data with: (a) Cloud Infrastructure Providers — to host and process data (e.g., AWS, Google Cloud), bound by data processing agreements; (b) AI Processing Services — anonymised diagnostic data may be processed by third-party LLM providers under strict data handling agreements; (c) Analytics Providers — pseudonymised usage data for platform improvements; (d) Legal Authorities — where required by law, court order, or government authority. In all cases, we share the minimum data necessary and ensure adequate contractual protections are in place.`,
  },
  {
    id: 'retention',
    title: '6. Data Retention',
    content: `We retain your personal data for as long as your account is active or as necessary to provide services. If you delete your account, we will erase or anonymise your identifiable data within 30 days, except where retention is required by law (e.g., financial records retained for 7 years as required under applicable Indian law). Anonymised, aggregated diagnostic data that cannot be linked back to you may be retained indefinitely to improve our AI models.`,
  },
  {
    id: 'rights',
    title: '7. Your Rights Under the DPDP Act',
    content: `As a Data Principal, you have the following rights under the DPDP Act, 2023: (a) Right to Access — you may request a summary of the personal data we hold about you; (b) Right to Correction — you may request correction of inaccurate or incomplete personal data; (c) Right to Erasure — you may request deletion of your personal data (subject to legal retention obligations); (d) Right to Grievance Redressal — you may raise a complaint with our Grievance Officer (see Section 10); (e) Right to Withdraw Consent — you may withdraw consent at any time; (f) Right to Nominate — you may nominate another individual to exercise your rights in the event of your death or incapacity. To exercise any right, email us at privacy@goxl.in or info@goxl.in.`,
  },
  {
    id: 'security',
    title: '8. Data Security',
    content: `We implement industry-standard technical and organisational safeguards to protect your data, including: TLS 1.3 encryption for all data in transit; AES-256 encryption for data at rest; access controls limiting data access to authorised personnel only; regular security audits and vulnerability assessments; breach notification procedures in compliance with the DPDP Act. While we take every precaution, no system is 100% secure. In the event of a data breach that poses significant risk to your rights, we will notify you as required by law.`,
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
              Effective: 1 July 2026
            </span>
            <span className="legal-meta-item">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M9 12h6m-3-3v6"/><circle cx="12" cy="12" r="9"/></svg>
              Version 1.0
            </span>
            <span className="legal-meta-item">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              DPDP Act 2023 Compliant
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
                        <span className="grievance-value">GoXL Consulting Solutions Pvt. Ltd.,<br />Bangalore, Karnataka, India — 560001</span>
                      </div>
                      <div className="grievance-row">
                        <span className="grievance-label">Email</span>
                        <span className="grievance-value">
                          <a href="mailto:privacy@goxl.in" className="grievance-email">privacy@goxl.in</a>
                        </span>
                      </div>
                      <div className="grievance-row">
                        <span className="grievance-label">Response Time</span>
                        <span className="grievance-value">We aim to acknowledge all complaints within 48 hours and resolve within 30 days.</span>
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
                  <p className="legal-section-body">{s.content}</p>
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
