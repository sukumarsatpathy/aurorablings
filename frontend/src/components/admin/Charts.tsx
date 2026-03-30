import { cn } from '@/lib/utils';

export function ActivityRing({ pct = 0.72, size = 54, color = "#fff", className }: { pct?: number, size?: number, color?: string, className?: string }) {
  const r = (size - 6) / 2, circ = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className={className}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="currentColor" strokeWidth="6" className="opacity-25" />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth="6"
        strokeDasharray={circ} strokeDashoffset={circ * (1 - pct)}
        strokeLinecap="round" className="-rotate-90 origin-center transition-all duration-1000 ease-out" />
    </svg>
  );
}

export function MiniLineChart({ color = "#517b4b", points, w = 180, h = 56 }: { color?: string, points: number[], w?: number, h?: number }) {
  if (!points || points.length === 0) return null;
  const max = Math.max(...points) * 1.1;
  const min = Math.min(...points) * 0.9;
  
  const xs = points.map((_, i) => 5 + (i / (points.length - 1)) * (w - 10));
  const ys = points.map(v => h - 5 - ((v - min) / (max - min)) * (h - 10));
  const d = xs.map((x, i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(" ");
  
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="block overflow-visible">
      {/* Glow/Shadow placeholder could go here */}
      <path d={d} fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      {/* Dots on last point */}
      <circle cx={xs[xs.length-1]} cy={ys[ys.length-1]} r="3" fill="#fff" stroke={color} strokeWidth="2" />
    </svg>
  );
}

export function BarChart({ values, color = "#ffffff" }: { values: number[], color?: string }) {
  if (!values || values.length === 0) return null;
  const max = Math.max(...values);
  return (
    <svg width="110" height="44" viewBox="0 0 110 44" className="block">
      {values.map((v, i) => {
        const h = (v / max) * 36;
        return (
          <rect 
            key={i} 
            x={8 + i * 14} 
            y={44 - h - 2} 
            width="10" 
            height={h} 
            rx="3"
            fill={i === values.length - 1 ? color : color} 
            className={cn("transition-all duration-500", i !== values.length - 1 && "opacity-40")}
          />
        );
      })}
    </svg>
  );
}
