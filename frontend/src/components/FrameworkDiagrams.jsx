/**
 * components/FrameworkDiagrams.jsx — one illustrative diagram per framework,
 * shown on its detail page. Plain inline SVG, no chart library: these are
 * fixed conceptual shapes (a 2x2 grid, a funnel, a loop), not data
 * visualizations of anything the founder entered.
 */

const STROKE = '#1B4332';
const MUTED = '#8a958b';
const EMERALD = '#10B981';
const LIME = '#A8D94A';
const IVORY = '#fbf7f2';

function Box({ x, y, w, h, fill = IVORY, stroke = STROKE, rx = 8 }) {
  return <rect x={x} y={y} width={w} height={h} rx={rx} fill={fill} stroke={stroke} strokeWidth="1.5" />;
}

function Label({ x, y, children, size = 11, weight = 700, fill = STROKE, anchor = 'middle' }) {
  return (
    <text x={x} y={y} fontSize={size} fontWeight={weight} fill={fill}
          textAnchor={anchor} fontFamily="Inter, sans-serif">
      {children}
    </text>
  );
}

export function FirstPrinciples() {
  return (
    <svg viewBox="0 0 340 220" width="100%" height="220" role="img" aria-label="Breaking a belief down into assumptions, discarding the unverified ones, and rebuilding from what's left">
      <Box x={100} y={8} w={140} h={34} fill="#fff" />
      <Label x={170} y={29}>Current belief</Label>
      <line x1={170} y1={42} x2={170} y2={62} stroke={MUTED} strokeWidth="1.5" markerEnd="url(#arrow)" />
      {[{ x: 20, ok: false }, { x: 130, ok: true }, { x: 240, ok: false }].map((a, i) => (
        <g key={i}>
          <Box x={a.x} y={64} w={80} h={40} fill={a.ok ? '#eafaf3' : '#fff'} stroke={a.ok ? EMERALD : MUTED} />
          <Label x={a.x + 40} y={87} size={10} fill={a.ok ? '#0b6a52' : MUTED}>{`Assumption ${String.fromCharCode(65 + i)}`}</Label>
          <Label x={a.x + 40} y={135} size={16} fill={a.ok ? EMERALD : '#c96'}>{a.ok ? '✓' : '✕'}</Label>
        </g>
      ))}
      <line x1={170} y1={148} x2={170} y2={168} stroke={MUTED} strokeWidth="1.5" markerEnd="url(#arrow)" />
      <Box x={80} y={170} w={180} h={38} fill="#eafaf3" stroke={EMERALD} />
      <Label x={170} y={193} fill="#0b6a52">Rebuilt conclusion</Label>
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 Z" fill={MUTED} />
        </marker>
      </defs>
    </svg>
  );
}

export function EightyTwenty() {
  const bars = [78, 62, 20, 16, 12, 10, 8, 7, 6, 5];
  const w = 22, gap = 8, base = 190;
  return (
    <svg viewBox="0 0 340 220" width="100%" height="220" role="img" aria-label="A few tall bars produce most of the result, with a long tail of small ones">
      <line x1={20} y1={base} x2={320} y2={base} stroke={MUTED} strokeWidth="1.5" />
      {bars.map((h, i) => {
        const x = 24 + i * (w + gap);
        const top20 = i < 2;
        return <rect key={i} x={x} y={base - h} width={w} height={h} rx={3}
                      fill={top20 ? EMERALD : '#d8e6dd'} />;
      })}
      <line x1={62} y1={20} x2={62} y2={base} stroke={STROKE} strokeWidth="1" strokeDasharray="3 3" />
      <Label x={38} y={16} size={10} fill={EMERALD}>~20% of inputs</Label>
      <Label x={38} y={30} size={10} fill={EMERALD} weight={800}>→ ~80% of result</Label>
      <Label x={230} y={16} size={10} fill={MUTED}>long tail</Label>
    </svg>
  );
}

export function EisenhowerMatrix() {
  const quads = [
    { x: 20, y: 16, label: 'Do now', sub: 'Urgent · Important', fill: '#eafaf3', stroke: EMERALD },
    { x: 174, y: 16, label: 'Schedule', sub: 'Not urgent · Important', fill: '#f2f8ee', stroke: LIME },
    { x: 20, y: 116, label: 'Delegate', sub: 'Urgent · Not important', fill: '#fdf6ee', stroke: '#c9a06a' },
    { x: 174, y: 116, label: 'Drop', sub: 'Not urgent · Not important', fill: '#faf3f3', stroke: '#c98a8a' },
  ];
  return (
    <svg viewBox="0 0 340 200" width="100%" height="200" role="img" aria-label="Four quadrants: do now, schedule, delegate, drop">
      {quads.map((q, i) => (
        <g key={i}>
          <Box x={q.x} y={q.y} w={146} h={84} fill={q.fill} stroke={q.stroke} />
          <Label x={q.x + 73} y={q.y + 36} size={13}>{q.label}</Label>
          <Label x={q.x + 73} y={q.y + 54} size={9} weight={500} fill={MUTED}>{q.sub}</Label>
        </g>
      ))}
    </svg>
  );
}

export function DecisionMatrix() {
  const rows = ['Option A', 'Option B', 'Option C'];
  const cols = ['Cost', 'Speed', 'Risk'];
  return (
    <svg viewBox="0 0 340 190" width="100%" height="190" role="img" aria-label="A table scoring each option against weighted criteria">
      <Label x={110} y={16} anchor="start" size={9} fill={MUTED}>criteria →</Label>
      {cols.map((c, i) => <Label key={c} x={112 + i * 60} y={34} size={10}>{c}</Label>)}
      <Label x={280} y={34} size={10} fill={EMERALD}>Total</Label>
      {rows.map((r, ri) => (
        <g key={r}>
          <Label x={40} y={62 + ri * 42} anchor="start" size={10}>{r}</Label>
          {cols.map((c, ci) => (
            <circle key={c} cx={112 + ci * 60} cy={58 + ri * 42} r={9}
                    fill={(ri + ci) % 3 === 0 ? EMERALD : '#dbe6de'} />
          ))}
          <rect x={266} y={48 + ri * 42} width={40} height={20} rx={5} fill="#eafaf3" stroke={EMERALD} />
        </g>
      ))}
    </svg>
  );
}

export function Swot() {
  const quads = [
    { x: 20, y: 16, label: 'Strengths', fill: '#eafaf3', stroke: EMERALD },
    { x: 174, y: 16, label: 'Weaknesses', fill: '#faf3f3', stroke: '#c98a8a' },
    { x: 20, y: 116, label: 'Opportunities', fill: '#f2f8ee', stroke: LIME },
    { x: 174, y: 116, label: 'Threats', fill: '#fdf6ee', stroke: '#c9a06a' },
  ];
  return (
    <svg viewBox="0 0 340 200" width="100%" height="200" role="img" aria-label="Strengths, Weaknesses, Opportunities, Threats in a grid">
      {quads.map((q, i) => (
        <g key={i}>
          <Box x={q.x} y={q.y} w={146} h={84} fill={q.fill} stroke={q.stroke} />
          <Label x={q.x + 73} y={q.y + 46} size={13}>{q.label}</Label>
        </g>
      ))}
      <Label x={170} y={12} size={9} fill={MUTED}>internal</Label>
      <Label x={170} y={112} size={9} fill={MUTED}>external</Label>
    </svg>
  );
}

export function BusinessModelCanvas() {
  const blocks = [
    { x: 8, y: 10, w: 74, h: 90, label: 'Key partners' },
    { x: 86, y: 10, w: 74, h: 42, label: 'Key activities' },
    { x: 86, y: 56, w: 74, h: 44, label: 'Key resources' },
    { x: 164, y: 10, w: 90, h: 90, label: 'Value proposition', fill: '#eafaf3', stroke: EMERALD },
    { x: 258, y: 10, w: 74, h: 42, label: 'Relationships' },
    { x: 258, y: 56, w: 74, h: 44, label: 'Channels' },
    { x: 8, y: 104, w: 190, h: 40, label: 'Cost structure' },
    { x: 202, y: 104, w: 130, h: 40, label: 'Revenue streams' },
  ];
  return (
    <svg viewBox="0 0 340 152" width="100%" height="170" role="img" aria-label="Nine blocks mapping the whole business model">
      {blocks.map((b, i) => (
        <g key={i}>
          <Box x={b.x} y={b.y} w={b.w} h={b.h} fill={b.fill || '#fff'} stroke={b.stroke || MUTED} rx={5} />
          <text x={b.x + b.w / 2} y={b.y + b.h / 2 + 3} fontSize={7.5} fontWeight={700}
                fill={b.stroke ? '#0b6a52' : STROKE} textAnchor="middle" fontFamily="Inter, sans-serif">
            {b.label}
          </text>
        </g>
      ))}
    </svg>
  );
}

export function Okrs() {
  return (
    <svg viewBox="0 0 340 200" width="100%" height="200" role="img" aria-label="One objective with three measurable key results beneath it">
      <Box x={90} y={10} w={160} h={38} fill="#eafaf3" stroke={EMERALD} />
      <Label x={170} y={33} size={11}>Objective</Label>
      {[0, 1, 2].map((i) => {
        const x = 30 + i * 100;
        return (
          <g key={i}>
            <line x1={170} y1={48} x2={x + 40} y2={80} stroke={MUTED} strokeWidth="1.5" />
            <Box x={x} y={82} w={80} h={50} fill="#fff" />
            <Label x={x + 40} y={102} size={9}>{`KR ${i + 1}`}</Label>
            <rect x={x + 10} y={112} width={60} height={6} rx={3} fill="#e3ece6" />
            <rect x={x + 10} y={112} width={60 * [0.8, 0.5, 0.3][i]} height={6} rx={3} fill={EMERALD} />
          </g>
        );
      })}
    </svg>
  );
}

export function Ikigai() {
  const circles = [
    { cx: 130, cy: 90, label: 'Love', dx: -55, dy: -55 },
    { cx: 190, cy: 90, label: 'Good at', dx: 55, dy: -55 },
    { cx: 130, cy: 150, label: 'World needs', dx: -55, dy: 55 },
    { cx: 190, cy: 150, label: 'Paid for', dx: 55, dy: 55 },
  ];
  return (
    <svg viewBox="0 0 340 220" width="100%" height="220" role="img" aria-label="Four overlapping circles: love, good at, world needs, paid for">
      {circles.map((c, i) => (
        <circle key={i} cx={c.cx} cy={c.cy} r={54} fill={EMERALD} fillOpacity="0.14" stroke={EMERALD} strokeWidth="1.2" />
      ))}
      {circles.map((c, i) => (
        <Label key={i} x={c.cx + c.dx} y={c.cy + c.dy} size={10} fill="#0b6a52">{c.label}</Label>
      ))}
      <circle cx={160} cy={120} r={16} fill={EMERALD} />
      <Label x={160} y={124} size={8} fill="#fff" weight={800}>Ikigai</Label>
    </svg>
  );
}

export function LeanStartup() {
  const steps = [
    { label: 'Build', angle: -90 },
    { label: 'Measure', angle: 30 },
    { label: 'Learn', angle: 150 },
  ];
  const cx = 170, cy = 110, r = 70;
  return (
    <svg viewBox="0 0 340 220" width="100%" height="220" role="img" aria-label="A loop: build, measure, learn, then back to build">
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={MUTED} strokeWidth="1.5" strokeDasharray="4 5" />
      {steps.map((s, i) => {
        const rad = (s.angle * Math.PI) / 180;
        const x = cx + r * Math.cos(rad), y = cy + r * Math.sin(rad);
        return (
          <g key={i}>
            <circle cx={x} cy={y} r={30} fill="#eafaf3" stroke={EMERALD} strokeWidth="1.5" />
            <Label x={x} y={y + 4} size={11} fill="#0b6a52">{s.label}</Label>
          </g>
        );
      })}
      <path d={`M ${cx} ${cy - r + 20} A ${r} ${r} 0 0 1 ${cx + r * Math.cos(Math.PI / 6) - 15} ${cy + r * Math.sin(Math.PI / 6) - 15}`}
            fill="none" stroke={MUTED} strokeWidth="1.5" markerEnd="url(#arrow2)" />
      <defs>
        <marker id="arrow2" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 Z" fill={MUTED} />
        </marker>
      </defs>
    </svg>
  );
}

