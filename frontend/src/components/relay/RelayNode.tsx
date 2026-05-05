"use client";

import { Card } from "@/components/ui/card";
import { ModeBadge } from "./ModeBadge";
import { useState } from "react";
import type { RelayNode as RelayNodeType } from "@/hooks/useRelaySSE";
import { useTranslations } from "@/lib/i18n";

type Props = { node: RelayNodeType; isLast?: boolean };

export function RelayNode({ node, isLast = false }: Props) {
  const { t } = useTranslations();
  const [expanded, setExpanded] = useState(false);
  const hasReason = node.reason && node.reason.trim().length > 0;

  return (
    <div className="flex gap-4">
      {/* 左侧时间轴 */}
      <div className="flex flex-col items-center">
        <div className="w-3 h-3 rounded-full bg-foreground mt-2" />
        {!isLast && <div className="w-0.5 flex-1 bg-border mt-1" />}
      </div>

      {/* 右侧卡片 */}
      <Card className="flex-1 p-4 mb-4">
        <div className="flex items-baseline justify-between mb-2 flex-wrap gap-2">
          <div className="text-xs uppercase tracking-wide text-muted-foreground font-medium">
            {node.movie_title}
            {node.movie_year && <span> · {node.movie_year}</span>}
          </div>
          <ModeBadge mode={node.mode} />
        </div>

        <div className="text-base font-medium leading-relaxed">
          &ldquo;{node.text}&rdquo;
        </div>

        {hasReason && (
          <div className="mt-3 pt-3 border-t border-dashed border-border">
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {expanded ? "\u25BE" : "\u25B8"} {t("aiReason")}
            </button>
            {expanded && (
              <div className="text-xs text-muted-foreground mt-2 leading-relaxed">
                {node.reason}
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
