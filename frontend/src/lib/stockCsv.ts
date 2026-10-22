/**
 * Reading a supplier sheet for Bulk Receive: SKU + quantity per line.
 *
 * Accepts comma, semicolon or tab separated text (what Excel / Google Sheets
 * export), with or without a header row. With a header, the SKU column is the
 * one named like "sku" and the quantity column one named like "qty"/"quantity";
 * without one, the first two columns are used.
 */

export interface CsvLine {
  /** 1-based line number in the file, for error messages. */
  line: number;
  sku: string;
  quantity: number;
}

export interface CsvProblem {
  line: number;
  text: string;
  reason: string;
}

export interface ParsedStockCsv {
  lines: CsvLine[];
  problems: CsvProblem[];
}

const splitRow = (row: string, delimiter: string): string[] => {
  const cells: string[] = [];
  let current = '';
  let quoted = false;
  for (let i = 0; i < row.length; i += 1) {
    const ch = row[i];
    if (quoted) {
      if (ch === '"' && row[i + 1] === '"') {
        current += '"';
        i += 1;
      } else if (ch === '"') {
        quoted = false;
      } else {
        current += ch;
      }
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === delimiter) {
      cells.push(current);
      current = '';
    } else {
      current += ch;
    }
  }
  cells.push(current);
  return cells.map((c) => c.trim());
};

const detectDelimiter = (sample: string): string => {
  const counts = [',', ';', '\t'].map((d) => [d, sample.split(d).length - 1] as const);
  counts.sort((a, b) => b[1] - a[1]);
  return counts[0][1] > 0 ? counts[0][0] : ',';
};

export function parseStockCsv(text: string): ParsedStockCsv {
  const rows = text.replace(/^\uFEFF/, '').split(/\r\n|\n|\r/);
  const firstReal = rows.find((r) => r.trim()) || '';
  const delimiter = detectDelimiter(firstReal);

  let skuCol = 0;
  let qtyCol = 1;
  let startIndex = 0;
  const firstIndex = rows.findIndex((r) => r.trim());
  if (firstIndex >= 0) {
    const header = splitRow(rows[firstIndex], delimiter).map((h) => h.toLowerCase());
    const skuAt = header.findIndex((h) => /\bsku\b|^code$|item code/.test(h));
    const qtyAt = header.findIndex((h) => /^(qty|quantity|quantities|pcs|pieces|units|count)\b/.test(h) || /\bqty\b|quantity/.test(h));
    if (skuAt >= 0 || qtyAt >= 0) {
      if (skuAt >= 0) skuCol = skuAt;
      if (qtyAt >= 0) qtyCol = qtyAt;
      startIndex = firstIndex + 1;
    }
  }

  const lines: CsvLine[] = [];
  const problems: CsvProblem[] = [];
  for (let i = startIndex; i < rows.length; i += 1) {
    const raw = rows[i];
    if (!raw.trim()) continue;
    const cells = splitRow(raw, delimiter);
    const sku = (cells[skuCol] || '').trim();
    const qtyText = (cells[qtyCol] || '').replace(/[,\s]/g, '');
    if (!sku && !qtyText) continue;
    if (!sku) {
      problems.push({ line: i + 1, text: raw, reason: 'No SKU' });
      continue;
    }
    if (!/^\d+$/.test(qtyText) || Number(qtyText) <= 0) {
      problems.push({ line: i + 1, text: raw, reason: qtyText ? `"${qtyText}" isn't a whole number above 0` : 'No quantity' });
      continue;
    }
    lines.push({ line: i + 1, sku, quantity: Number(qtyText) });
  }
  return { lines, problems };
}
