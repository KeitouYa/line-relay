"use client";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useTranslations } from "@/lib/i18n";

type Props = { message: string; onRetry: () => void };

export function ErrorPanel({ message, onRetry }: Props) {
  const { t } = useTranslations();

  return (
    <Card className="p-6 mt-8 text-center">
      <div className="text-4xl mb-3">😅</div>
      <div className="text-base mb-2">{t("relayFailed")}</div>
      <div className="text-sm text-muted-foreground mb-4">{message}</div>
      <Button onClick={onRetry} variant="outline">
        {t("retry")}
      </Button>
    </Card>
  );
}
