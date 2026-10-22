import React, { useEffect, useRef } from 'react';
import { LexicalComposer } from '@lexical/react/LexicalComposer';
import { RichTextPlugin } from '@lexical/react/LexicalRichTextPlugin';
import { ContentEditable } from '@lexical/react/LexicalContentEditable';
import { HistoryPlugin } from '@lexical/react/LexicalHistoryPlugin';
import { ListPlugin } from '@lexical/react/LexicalListPlugin';
import { OnChangePlugin } from '@lexical/react/LexicalOnChangePlugin';
import { LexicalErrorBoundary } from '@lexical/react/LexicalErrorBoundary';
import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import { $generateHtmlFromNodes, $generateNodesFromDOM } from '@lexical/html';
import {
  $createParagraphNode,
  $getRoot,
  $getSelection,
  $insertNodes,
  $isRangeSelection,
  COMMAND_PRIORITY_HIGH,
  FORMAT_TEXT_COMMAND,
  PASTE_COMMAND,
} from 'lexical';
import { HeadingNode, QuoteNode } from '@lexical/rich-text';
import {
  $isListNode,
  INSERT_ORDERED_LIST_COMMAND,
  INSERT_UNORDERED_LIST_COMMAND,
  ListItemNode,
  ListNode,
  REMOVE_LIST_COMMAND,
} from '@lexical/list';
import { Bold, Italic, Underline, List, ListOrdered } from 'lucide-react';
import { cleanDescriptionHtml } from '@/lib/cleanHtml';

interface LexicalHtmlEditorProps {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
}

// No class names here on purpose: they would be saved into the description
// HTML. Lists and paragraphs are styled by the `.rich-text` CSS instead, the
// same way on the product page and in this editor.
const theme = {
  text: {
    bold: 'font-bold',
    italic: 'italic',
    underline: 'underline',
  },
};

const buttonClass = 'h-8 w-8 inline-flex items-center justify-center rounded hover:bg-muted';

const Toolbar: React.FC = () => {
  const [editor] = useLexicalComposerContext();

  // Second click on the same list button turns the list back into paragraphs.
  const toggleList = (type: 'bullet' | 'number') => {
    let inSameList = false;
    editor.getEditorState().read(() => {
      const selection = $getSelection();
      if (!$isRangeSelection(selection)) return;
      const list = selection.anchor.getNode().getParents().find($isListNode);
      inSameList = Boolean(list && list.getListType() === type);
    });
    if (inSameList) {
      editor.dispatchCommand(REMOVE_LIST_COMMAND, undefined);
    } else {
      editor.dispatchCommand(type === 'bullet' ? INSERT_UNORDERED_LIST_COMMAND : INSERT_ORDERED_LIST_COMMAND, undefined);
    }
  };

  // onMouseDown + preventDefault keeps the text selection in the editor.
  const keepFocus = (e: React.MouseEvent) => e.preventDefault();

  return (
    <div className="flex items-center gap-1 border-b border-border px-2 py-1.5 bg-muted/20 rounded-t-lg">
      <button type="button" className={buttonClass} onMouseDown={keepFocus} onClick={() => editor.dispatchCommand(FORMAT_TEXT_COMMAND, 'bold')} title="Bold">
        <Bold size={14} />
      </button>
      <button type="button" className={buttonClass} onMouseDown={keepFocus} onClick={() => editor.dispatchCommand(FORMAT_TEXT_COMMAND, 'italic')} title="Italic">
        <Italic size={14} />
      </button>
      <button type="button" className={buttonClass} onMouseDown={keepFocus} onClick={() => editor.dispatchCommand(FORMAT_TEXT_COMMAND, 'underline')} title="Underline">
        <Underline size={14} />
      </button>
      <button type="button" className={buttonClass} onMouseDown={keepFocus} onClick={() => toggleList('bullet')} title="Bullet list">
        <List size={14} />
      </button>
      <button type="button" className={buttonClass} onMouseDown={keepFocus} onClick={() => toggleList('number')} title="Numbered list">
        <ListOrdered size={14} />
      </button>
    </div>
  );
};

/**
 * Loads `html` into the editor — but only when it came from outside (a
 * different product opened). Our own edits echo back through `value`; loading
 * those again would rebuild the editor on every keystroke.
 */
const HtmlValuePlugin: React.FC<{ html: string; lastEmitted: React.MutableRefObject<string | null> }> = ({ html, lastEmitted }) => {
  const [editor] = useLexicalComposerContext();

  useEffect(() => {
    if (lastEmitted.current !== null && html === lastEmitted.current) return;
    editor.update(() => {
      const dom = new DOMParser().parseFromString(cleanDescriptionHtml(html || '') || '<p></p>', 'text/html');
      const nodes = $generateNodesFromDOM(editor, dom);
      const root = $getRoot();
      root.clear();
      root.select();
      $insertNodes(nodes);
      if (root.getChildrenSize() === 0) {
        root.append($createParagraphNode());
      }
    });
  }, [editor, html, lastEmitted]);

  return null;
};

/**
 * Pasting keeps only structure — paragraphs, line breaks, bold, italic,
 * underline and lists. Fonts, colours, sizes, backgrounds, classes and
 * links from the source page are dropped.
 */
const CleanPastePlugin: React.FC = () => {
  const [editor] = useLexicalComposerContext();

  useEffect(() => {
    return editor.registerCommand(
      PASTE_COMMAND,
      (event) => {
        const clipboard = (event as ClipboardEvent).clipboardData;
        const html = clipboard?.getData('text/html');
        if (!clipboard || !html) return false; // plain text: default paste is already unstyled
        event.preventDefault();
        const clean = cleanDescriptionHtml(html);
        editor.update(() => {
          const dom = new DOMParser().parseFromString(clean || '<p></p>', 'text/html');
          const nodes = $generateNodesFromDOM(editor, dom);
          const selection = $getSelection();
          if ($isRangeSelection(selection)) selection.removeText();
          $insertNodes(nodes);
        });
        return true;
      },
      COMMAND_PRIORITY_HIGH,
    );
  }, [editor]);

  return null;
};

export const LexicalHtmlEditor: React.FC<LexicalHtmlEditorProps> = ({
  value,
  onChange,
  placeholder = 'Write product description...',
}) => {
  const lastEmitted = useRef<string | null>(null);

  const initialConfig = {
    namespace: 'product-description-editor',
    theme,
    onError(error: Error) {
      console.error(error);
    },
    nodes: [HeadingNode, QuoteNode, ListNode, ListItemNode],
  };

  return (
    <LexicalComposer initialConfig={initialConfig}>
      <div className="relative rounded-lg border border-border bg-white">
        <Toolbar />
        <div className="relative">
          <RichTextPlugin
            contentEditable={
              <ContentEditable className="rich-text min-h-[180px] px-3 py-2 text-sm outline-none" />
            }
            placeholder={
              <div className="pointer-events-none absolute left-3 top-2 text-sm text-muted-foreground">{placeholder}</div>
            }
            ErrorBoundary={LexicalErrorBoundary}
          />
        </div>
        <HistoryPlugin />
        <ListPlugin />
        <CleanPastePlugin />
        <HtmlValuePlugin html={value} lastEmitted={lastEmitted} />
        <OnChangePlugin
          ignoreSelectionChange
          onChange={(editorState, editor) => {
            editorState.read(() => {
              const html = cleanDescriptionHtml($generateHtmlFromNodes(editor, null));
              if (html === lastEmitted.current) return;
              lastEmitted.current = html;
              onChange(html);
            });
          }}
        />
      </div>
    </LexicalComposer>
  );
};
