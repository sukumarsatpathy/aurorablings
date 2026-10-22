/**
 * Reduce rich text (pasted from a website, Word, Google Docs, or saved by the
 * editor) to plain structure: paragraphs, line breaks, bold, italic,
 * underline and bullet/numbered lists. Every attribute — style, class, font,
 * colour, links — is dropped, so descriptions always look like the site.
 */

const DROP = new Set([
  'script', 'style', 'meta', 'link', 'title', 'head', 'noscript', 'iframe', 'object', 'embed',
  'svg', 'canvas', 'img', 'picture', 'video', 'audio', 'button', 'input', 'select', 'textarea',
  'form', 'template', 'hr',
]);

const BLOCKS = new Set([
  'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'section', 'article', 'header',
  'footer', 'main', 'aside', 'nav', 'pre', 'table', 'thead', 'tbody', 'tfoot', 'tr', 'td', 'th',
  'dl', 'dt', 'dd', 'figure', 'figcaption', 'address', 'center',
]);
const BLOCK_SELECTOR = [...BLOCKS, 'ul', 'ol', 'li'].join(',');

type Mark = 'strong' | 'em' | 'u';

/** Bold / italic / underline as expressed by the tag and its inline style. */
function marksFor(el: HTMLElement): { add: Mark[]; boldOff: boolean } {
  const tag = el.tagName.toLowerCase();
  const style = el.style;
  const weight = style?.fontWeight || '';
  const numericWeight = Number(weight);
  const boldOff = weight === 'normal' || (numericWeight > 0 && numericWeight < 600);
  const add: Mark[] = [];
  if (((tag === 'b' || tag === 'strong') && !boldOff) || weight === 'bold' || weight === 'bolder' || numericWeight >= 600) add.push('strong');
  if (tag === 'i' || tag === 'em' || style?.fontStyle === 'italic') add.push('em');
  if (tag === 'u' || /underline/.test(style?.textDecoration || style?.textDecorationLine || '')) add.push('u');
  return { add, boldOff };
}

function cleanChildren(source: Node, target: Node, doc: Document, active: Set<Mark>, inList: boolean): void {
  source.childNodes.forEach((child) => cleanNode(child, target, doc, active, inList));
}

function cleanNode(node: Node, target: Node, doc: Document, active: Set<Mark>, inList: boolean): void {
  if (node.nodeType === Node.TEXT_NODE) {
    const text = node.textContent || '';
    // Formatting whitespace between list items / blocks isn't content.
    if (inList && !text.trim()) return;
    target.appendChild(doc.createTextNode(text));
    return;
  }
  if (node.nodeType !== Node.ELEMENT_NODE) return;

  const el = node as HTMLElement;
  const tag = el.tagName.toLowerCase();
  if (DROP.has(tag) || tag.includes(':')) {
    // <o:p> etc. from Word: keep their text, drop the tag.
    if (tag.includes(':')) cleanChildren(el, target, doc, active, inList);
    return;
  }

  if (tag === 'br') {
    target.appendChild(doc.createElement('br'));
    return;
  }

  if (tag === 'ul' || tag === 'ol') {
    const list = doc.createElement(tag);
    cleanChildren(el, list, doc, new Set(), true);
    if (list.childNodes.length) target.appendChild(list);
    return;
  }

  if (tag === 'li') {
    const li = doc.createElement('li');
    cleanChildren(el, li, doc, new Set(), false);
    target.appendChild(li);
    return;
  }

  if (BLOCKS.has(tag)) {
    // A wrapper around other blocks just passes them through.
    if (el.querySelector(BLOCK_SELECTOR)) {
      cleanChildren(el, target, doc, active, inList);
      return;
    }
    const p = doc.createElement('p');
    cleanChildren(el, p, doc, new Set(), false);
    target.appendChild(inList ? wrapInLi(p, doc) : p);
    return;
  }

  // Inline element (span, a, font, b, strong, i, em, u, …): keep only the marks.
  const { add } = marksFor(el);
  const fresh = add.filter((mark) => !active.has(mark));
  let into: Node = target;
  const nextActive = new Set(active);
  for (const mark of fresh) {
    const wrapper = doc.createElement(mark);
    into.appendChild(wrapper);
    into = wrapper;
    nextActive.add(mark);
  }
  cleanChildren(el, into, doc, nextActive, inList);
}

function wrapInLi(p: HTMLElement, doc: Document): HTMLElement {
  const li = doc.createElement('li');
  while (p.firstChild) li.appendChild(p.firstChild);
  return li;
}

const isBlank = (el: Element) => !(el.textContent || '').replace(/\u00a0/g, ' ').trim() && !el.querySelector('br');

export function cleanDescriptionHtml(html: string): string {
  if (!html || typeof DOMParser === 'undefined') return html || '';
  const source = new DOMParser().parseFromString(html, 'text/html');
  const doc = document.implementation.createHTMLDocument('');
  const out = doc.createElement('div');
  cleanChildren(source.body, out, doc, new Set(), false);

  // Loose text/inline at the top level goes into paragraphs.
  const result = doc.createElement('div');
  let loose: HTMLElement | null = null;
  out.childNodes.forEach((child) => {
    const isBlock = child.nodeType === Node.ELEMENT_NODE && ['p', 'ul', 'ol'].includes((child as Element).tagName.toLowerCase());
    if (isBlock) {
      loose = null;
      result.appendChild(child.cloneNode(true));
      return;
    }
    if (child.nodeType === Node.TEXT_NODE && !(child.textContent || '').trim() && !loose) return;
    if (!loose) {
      loose = doc.createElement('p');
      result.appendChild(loose);
    }
    loose.appendChild(child.cloneNode(true));
  });

  // Drop empty list items, and collapse runs of empty paragraphs (Word loves them).
  result.querySelectorAll('li').forEach((li) => {
    if (isBlank(li)) li.remove();
  });
  result.querySelectorAll('ul,ol').forEach((list) => {
    if (!list.children.length) list.remove();
  });
  let previousBlank = true; // also trims leading blanks
  Array.from(result.children).forEach((child) => {
    const blank = child.tagName.toLowerCase() === 'p' && (isBlank(child) || (child.childNodes.length === 1 && child.firstChild?.nodeName === 'BR'));
    if (blank && previousBlank) child.remove();
    previousBlank = blank;
  });
  while (result.lastElementChild && result.lastElementChild.tagName === 'P' && (isBlank(result.lastElementChild) || result.lastElementChild.textContent === '')) {
    result.lastElementChild.remove();
  }

  return result.innerHTML;
}
