import type { ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useTranslations } from '@/i18n/use-translations';
import { cn } from '@/lib/utils';

// A line holding only this comment splits a context text: what follows it is
// rendered inside a collapsed <details>. Only the first such line splits.
const MORE_MARKER_LINE = /^[ \t]*<!-- more -->[ \t]*\r?$/m;

function MoreDetails({ children }: { children: ReactNode }) {
  const { t } = useTranslations();
  return (
    <details className="mt-3">
      <summary className="cursor-pointer font-medium text-blueberry-700">{t('context.moreDetails')}</summary>
      {children}
    </details>
  );
}

type MarkdownContentProps = {
  children: ReactNode;
  inline?: boolean;
  className?: string;
};

export default function MarkdownContent({ children, inline = false, className }: MarkdownContentProps) {
  const Wrapper = inline ? 'span' : 'div';
  const classes = cn(
    'prose prose-sm max-w-none prose-p:my-0 prose-a:text-blueberry-700 prose-a:visited:text-blueberry-700',
    className
  );

  if (typeof children !== 'string') {
    return className ? <Wrapper className={classes}>{children}</Wrapper> : <>{children}</>;
  }

  const marker = inline ? null : MORE_MARKER_LINE.exec(children);
  const head = marker ? children.slice(0, marker.index) : children;
  const tail = marker ? children.slice(marker.index + marker[0].length) : null;

  const markdown = (text: string) => (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={
        inline
          ? {
              p: ({ children: paragraphChildren }) => <span>{paragraphChildren}</span>,
            }
          : undefined
      }
    >
      {text}
    </ReactMarkdown>
  );

  return (
    <Wrapper className={classes}>
      {markdown(head)}
      {tail !== null ? <MoreDetails>{markdown(tail)}</MoreDetails> : null}
    </Wrapper>
  );
}
