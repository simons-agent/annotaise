import { renderToStaticMarkup } from 'react-dom/server';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { translations } from '@/i18n/translations';
import MarkdownContent from './MarkdownContent';

let language: 'pt-BR' | 'en' = 'pt-BR';

vi.mock('@/i18n/use-translations', () => ({
  useTranslations: () => ({
    language,
    locale: language === 'en' ? 'en-US' : 'pt-BR',
    t: (key: string) => translations[language][key] ?? translations['pt-BR'][key] ?? key,
  }),
}));

const MARKER = '<!-- more -->';
const render = (text: string, inline = false) =>
  renderToStaticMarkup(<MarkdownContent inline={inline}>{text}</MarkdownContent>);

beforeEach(() => {
  language = 'pt-BR';
});

describe('MarkdownContent collapsible marker', () => {
  it('renders details block after marker', () => {
    const html = render(`# CWE-1\n\nShort part.\n\n${MARKER}\n\n## Extra\n\nLong part.`);
    expect(html).toContain('<details');
    expect(html).not.toContain('<details open');
    expect(html).toMatch(/<summary[^>]*>Mais detalhes<\/summary>/);
    const [before, after] = html.split('<details');
    expect(before).toContain('Short part.');
    expect(before).not.toContain('Long part.');
    expect(after).toContain('Long part.');
    expect(after).toContain('<h2>Extra</h2>');
    expect(html).not.toContain('more -->');
  });

  it('no marker → unchanged output', () => {
    const html = render('# Title\n\nJust **text**.');
    expect(html).not.toContain('<details');
    expect(html).toContain('<h1>Title</h1>');
    expect(html).toContain('<strong>text</strong>');
  });

  it('splits only on the first marker line', () => {
    const html = render(`A\n\n${MARKER}\n\nB\n\n${MARKER}\n\nC`);
    expect(html.match(/<details/g)).toHaveLength(1);
    expect(html.indexOf('<details')).toBeGreaterThan(html.indexOf('>A<'));
    const inside = html.slice(html.indexOf('<details'));
    expect(inside).toContain('B');
    expect(inside).toContain('C');
  });

  it('does not split on a marker embedded in a line', () => {
    const html = render(`A text ${MARKER} more text`);
    expect(html).not.toContain('<details');
  });

  it('summary label follows language (pt-BR / en)', () => {
    const text = `A\n\n${MARKER}\n\nB`;
    expect(render(text)).toMatch(/<summary[^>]*>Mais detalhes<\/summary>/);
    language = 'en';
    expect(render(text)).toMatch(/<summary[^>]*>More details<\/summary>/);
  });

  it('inline mode never splits', () => {
    const html = render(`A\n\n${MARKER}\n\nB`, true);
    expect(html).not.toContain('<details');
  });
});

describe('MarkdownContent links', () => {
  // An annotator who follows the official-entry link must not lose the
  // half-answered item, so record links open in a new tab.
  it('opens links before and after the marker in a new tab', () => {
    const html = render(
      `Entry: [https://cwe.mitre.org/data/definitions/352.html](https://cwe.mitre.org/data/definitions/352.html)\n\n${MARKER}\n\nSee https://www.cve.org/CVERecord?id=CVE-2024-0001`
    );
    const anchors = html.match(/<a [^>]*>/g) ?? [];
    expect(anchors).toHaveLength(2);
    for (const a of anchors) {
      expect(a).toContain('target="_blank"');
      expect(a).toContain('rel="noopener noreferrer"');
    }
  });

  it('inline links open in a new tab too', () => {
    const html = render('[x](https://example.org)', true);
    expect(html).toMatch(/<a [^>]*target="_blank"[^>]*>/);
  });
});
