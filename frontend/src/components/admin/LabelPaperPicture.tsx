import React from 'react';

import type { LabelPaperKey } from '@/lib/labelPapers';

/**
 * A to-scale drawing of a label roll's label, with sample content laid out the
 * way it prints, and its measurements. Drawn rather than photographed so it
 * shows exactly where the barcode, name and price go — which is the thing to
 * get right in the label printer app's template.
 */

// Thin bars of a sample barcode, as [x, width] in mm from the barcode's left.
const BARS = [
  [0, 0.5], [0.75, 0.25], [1.5, 0.5], [2.5, 0.25], [3, 0.75], [4.25, 0.25], [5, 0.5], [6, 0.25],
  [6.75, 0.75], [8, 0.25], [8.5, 0.5], [9.5, 0.25], [10, 0.75], [11.25, 0.25], [12, 0.5], [13, 0.25],
  [13.5, 0.75], [14.75, 0.25], [15.5, 0.5], [16.5, 0.25], [17, 0.75], [18.25, 0.25], [19, 0.5], [20, 0.75],
] as const;

const Barcode: React.FC<{ x: number; y: number; height: number; digits?: boolean }> = ({ x, y, height, digits = true }) => (
  <g>
    {BARS.map(([bx, w]) => (
      <rect key={bx} x={x + bx} y={y} width={w} height={height} fill="currentColor" />
    ))}
    {digits ? (
      <text x={x + 10.4} y={y + height + 2} fontSize={1.8} textAnchor="middle" fill="currentColor" fontFamily="ui-monospace, monospace">
        10000123
      </text>
    ) : null}
  </g>
);

const Dim: React.FC<{ x1: number; x2: number; y: number; label: string }> = ({ x1, x2, y, label }) => (
  <g className="text-muted-foreground" stroke="currentColor" strokeWidth={0.2}>
    <line x1={x1} y1={y} x2={x2} y2={y} />
    <line x1={x1} y1={y - 1} x2={x1} y2={y + 1} />
    <line x1={x2} y1={y - 1} x2={x2} y2={y + 1} />
    <text x={(x1 + x2) / 2} y={y - 1} fontSize={2.4} textAnchor="middle" fill="currentColor" stroke="none">
      {label}
    </text>
  </g>
);

const VDim: React.FC<{ x: number; y1: number; y2: number; label: string }> = ({ x, y1, y2, label }) => (
  <g className="text-muted-foreground" stroke="currentColor" strokeWidth={0.2}>
    <line x1={x} y1={y1} x2={x} y2={y2} />
    <line x1={x - 1} y1={y1} x2={x + 1} y2={y1} />
    <line x1={x - 1} y1={y2} x2={x + 1} y2={y2} />
    <text x={x - 1.5} y={(y1 + y2) / 2 + 0.8} fontSize={2.4} textAnchor="end" fill="currentColor" stroke="none">
      {label}
    </text>
  </g>
);

export const LabelPaperPicture: React.FC<{ paper: LabelPaperKey; className?: string }> = ({ paper, className }) => {
  if (paper === 'tail_tag') {
    // 100 × 15 mm: 64 mm head (two 32 mm faces) + 36 mm tail.
    return (
      <svg viewBox="-12 -6 116 26" className={className} role="img" aria-label="Tail tag, 100 by 15 millimetres, 64 millimetre head folding into two faces">
        <g className="text-foreground">
          <path
            d="M1.5 0 H62.5 Q64 0 64 1.5 V5.5 H98.5 Q100 5.5 100 7.5 Q100 9.5 98.5 9.5 H64 V13.5 Q64 15 62.5 15 H1.5 Q0 15 0 13.5 V1.5 Q0 0 1.5 0 Z"
            fill="white"
            stroke="currentColor"
            strokeOpacity={0.35}
            strokeWidth={0.3}
          />
          <line x1={32} y1={0.5} x2={32} y2={14.5} stroke="currentColor" strokeOpacity={0.5} strokeWidth={0.25} strokeDasharray="0.8 0.8" />
          {/* Face A: barcode */}
          <Barcode x={5.6} y={2.5} height={8} />
          {/* Face B: name + price */}
          <text x={35} y={5} fontSize={2.6} fontWeight={600} fill="currentColor">Jhumka Red L</text>
          <text x={35} y={8.4} fontSize={2} fill="currentColor" opacity={0.7}>ER-JH-021</text>
          <text x={35} y={12.4} fontSize={2.8} fontWeight={700} fill="currentColor">MRP ₹499</text>
          <text x={82} y={8.3} fontSize={1.8} textAnchor="middle" fill="currentColor" opacity={0.45}>tail</text>
        </g>
        <Dim x1={0} x2={64} y={-2.5} label="64 mm head" />
        <Dim x1={0} x2={100} y={18.5} label="100 mm" />
        <VDim x={-2} y1={0} y2={15} label="15 mm" />
        <g fontSize={1.8} textAnchor="middle" className="text-muted-foreground" fill="currentColor">
          <text x={16} y={-0.6}>face A · 32 mm</text>
          <text x={48} y={-0.6}>face B · 32 mm</text>
        </g>
      </svg>
    );
  }

  // 40 × 15 mm transparent sticker: name on top, barcode left, MRP right.
  return (
    <svg viewBox="-11 -3 56 25" className={className} role="img" aria-label="Packed sticker, 40 by 15 millimetres, transparent">
      <defs>
        <pattern id="lp-clear" width="2" height="2" patternUnits="userSpaceOnUse">
          <rect width="2" height="2" fill="#f4f4f5" />
          <rect width="1" height="1" fill="#e4e4e7" />
          <rect x="1" y="1" width="1" height="1" fill="#e4e4e7" />
        </pattern>
      </defs>
      <g className="text-foreground">
        <rect x={0} y={0} width={40} height={15} rx={1.2} fill="url(#lp-clear)" stroke="currentColor" strokeOpacity={0.35} strokeWidth={0.3} />
        <text x={2} y={3.2} fontSize={2.2} fontWeight={600} fill="currentColor">Jhumka Red L</text>
        <text x={38} y={3.2} fontSize={1.8} textAnchor="end" fill="currentColor" opacity={0.7}>ER-JH-021</text>
        <Barcode x={2.5} y={4.4} height={6.6} />
        <text x={33.5} y={7.6} fontSize={1.8} textAnchor="middle" fill="currentColor" opacity={0.7}>MRP</text>
        <text x={33.5} y={11} fontSize={3} fontWeight={700} textAnchor="middle" fill="currentColor">₹499</text>
      </g>
      <Dim x1={0} x2={40} y={20} label="40 mm" />
      <VDim x={-2} y1={0} y2={15} label="15 mm" />
    </svg>
  );
};

export default LabelPaperPicture;
