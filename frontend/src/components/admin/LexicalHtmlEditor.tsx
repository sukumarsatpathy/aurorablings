import React, { useEffect } from 'react';
import { LexicalComposer } from '@lexical/react/LexicalComposer';
import { RichTextPlugin } from '@lexical/react/LexicalRichTextPlugin';
import { ContentEditable } from '@lexical/react/LexicalContentEditable';
import { HistoryPlugin } from '@lexical/react/LexicalHistoryPlugin';
import { OnChangePlugin } from '@lexical/react/LexicalOnChangePlugin';
import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import { $generateHtmlFromNodes, $generateNodesFromDOM } from '@lexical/html';
import { $createParagraphNode, $getRoot, $insertNodes, FORMAT_TEXT_COMMAND } from 'lexical';
import { HeadingNode, QuoteNode } from '@lexical/rich-text';
import { ListItemNode, ListNode, INSERT_ORDERED_LIST_COMMAND, INSERT_UNORDERED_LIST_COMMAND } from '@lexical/list';
import { Bold, Italic, Underline, List, ListOrdered } from 'lucide-react';

interface LexicalHtmlEditorProps {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
}

const theme = {
  paragraph: 'mb-2 text-sm leading-relaxed text-foreground',
  text: {
    bold: 'font-bold',
    italic: 'italic',
    underline: 'underline',
  },
};

const Toolbar: React.FC = () => {
  const [editor] = useLexicalComposerContext();
  return (
    <div className="flex items-center gap-1 border-b border-border px-2 py-1.5 bg-muted/20 rounded-t-lg">
      <button type="button" className="h-8 w-8 inline-flex items-center justify-center rounded hover:bg-muted" onClick={() => editor.dispatchCommand(FORMAT_TEXT_COMMAND, 'bold')} title="Bold">
        <Bold size={14} />
      </button>
      <button type="button" className="h-8 w-8 inline-flex items-center justify-center rounded hover:bg-muted" onClick={() => editor.dispatchCommand(FORMAT_TEXT_COMMAND, 'italic')} title="Italic">
        <Italic size={14} />
      </button>
      <button type="button" className="h-8 w-8 inline-flex items-center justify-center rounded hover:bg-muted" onClick={() => editor.dispatchCommand(FORMAT_TEXT_COMMAND, 'underline')} title="Underline">
        <Underline size={14} />
      </button>
      <button type="button" className="h-8 w-8 inline-flex items-center justify-center rounded hover:bg-muted" onClick={() => editor.dispatchCommand(INSERT_UNORDERED_LIST_COMMAND, undefined)} title="Bullet list">
        <List size={14} />
      </button>
      <button type="button" className="h-8 w-8 inline-flex items-center justify-center rounded hover:bg-muted" onClick={() => editor.dispatchCommand(INSERT_ORDERED_LIST_COMMAND, undefined)} title="Numbered list">
        <ListOrdered size={14} />
      </button>
    </div>
  );
};

const HtmlValuePlugin: React.FC<{ html: string }> = ({ html }) => {
  const [editor] = useLexicalComposerContext();

  useEffect(() => {
    editor.update(() => {
      const parser = new DOMParser();
      const dom = parser.parseFromString(html || '<p></p>', 'text/html');
      const nodes = $generateNodesFromDOM(editor, dom);
      const root = $getRoot();
      root.clear();
      $insertNodes(nodes);
      if (root.getChildrenSize() === 0) {
        root.append($createParagraphNode());
      }
    });
  }, [editor, html]);

  return null;
};

export const LexicalHtmlEditor: React.FC<LexicalHtmlEditorProps> = ({
  value,
  onChange,
  placeholder = 'Write product description...',
}) => {
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
      <div className="rounded-lg border border-border bg-white">
        <Toolbar />
        <RichTextPlugin
          contentEditable={
            <ContentEditable className="min-h-[180px] px-3 py-2 text-sm outline-none" />
          }
          placeholder={<div className="px-3 py-2 text-sm text-muted-foreground">{placeholder}</div>}
          ErrorBoundary={() => null}
        />
        <HistoryPlugin />
        <HtmlValuePlugin html={value} />
        <OnChangePlugin
          onChange={(editorState, editor) => {
            editorState.read(() => {
              const html = $generateHtmlFromNodes(editor, null);
              onChange(html);
            });
          }}
        />
      </div>
    </LexicalComposer>
  );
};
