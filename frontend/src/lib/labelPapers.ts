/**
 * The two barcode label rolls (mirrors backend apps/catalog/label_papers.py).
 *
 * Each category picks one; label downloads are split by paper because only one
 * roll is in the printer at a time. Both carry the same columns (Barcode, Name,
 * SKU, MRP) — the label printer app's template places them on the roll.
 */
export type LabelPaperKey = 'packed_sticker' | 'tail_tag';

export interface LabelPaper {
  key: LabelPaperKey;
  name: string;
  widthMm: number;
  heightMm: number;
  size: string;
  material: string;
  use: string;
}

export const LABEL_PAPERS: LabelPaper[] = [
  {
    key: 'packed_sticker',
    name: 'Packed sticker',
    widthMm: 40,
    heightMm: 15,
    size: '40 × 15 mm',
    material: 'Transparent, waterproof',
    use: 'Packed display — stick on the white side of the pouch or box.',
  },
  {
    key: 'tail_tag',
    name: 'Tail tag',
    widthMm: 100,
    heightMm: 15,
    size: '100 × 15 mm · 64 mm head',
    material: 'White, waterproof, non-tearable',
    use: 'Loose display — the head folds into two 32 × 15 mm faces (barcode / name + price); the tail loops through the piece.',
  },
];

export const DEFAULT_LABEL_PAPER: LabelPaperKey = 'packed_sticker';

export const labelPaper = (key?: string | null): LabelPaper =>
  LABEL_PAPERS.find((p) => p.key === key) || LABEL_PAPERS[0];
