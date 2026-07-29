import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import '../styles/legal.css';

const SECTIONS = [
  {
    id: 'acceptance',
    title: '1. Acceptance of Terms',
    content: `By accessing or using the Ally platform ("Platform") operated by GoXL Consulting Solutions Pvt. Ltd. ("GoXL", "we", "us", or "our"), you confirm that you are at least 18 years old, have the legal authority to enter into this agreement on behalf of yourself or your business entity, and agree to be bound by these Terms of Service ("Terms"). If you do not agree, please do not use the Platform.`,
  },
  {
    id: 'description',
    title: '2. Description of Service',
    content: `Ally is an AI-powered founder diagnostic and advisory platform. It collects information about your business and leadership profile to generate a Founder DNA Report, a Business DNA analysis, and personalised next-step recommendations. The Platform is a decision-support tool — it does not constitute professional legal, financial, or management consulting advice. You remain solely responsible for all business decisions made in reliance on any output from the Platform.`,
  },
  {
    id: 'accounts',
    title: '3. User Accounts & Authentication',
    content: `Access to the Platform is granted via OAuth 2.0 authentication through Google or LinkedIn. You are responsible for maintaining the confidentiality of your account session and for all activities that occur under your account. You agree to immediately notify GoXL of any unauthorised use of your account at info@goxl.in. GoXL reserves the right to suspend or terminate accounts that violate these Terms.`,
  },
  {
    id: 'data',
    title: '4. Your Data & Content',
    content: `You retain full ownership of all business information, diagnostic inputs, and data you provide to the Platform ("Your Data"). By submitting Your Data, you grant GoXL a limited, non-exclusive, royalty-free licence to process Your Data solely to deliver the Platform's services to you. We do not sell, rent, or share Your Data with third parties for advertising or marketing purposes. Anonymised, aggregated insights may be used internally to improve our AI models.`,
  },
  {
    id: 'prohibited',
    title: '5. Prohibited Conduct',
    content: `You agree not to: (a) reverse-engineer, decompile, or attempt to extract the source code of the Platform or its AI models; (b) use automated bots, scrapers, or scripts to access the Platform; (c) submit false, misleading, or fraudulent business information; (d) attempt to gain unauthorised access to other users' accounts or data; (e) use the Platform for any unlawful purpose or in violation of applicable law; (f) resell or sublicence access to the Platform without prior written consent from GoXL.`,
  },
  {
    id: 'ip',
    title: '6. Intellectual Property',
    content: `The Platform, including all AI models, report formats, UI/UX design, and underlying technology, is the exclusive property of GoXL Consulting Solutions Pvt. Ltd. and is protected by applicable intellectual property laws. You are granted a limited, non-transferable licence to use the Platform for your personal or internal business purposes only. The Ally name, GoXL name, logos, and all associated trademarks are the property of GoXL.`,
  },
  {
    id: 'disclaimers',
    title: '7. Disclaimers & Limitation of Liability',
    content: `The Platform is provided on an "AS IS" and "AS AVAILABLE" basis. GoXL makes no warranties, express or implied, regarding the accuracy, completeness, or fitness for purpose of any AI-generated output. To the fullest extent permitted by law, GoXL's total aggregate liability to you for any claims arising out of or related to these Terms or your use of the Platform shall not exceed the amount you have paid to GoXL in the three (3) months preceding the claim. In no event shall GoXL be liable for any indirect, incidental, consequential, or punitive damages.`,
  },
  {
    id: 'termination',
    title: '8. Termination',
    content: `Either party may terminate this agreement at any time. You may delete your account from within the Platform settings. GoXL may suspend or terminate your access with or without notice if you breach these Terms. Upon termination, your right to use the Platform ceases immediately. Sections 4, 6, 7, and 9 shall survive termination.`,
  },
  {
    id: 'governing',
    title: '9. Governing Law & Dispute Resolution',
    content: `These Terms shall be governed by and construed in accordance with the laws of India. Any disputes arising from these Terms shall first be attempted to be resolved through good-faith negotiation. If unresolved within 30 days, disputes shall be subject to the exclusive jurisdiction of the courts of Bangalore, Karnataka, India.`,
  },
  {
    id: 'changes',
    title: '10. Changes to These Terms',
    content: `GoXL reserves the right to update these Terms at any time. We will notify you of material changes via the Platform or email. Your continued use of the Platform after the effective date of any changes constitutes your acceptance of the revised Terms. The current version number and effective date are displayed at the top of this page.`,
  },
  {
    id: 'contact',
    title: '11. Contact',
    content: `For any questions regarding these Terms, please contact us at info@goxl.in. For privacy-specific queries or data-related complaints, please refer to our Privacy Policy and the Grievance Officer contact listed therein.`,
  },
];

export default function TermsOfService() {
  useEffect(() => {
    document.title = 'Terms of Service — Ally by GoXL';
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
          <Link to="/terms" className="legal-nav-link active">Terms of Service</Link>
          <Link to="/privacy" className="legal-nav-link">Privacy Policy</Link>
        </nav>
      </header>

      <main className="legal-main" id="main-content">
        {/* Hero */}
        <div className="legal-hero">
          <div className="legal-badge">Legal</div>
          <h1 className="legal-title">Terms of Service</h1>
          <p className="legal-subtitle">
            Please read these terms carefully before using the Ally platform.
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
              Governed by Indian Law
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
            {SECTIONS.map((s) => (
              <section key={s.id} id={s.id} className="legal-section">
                <h2 className="legal-section-title">{s.title}</h2>
                <p className="legal-section-body">{s.content}</p>
              </section>
            ))}
          </article>
        </div>

        {/* Footer strip */}
        <div className="legal-footer-strip">
          <p>
            Questions about these terms?{' '}
            <a href="mailto:info@goxl.in" className="legal-footer-link">Contact us at info@goxl.in</a>
          </p>
          <div className="legal-footer-strip-links">
            <Link to="/privacy" className="legal-footer-link">Privacy Policy →</Link>
          </div>
        </div>
      </main>
    </div>
  );
}
