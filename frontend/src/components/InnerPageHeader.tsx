'use client';

import { ArrowLeft } from 'lucide-react';
import Button from '@/components/button/Button';
import { useTranslations } from '@/i18n/use-translations';

interface InnerPageHeaderProps {
  onBack: () => void;
  children?: React.ReactNode;
}

export default function InnerPageHeader({ onBack, children }: InnerPageHeaderProps) {
  const { t } = useTranslations();

  return (
    <header className="flex items-center bg-blueberry-700 px-4 py-4 md:px-6 text-white shadow-md">
      <div className="flex w-full min-w-0 items-start gap-3 md:items-center">
        <Button
          variant="light"
          fill={false}
          size="icon"
          onClick={onBack}
          className="flex items-center justify-center bg-white/20 hover:bg-white/30"
          aria-label={t('common.back')}
        >
          <ArrowLeft size={22} />
        </Button>
        <div className="flex min-w-0 flex-1 flex-wrap items-center justify-between gap-x-3 gap-y-2">{children}</div>
      </div>
    </header>
  );
}
