/**
 * Option pickers for a product with several attributes (e.g. Color × Size).
 *
 * Every active variant carries its attribute values ("Color: Violet",
 * "Size: 2-6"). From those we build one picker per attribute, showing only the
 * options that some variant actually has, and resolve the shopper's picks back
 * to a single variant. All of this runs on data already in the product
 * response — no extra requests.
 */
import type { CatalogAttribute, CatalogMedia, CatalogVariant } from '@/services/api/catalog';

export interface OptionValue {
  key: string;
  label: string;
  /** AttributeValue ids behind this label (photos are tagged with these). */
  valueIds: string[];
}

export interface OptionGroup {
  key: string;
  name: string;
  isColour: boolean;
  values: OptionValue[];
}

export type Selection = Record<string, string>;

export const normaliseKey = (raw: unknown): string => String(raw ?? '').trim().toLowerCase();

export const isColourName = (name: string): boolean => /colou?r/i.test(name);

const FALLBACK_GROUP = '__variant';

const isInStock = (variant: CatalogVariant): boolean =>
  Boolean(variant.is_in_stock) || Number(variant.stock_quantity || 0) > 0;

/** The variant's picks, e.g. { color: 'violet', size: '2-6' }. */
export function variantSelection(variant: CatalogVariant, groups: OptionGroup[]): Selection {
  if (groups.length === 1 && groups[0].key === FALLBACK_GROUP) {
    return { [FALLBACK_GROUP]: variant.id };
  }
  const selection: Selection = {};
  for (const av of variant.attribute_values || []) {
    const groupKey = normaliseKey(av.attribute_name);
    if (groupKey && av.value) selection[groupKey] = normaliseKey(av.value);
  }
  return selection;
}

export function buildOptionGroups(
  variants: CatalogVariant[],
  attributes: CatalogAttribute[] = [],
): OptionGroup[] {
  const attrOrder = new Map<string, { order: number; values: Map<string, { order: number; id: string }> }>();
  attributes.forEach((attr, index) => {
    const values = new Map<string, { order: number; id: string }>();
    (attr.values || []).forEach((v, vIndex) => {
      values.set(normaliseKey(v.value), { order: Number(v.sort_order ?? vIndex) * 1000 + vIndex, id: v.id });
    });
    attrOrder.set(normaliseKey(attr.name), { order: Number(attr.sort_order ?? index) * 1000 + index, values });
  });

  const groups = new Map<string, OptionGroup>();
  for (const variant of variants) {
    for (const av of variant.attribute_values || []) {
      const groupKey = normaliseKey(av.attribute_name);
      const valueKey = normaliseKey(av.value);
      if (!groupKey || !valueKey) continue;
      let group = groups.get(groupKey);
      if (!group) {
        group = { key: groupKey, name: String(av.attribute_name).trim(), isColour: isColourName(av.attribute_name), values: [] };
        groups.set(groupKey, group);
      }
      let value = group.values.find((v) => v.key === valueKey);
      if (!value) {
        value = { key: valueKey, label: String(av.value).trim(), valueIds: [] };
        group.values.push(value);
      }
      const ids = [av.id, attrOrder.get(groupKey)?.values.get(valueKey)?.id];
      for (const id of ids) {
        if (id && !value.valueIds.includes(String(id))) value.valueIds.push(String(id));
      }
    }
  }

  // Products whose variants have no attributes: one picker by variant name.
  if (groups.size === 0) {
    const named = variants.filter((v) => v.name && v.name !== v.sku);
    if (variants.length < 2 || named.length === 0) return [];
    return [{
      key: FALLBACK_GROUP,
      name: 'Options',
      isColour: false,
      values: variants.map((v) => ({ key: v.id, label: v.name || v.sku, valueIds: [] })),
    }];
  }

  const valueOrder = (groupKey: string, value: OptionValue, fallback: number) =>
    attrOrder.get(groupKey)?.values.get(value.key)?.order ?? 1e9 + fallback;

  const list = Array.from(groups.values());
  for (const group of list) {
    const firstSeen = new Map(group.values.map((v, i) => [v.key, i]));
    group.values.sort((a, b) => valueOrder(group.key, a, firstSeen.get(a.key)!) - valueOrder(group.key, b, firstSeen.get(b.key)!));
  }
  // Colour first (it changes the photos), then admin order.
  const groupOrder = (g: OptionGroup, i: number) => (g.isColour ? -1e12 : 0) + (attrOrder.get(g.key)?.order ?? 1e9 + i);
  const firstSeenGroup = new Map(list.map((g, i) => [g.key, i]));
  return list.sort((a, b) => groupOrder(a, firstSeenGroup.get(a.key)!) - groupOrder(b, firstSeenGroup.get(b.key)!));
}

const matches = (candidate: Selection, wanted: Selection) =>
  Object.entries(wanted).every(([k, v]) => candidate[k] === v);

export function findVariant(
  variants: CatalogVariant[],
  groups: OptionGroup[],
  selection: Selection,
): CatalogVariant | null {
  if (!groups.length) return null;
  return variants.find((variant) => {
    const own = variantSelection(variant, groups);
    return groups.every((g) => own[g.key] === selection[g.key]);
  }) || null;
}

/**
 * Can `value` of `groupKey` be bought, given the other picks?
 * exists: some variant has it with the other picks; inStock: one of those has stock.
 */
export function optionState(
  variants: CatalogVariant[],
  groups: OptionGroup[],
  selection: Selection,
  groupKey: string,
  valueKey: string,
): { exists: boolean; inStock: boolean } {
  const wanted: Selection = { ...selection, [groupKey]: valueKey };
  let exists = false;
  for (const variant of variants) {
    if (!matches(variantSelection(variant, groups), wanted)) continue;
    exists = true;
    if (isInStock(variant)) return { exists, inStock: true };
  }
  return { exists, inStock: false };
}

/**
 * The shopper picked `valueKey` for `groupKey`. Keep their other picks where a
 * variant allows it; otherwise move them to the closest in-stock combination
 * (so picking a colour never leaves the page on an impossible size).
 */
export function pickOption(
  variants: CatalogVariant[],
  groups: OptionGroup[],
  current: Selection,
  groupKey: string,
  valueKey: string,
): Selection {
  const candidates = variants
    .map((variant) => ({ variant, sel: variantSelection(variant, groups) }))
    .filter(({ sel }) => sel[groupKey] === valueKey);
  if (!candidates.length) return { ...current, [groupKey]: valueKey };

  const score = ({ variant, sel }: { variant: CatalogVariant; sel: Selection }) => {
    let s = isInStock(variant) ? 1000 : 0;
    groups.forEach((g, i) => {
      if (g.key !== groupKey && sel[g.key] === current[g.key]) s += 100 - i;
    });
    if (variant.is_default) s += 1;
    return s;
  };
  const best = candidates.reduce((a, b) => (score(b) > score(a) ? b : a));
  return { ...best.sel };
}

/**
 * Photos for the chosen colour: its tagged photos first, then photos tagged
 * with no colour. A colour with no photos of its own shows the untagged ones
 * (or everything, if nothing is untagged).
 */
export function mediaForColour(media: CatalogMedia[], colourValueIds: string[] | null): CatalogMedia[] {
  const sorted = [...media].sort((a, b) => Number(a.sort_order || 0) - Number(b.sort_order || 0));
  if (!colourValueIds || colourValueIds.length === 0) return sorted;
  const ids = new Set(colourValueIds.map(String));
  const own = sorted.filter((m) => m.attribute_value && ids.has(String(m.attribute_value)));
  const shared = sorted.filter((m) => !m.attribute_value);
  if (own.length) return [...own, ...shared];
  return shared.length ? shared : sorted;
}

/** Swatch colours for common jewellery colour names. Unknown names get no dot. */
const SWATCHES: Record<string, string> = {
  'mustard yellow': '#d4a017',
  mustard: '#d4a017',
  yellow: '#f2c94c',
  violet: '#7f3fbf',
  purple: '#6b2fa0',
  'emerald green': '#1f8a5b',
  emerald: '#1f8a5b',
  'malachite green': '#0b6e4f',
  malachite: '#0b6e4f',
  green: '#2e7d32',
  'amber orange': '#f39c12',
  amber: '#ffbf00',
  orange: '#ef7d1a',
  fuchsia: '#d6249f',
  pink: '#e86fa4',
  'rose pink': '#e8789a',
  magenta: '#c2185b',
  beige: '#e3d3b4',
  ivory: '#f4efe1',
  cream: '#f3e9d2',
  white: '#ffffff',
  black: '#111111',
  red: '#c62828',
  maroon: '#7b1e2b',
  'ruby red': '#9b111e',
  blue: '#1e5bb8',
  'navy blue': '#1f2f5c',
  'royal blue': '#2747a8',
  'sky blue': '#76b5e8',
  turquoise: '#30b5b0',
  teal: '#127a7a',
  gold: '#c9a227',
  golden: '#c9a227',
  silver: '#c0c0c0',
  'rose gold': '#b76e79',
  peach: '#f6b48f',
  brown: '#7a4a26',
  grey: '#8a8a8a',
  gray: '#8a8a8a',
  multicolour: 'conic-gradient(#e53935, #fbc02d, #43a047, #1e88e5, #8e24aa, #e53935)',
  multicolor: 'conic-gradient(#e53935, #fbc02d, #43a047, #1e88e5, #8e24aa, #e53935)',
};

export function swatchFor(label: string): string | null {
  return SWATCHES[normaliseKey(label)] ?? null;
}
