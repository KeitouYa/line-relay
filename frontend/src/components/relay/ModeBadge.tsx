"use client";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useTranslations } from "@/lib/i18n";

type Props = { mode: string };

const MODE_STYLES: Record<string, string> = {
  seed: "bg-gray-100 text-gray-700 border-gray-200",
  "follow-up": "bg-blue-100 text-blue-700 border-blue-200",
  "keyword-trigger": "bg-green-100 text-green-700 border-green-200",
  twist: "bg-orange-100 text-orange-700 border-orange-200",
  break: "bg-purple-100 text-purple-700 border-purple-200",
  fallback: "bg-gray-100 text-gray-500 border-gray-200",
  unknown: "bg-gray-100 text-gray-500 border-gray-200",
};

export function ModeBadge({ mode }: Props) {
  const { t } = useTranslations();
  const MODE_LABELS: Record<string, string> = {
    seed: t("modeSeed"),
    fallback: t("modeFallback"),
    "follow-up": t("modeFollowUp"),
    "keyword-trigger": t("modeKeywordTrigger"),
    twist: t("modeTwist"),
    break: t("modeBreak"),
  };
  const style = MODE_STYLES[mode] || MODE_STYLES.unknown;
  const label = MODE_LABELS[mode] || mode;
  return (
    <Badge variant="outline" className={cn("text-xs font-normal", style)}>
      {label}
    </Badge>
  );
}
