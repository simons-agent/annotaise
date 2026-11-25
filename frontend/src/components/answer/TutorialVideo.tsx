'use client';

import { useEffect, useState } from 'react';
import { ChevronDown, PlayCircle } from 'lucide-react';
import { useTranslations } from '@/i18n/use-translations';

type TutorialVideoProps = {
  videoId: string;
  /** Initial state: open until the annotator has submitted a first record. */
  defaultOpen: boolean;
};

// Collapsible tutorial video above the guide. youtube-nocookie.com is YouTube's
// privacy-enhanced mode: no tracking cookies until the viewer presses play.
export default function TutorialVideo({ videoId, defaultOpen }: TutorialVideoProps) {
  const { t } = useTranslations();
  const [open, setOpen] = useState(defaultOpen);
  // Follow the default when it changes (e.g. progress loads after the guide).
  useEffect(() => setOpen(defaultOpen), [defaultOpen]);

  return (
    <div className="rounded-lg border border-blueberry-700-25 bg-blueberry-700-15">
      <button
        type="button"
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-semibold text-blueberry-700"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <PlayCircle className="h-4 w-4 shrink-0" />
        <span className="flex-1">{t('video.title')}</span>
        <ChevronDown className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open ? (
        <div className="px-3 pb-3">
          <div className="relative w-full overflow-hidden rounded-md" style={{ paddingTop: '56.25%' }}>
            <iframe
              className="absolute inset-0 h-full w-full"
              src={`https://www.youtube-nocookie.com/embed/${videoId}?rel=0`}
              title={t('video.iframeTitle')}
              allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture; fullscreen"
              referrerPolicy="strict-origin-when-cross-origin"
              allowFullScreen
              loading="lazy"
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}
