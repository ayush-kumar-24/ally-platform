/**
 * data/faqs.js — the product's answers, in one place.
 *
 * Shared by the Help & Support page and the help widget that floats over every
 * platform page. They used to be one array inside HelpSupport.jsx; a second
 * surface asking the same questions is exactly how two versions of an answer
 * start to drift, and a support answer that contradicts itself is worse than
 * no answer.
 *
 * Answers are checked against what the code actually does, not what the
 * product is meant to do eventually. Four of the originals were wrong -- the
 * worst claimed Pro "unlocks unlimited diagnoses", while every tier is capped
 * at diagnosis_lifetime_limit = 1 (backend/app/plans/catalog.py), and
 * described a two-tier ladder that no longer matched the catalog. A support
 * page that overstates a paid plan is worse than no support page.
 *
 * The plan answers below track MOCK_PLANS and COMPARE_ROWS (data/mockData.js,
 * pages/Billing.jsx). If the ladder changes again, they change here too --
 * there is no Free tier any more, and chat is a paid feature.
 *
 * `keywords` exist for the search only: the words a founder actually types
 * ("password", "stuck", "refund") are often in neither the question nor the
 * answer, so searching for them found nothing at all.
 */

export const FAQS = [
  {
    q: 'How do I start a diagnosis?',
    a: 'Open "Adaptive diagnosis" in the sidebar — or "Start Founder Diagnosis" on your Compass. Ally begins with Founder DNA (how you decide and work), then moves to your current problem, then the business itself.',
    keywords: 'begin get started first steps new founder dna assessment',
  },
  {
    q: 'How do plans work?',
    a: 'There are three: Starter (₹199/month), Plus (₹450/month) and Pro (₹999/month). All three include one adaptive diagnosis, your Clarity Report, voice in the diagnosis, and booking a discovery call at ₹300 per 30 minutes. Plus adds chat with Ally (3,500 tokens a day), voice in chat, your next 3 steps, Goals and Plan Your Day. Pro raises chat to 8,000 tokens a day and adds Ally recommending your steps, Vision, discussing the knowledge base, email reminders, Know My Energy and priority call booking.',
    keywords: 'pricing price cost subscription tiers basic starter plus pro difference compare free',
  },
  {
    q: 'How many diagnoses do I get?',
    a: 'One full diagnosis per account, on every plan including Pro — it is a deep one-time mapping, not something to re-run weekly. Upgrading raises your chat allowance and unlocks features, not the diagnosis count. If you genuinely need a second run, contact support and we will look at it case by case.',
    keywords: 'again retake repeat second another limit once',
  },
  {
    q: 'How do reminders work?',
    a: 'Tasks you set in Plan Your Day show up as "Next due", and Ally nudges you about anything overdue or due today while you are in the app. There are no push notifications or reminder emails yet, so Ally cannot reach you when the app is closed.',
    keywords: 'notification alert push email nudge due tasks plan day',
  },
  {
    q: 'How do I upgrade?',
    a: 'Go to Profile, then the Subscription & billing card, and click "Upgrade plan".',
    keywords: 'pay payment billing subscribe buy plan change',
  },
  {
    q: 'Can I edit my Founder Profile?',
    a: 'Yes. Go to Profile, click "Edit" in the Founder Identity section, change your name, email or LinkedIn URL, and save.',
    keywords: 'change name email linkedin details update identity',
  },
  {
    q: 'Can I export, download or share my report?',
    a: 'Yes. The report page has a download button that gives you the report as a PDF, and a share button that creates a link anyone can open without signing in. Shared links are listed under "Links you have shared" on the same page, and you can revoke one there at any time. To export everything Ally holds about you — not just this report — use Profile → Privacy Center → "Download my data", which arrives as a JSON file immediately.',
    keywords: 'pdf save print share copy export download report link revoke send',
  },
  {
    q: 'What happens to my data, and can I delete it?',
    a: 'Profile → Privacy Center is the single place for this. You can download everything we hold, see a category-by-category summary, pause AI processing, withdraw consent, or request account deletion — which is scheduled with a 30-day recovery window before anything is permanently erased.',
    keywords: 'privacy security delete account remove gdpr consent stored',
  },

  /* Below: the questions support actually receives that had no answer here.
     Each one describes what the app does today -- where a capability does not
     exist (no self-serve cancel, no email support ticket), it says so rather
     than pointing at a button that is not there. */

  {
    q: "I forgot my password — how do I get back in?",
    a: 'On the sign-in page choose "Email me a code" and enter your email. Ally sends an 8-digit code; entering it lets you set a new password there and then. Your email address is your login — there is no separate username to remember.',
    keywords: 'reset forgot password locked out cannot sign in login recover change password',
  },
  {
    q: "The sign-in code hasn't arrived",
    a: 'Codes usually arrive within a minute. Check your spam or promotions folder first, and make sure you used the same address you registered with. A code expires after a few minutes, so if it has been a while, request a fresh one — the button re-enables after a short cooldown. If nothing arrives at all, email us and we will check the address on your account.',
    keywords: 'otp code email not received spam missing expired resend wait',
  },
  {
    q: 'Ally stopped mid-diagnosis. Did I lose my answers?',
    a: 'No. Every answer is saved as you go, so closing the tab or losing connection does not lose your progress. Open "Adaptive diagnosis" again and you will be returned to where you stopped.',
    keywords: 'crash refresh closed tab lost progress resume continue interrupted stuck',
  },
  {
    q: 'When is my report ready?',
    a: 'The report is written from your completed diagnosis, so it becomes available once the diagnosis is finished — not on a schedule. Until then the Report page tells you what is still missing. Generating it takes seconds, not days.',
    keywords: 'how long wait ready time report generate available',
  },
  {
    q: 'I have run out of chat for today',
    a: 'Chat is metered by a daily token allowance that resets each day, so waiting until tomorrow restores it — Plus gives 3,500 tokens a day and Pro 8,000. Upgrading raises the allowance; it does not change the diagnosis, which every plan includes once.',
    keywords: 'limit quota tokens allowance exhausted used up daily reset chat blocked',
  },
  {
    q: 'How do I cancel or get a refund?',
    a: 'There is no self-serve cancel button yet. Email info@goxl.in from the address on your account and we will handle the cancellation and any refund question directly.',
    keywords: 'stop billing unsubscribe money back downgrade cancel refund',
  },
  {
    q: 'Is my business information private?',
    a: 'Yes. What you tell Ally is yours: it is used to give you your diagnosis, report and recommendations, and is never sold or shared as a product. Profile → Privacy Center shows exactly what is held, lets you pause AI processing, and lets you export or delete it.',
    keywords: 'confidential secure who can see shared sold safe private encryption',
  },
  {
    q: 'Can I talk to a person?',
    a: 'Yes. Use "Schedule assistance" on this page to book a discovery call — every plan can book one at ₹300 per 30 minutes, and Pro gets priority on slots — or email info@goxl.in and we will reply within one working day (Mon–Fri, 9 AM – 6 PM IST).',
    keywords: 'human call phone speak team contact support real person meeting',
  },
];

/**
 * FAQs matching `query`, best first, or all of them for an empty query.
 *
 * Every word has to match somewhere (AND, not OR) -- with OR, "delete report"
 * returned both the deletion answer and every answer that merely says
 * "report". Ranking puts a question-title hit above a keyword hit above a
 * body hit, so the answer whose *subject* is what you typed comes first.
 */
export function searchFaqs(query, faqs = FAQS) {
  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return faqs;

  return faqs
    .map((faq) => {
      const q = faq.q.toLowerCase();
      const k = (faq.keywords || '').toLowerCase();
      const a = faq.a.toLowerCase();
      let score = 0;
      for (const w of words) {
        if (q.includes(w)) score += 3;
        else if (k.includes(w)) score += 2;
        else if (a.includes(w)) score += 1;
        else return null; // this FAQ misses a word -- drop it entirely
      }
      return { faq, score };
    })
    .filter(Boolean)
    .sort((x, y) => y.score - x.score)
    .map((hit) => hit.faq);
}
