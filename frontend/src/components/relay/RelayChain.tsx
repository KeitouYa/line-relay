"use client";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { RelayNode } from "./RelayNode";
import type { RelayState } from "@/hooks/useRelaySSE";
import { useEffect, useState } from "react";
import { useTranslations } from "@/lib/i18n";

type Props = {
  state: RelayState;
  onCopy: () => void;
  onRegenerate: () => void;
};

export function RelayChain({ state, onCopy, onRegenerate }: Props) {
  const { t } = useTranslations();
  const { chain, status, rounds, startTime } = state;
  const [elapsed, setElapsed] = useState(0);

  // 加载中实时计时
  useEffect(() => {
    if (status !== "loading" || !startTime) return;
    const id = setInterval(() => {
      setElapsed((Date.now() - startTime) / 1000);
    }, 100);
    return () => clearInterval(id);
  }, [status, startTime]);

  if (chain.length === 0 && status !== "loading") return null;

  // chain[0] 是 seed (round 0),后面是 round 1...N
  const completedRounds = chain.length > 0 ? chain.length - 1 : 0;
  const showLoadingCard = status === "loading" && completedRounds < rounds;

  return (
    <div className="mt-8">
      {chain.map((node, i) => (
        <RelayNode
          key={`${node.round}-${node.quote_id}`}
          node={node}
          isLast={i === chain.length - 1 && !showLoadingCard}
        />
      ))}

      {showLoadingCard && (
        <div className="flex gap-4">
          <div className="flex flex-col items-center">
            <div className="w-3 h-3 rounded-full bg-muted animate-pulse mt-2" />
          </div>
          <Card className="flex-1 p-4 mb-4">
            <Skeleton className="h-3 w-32 mb-3" />
            <Skeleton className="h-5 w-full mb-2" />
            <Skeleton className="h-5 w-3/4" />
            <div className="text-xs text-muted-foreground mt-3">
              {t("thinking")} ({completedRounds + 1}/{rounds}) · {t("elapsed")}{" "}
              {elapsed.toFixed(1)}s
            </div>
          </Card>
        </div>
      )}

      {status === "done" && (
        <div className="flex gap-2 mt-4">
          <Button onClick={onCopy} variant="outline" className="flex-1">
            {t("copyChain")}
          </Button>
          <Button onClick={onRegenerate} variant="outline" className="flex-1">
            {t("regenerate")}
          </Button>
        </div>
      )}
    </div>
  );
}
