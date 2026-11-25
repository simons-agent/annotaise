'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ExternalLink } from 'lucide-react';

import { useTranslations } from '@/i18n/use-translations';
import { firstYoutubeId } from '@/modules/goal/goal';
import TutorialVideo from './TutorialVideo';

type GuidePanelProps = {
  // Labeling guide markdown; empty string renders the "no guide" placeholder.
  guideText: string;
  // When set, shows an "open in new tab" link to the full guide route.
  externalHref?: string;
  // The guide's first YouTube link is embedded above it; open by default when true.
  videoOpen?: boolean;
};

// Side panel that renders a labeling's annotation guide as markdown. Shared by
// the authenticated answer page and the public (anonymous) answer page.
export default function GuidePanel({ guideText, externalHref, videoOpen = true }: GuidePanelProps) {
  const { t } = useTranslations();
  const videoId = firstYoutubeId(guideText);

  return (
    <div className="h-full rounded-xl bg-white p-4 overflow-auto space-y-3">
      {externalHref ? (
        <div className="flex items-center justify-end gap-2">
          {/* Open the full guide route while preserving the current answer session. */}
          <span
            role="button"
            tabIndex={0}
            className="inline-flex items-center gap-1 text-sm text-primary underline underline-offset-2 cursor-pointer hover:opacity-80"
            onClick={() => window.open(externalHref, '_blank', 'noopener,noreferrer')}
          >
            {t('answer.openNewTab')}
            <ExternalLink className="h-3 w-3" />
          </span>
        </div>
      ) : null}

      <div className="mt-1 space-y-4">
        {videoId ? <TutorialVideo videoId={videoId} defaultOpen={videoOpen} /> : null}
        {guideText ? (
          <div className="prose prose-sm max-w-none text-gray-900">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{guideText}</ReactMarkdown>
          </div>
        ) : (
          <p className="text-sm text-gray-600">{t('answer.noGuide')}</p>
        )}
      </div>
    </div>
  );
}
