export const MOCK_FOUNDER = {
  name: 'Rahul Varma',
  initials: 'RV',
  email: 'rahul@example.com',
  stage: 'Seed',
  role: 'CEO & Co-founder',
  company: 'Nexus Robotics',
  location: 'Mumbai, India',
  avatar: null,
  clarityScore: 72,
  clarityChanged: false,
  plan: 'pro',
  planLabel: 'Pro',
  planTier: 1,
  planBadge: 'pb-pro',
  joined: '2025-11-14',
};

export const MOCK_DASHBOARD = {
  clarityScore: 72,
  clarityChange: '+5',
  insightCount: 3,
  notifCount: 5,
  activeGoals: 4,
  completedToday: 2,
  stats: [
    { label: 'Founder Clarity', value: 72, unit: '%', sub: '↑ 5% this week', progress: 72, color: 'emerald' },
    { label: 'Business Health', value: 58, unit: '%', sub: '2 dimensions below threshold', progress: 58, color: 'amber' },
    { label: 'AI Sessions', value: 14, unit: '', sub: 'This month', progress: 47, color: 'emerald' },
    { label: 'Action Completion', value: 68, unit: '%', sub: '4 of 6 done today', progress: 68, color: 'emerald' },
  ],
  insights: [
    { tag: 'Pattern detected', tagClass: '', time: '2h ago', text: 'You tend to delay pricing decisions. Every 3-week delay costs ~₹45K in missed runway. Let\'s address this in your next chat.', actions: true },
    { tag: 'High-impact', tagClass: 'clay', time: 'Yesterday', text: 'Your team cohesion score dropped 12% after the last hire. Consider a structured onboarding plan for new executives.', actions: true },
  ],
  recentDiagnoses: [
    { title: 'Q4 Growth Bottleneck', sub: 'Revenue · Operations', score: 84, date: '2 days ago', icon: 'trending' },
    { title: 'Team Alignment Review', sub: 'Culture · Hiring', score: 65, date: '1 week ago', icon: 'users' },
    { title: 'Product Market Fit', sub: 'Strategy · Product', score: 91, date: '2 weeks ago', icon: 'target' },
  ],
  journeySteps: [
    { label: 'Founder DNA', done: true, now: false },
    { label: 'Business DNA', done: true, now: false },
    { label: 'Root Cause', done: false, now: true },
    { label: 'Clarity Report', done: false, now: false },
    { label: 'Action Plan', done: false, now: false },
  ],
  upcomingCall: {
    date: 24,
    month: 'Jul',
    title: 'Strategy Deep Dive',
    with: 'GoXL Coach',
  },
  tokenMeter: {
    used: 68,
    total: 100,
    plan: 'Pro',
    sessionsThisMonth: 14,
    avgPerSession: 4.2,
  },
};

export const MOCK_CHAT_HISTORY = [
  { id: 'c1', title: 'Q4 Growth Strategy', preview: 'We discussed revenue bottlenecks...', time: '2h ago', messages: 12, active: true },
  { id: 'c2', title: 'Team Dynamics & Hiring', preview: 'Explored team cohesion issues...', time: '1d ago', messages: 8, active: false },
  { id: 'c3', title: 'Fundraising Prep', preview: 'Pitch deck and investor targeting...', time: '3d ago', messages: 15, active: false },
  { id: 'c4', title: 'Product Roadmap', preview: 'Prioritization framework...', time: '5d ago', messages: 6, active: false },
];

export const MOCK_MESSAGES = {
  c1: [
    { role: 'ally', text: 'Hi Rahul. Based on our last conversation, I\'ve been thinking about your Q4 growth challenge. Would you like to pick up where we left off?', time: '2h ago' },
    { role: 'me', text: 'Yes please. I\'ve been stuck on whether to focus on retention or acquisition right now.', time: '2h ago' },
    { role: 'ally', text: 'Great question. Let me pull up your numbers. Your retention rate is 68% — that\'s 12% below your industry benchmark. Meanwhile, your CAC is actually below target at ₹4,200.', time: '2h ago' },
    { role: 'ally', text: 'The data suggests retention is your #1 leverage point. A 10% improvement in retention could increase your LTV by 34%, which is worth roughly ₹8.2L annually at your current scale.', time: '2h ago', confidence: 88 },
  ],
};

export const MOCK_NOTIFICATIONS = [
  { id: 'n1', type: 'reminder', status: 'upcoming', time: 'Today, 3:00 PM', message: 'Call with GoXL — Strategy Review', from: 'Ally' },
  { id: 'n2', type: 'insight', status: 'upcoming', time: '2h ago', message: 'New pattern detected in your decision-making data', from: 'Ally' },
  { id: 'n3', type: 'goal', status: 'overdue', time: 'Yesterday', message: 'Complete competitor analysis — overdue by 2 days', from: 'System' },
];

export const MOCK_PLAN_GOALS = [
  { id: 'g1', text: 'Finalize Q3 financial model', priority: 'high', done: false, createdAt: Date.now() - 86400000 },
  { id: 'g2', text: 'Review customer churn analysis', priority: 'high', done: true, createdAt: Date.now() - 172800000 },
  { id: 'g3', text: 'Draft investor update email', priority: 'med', done: false, createdAt: Date.now() - 259200000 },
  { id: 'g4', text: 'Team 1:1s preparation', priority: 'low', done: false, createdAt: Date.now() - 345600000 },
  { id: 'g5', text: 'Update pricing page', priority: 'med', done: true, createdAt: Date.now() - 432000000 },
];

export const MOCK_DIMENSIONS = [
  { name: 'Revenue & Growth', key: 'revenue', score: 76, color: 'hi', note: 'Steady MRR growth at 8% MoM', icon: 'trending' },
  { name: 'Product & Strategy', key: 'product', score: 62, color: 'md', note: 'Feature velocity is strong but strategic clarity needs work', icon: 'target' },
  { name: 'Team & Culture', key: 'team', score: 48, color: 'lo', note: 'Post-hire cohesion dip — invest in onboarding structure', icon: 'users' },
  { name: 'Operations & Execution', key: 'ops', score: 70, color: 'hi', note: 'Good operational cadence, documentation needs improvement', icon: 'settings' },
  { name: 'Fundraising & Finance', key: 'finance', score: 55, color: 'md', note: 'Runway of 14 months but no active investor conversations', icon: 'dollar' },
  { name: 'Market & Positioning', key: 'market', score: 80, color: 'hi', note: 'Strong NPS, clear differentiation in your segment', icon: 'compass' },
];

export const MOCK_GUIDED_STEPS = [
  { id: 'login', label: 'Welcome', group: 'Start' },
  { id: 'expectation', label: 'How it works', group: 'Start' },
  { id: 'welcome', label: 'Your Journey', group: 'Start' },
  { id: 'allyintro', label: 'Meet Ally', group: 'Discover' },
  { id: 'profile', label: 'Tell me about you', group: 'Discover' },
  { id: 'tour', label: 'Quick Tour', group: 'Discover' },
  { id: 'summary', label: 'Your Summary', group: 'Build' },
  { id: 'validate', label: 'Validation', group: 'Build' },
  { id: 'problem', label: 'Your Challenge', group: 'Build' },
  { id: 'reveal', label: 'Clarity Reveal', group: 'Results' },
  { id: 'recommend', label: 'Recommendations', group: 'Results' },
  { id: 'success', label: 'Complete', group: 'Results' },
];

export const MOCK_ACTIVITIES = [
  { label: 'Founder DNA assessed', time: '2 days ago' },
  { label: 'Business DNA mapped', time: '2 days ago' },
  { label: 'Root cause identified', time: 'Today' },
  { label: 'Clarity Report generated', time: '' },
];

export const LANDING_NAV_ITEMS = [
  { href: '#lp-hero', label: 'Home' },
  { href: '#lp-engine', label: 'Inside the Engine' },
  { href: '#lp-features', label: 'Why Ally' },
  { href: '#lp-how', label: 'The Clarity Method' },
  { href: '#lp-final', label: 'Get Started' },
];

export const MOCK_PLANS = [
  { id: 'free', name: 'Free', price: 0, period: '/mo', tag: 'Good for a taste', popular: false, cta: 'Current', features: ['2 diagnoses / mo', 'Basic founder DNA', '1 chat session / week', 'Email support'] },
  { id: 'pro', name: 'Pro', price: 2499, period: '/mo', tag: 'For active founders', popular: true, cta: 'Start Pro', features: ['10 diagnoses / mo', 'Full founder + business DNA', 'Unlimited chat', 'Priority support', 'Clarity reports', 'Action plans'] },
  { id: 'proplus', name: 'Pro+', price: 4999, period: '/mo', tag: 'For scaling teams', popular: false, cta: 'Start Pro+', features: ['25 diagnoses / mo', 'Everything in Pro', 'Team accounts (3)', 'Dedicated coach', 'Custom benchmarks', 'API access'] },
  { id: 'max', name: 'Max', price: 9999, period: '/mo', tag: 'For enterprises', popular: false, cta: 'Contact us', features: ['Unlimited diagnoses', 'Everything in Pro+', 'Unlimited team members', 'White-label reports', 'On-premise option', 'SLA guarantee'] },
];

export const MOCK_HELP_FAQ = [
  { q: 'How does Ally diagnose my business?', a: 'Ally asks you a series of questions about your founder journey, decision patterns, and business metrics. It then cross-references your answers across 10+ business dimensions to identify your root constraint.' },
  { q: 'Is my data private?', a: 'Yes. All data is encrypted end-to-end. We never share your personal or business data. You can delete your data at any time from your profile settings.' },
  { q: 'How long does a diagnosis take?', a: 'The initial guided diagnosis takes about 15-20 minutes. Follow-up sessions are typically 5-10 minutes.' },
  { q: 'Can I use Ally with my team?', a: 'Yes. Pro+ and Max plans include team accounts so your co-founders and key team members can also participate in diagnoses.' },
  { q: 'What is the Founder DNA Platform?', a: 'It\'s a framework that separates founder-level patterns from business-level metrics. Most tools diagnose the business; Ally diagnoses the founder first, then the business, then finds the root cause at their intersection.' },
];

export const MOCK_DISCOVERY_SLOTS = {
  '2026-07-15': ['10:00 AM', '11:30 AM', '2:00 PM', '4:00 PM'],
  '2026-07-16': ['9:00 AM', '10:30 AM', '1:00 PM', '3:30 PM'],
  '2026-07-17': ['11:00 AM', '2:00 PM', '4:30 PM'],
  '2026-07-18': ['9:30 AM', '11:00 AM', '2:30 PM'],
};
