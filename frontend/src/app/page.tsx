"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useRelaySSE } from "@/hooks/useRelaySSE";
import { RelayChain } from "@/components/relay/RelayChain";
import { ErrorPanel } from "@/components/relay/ErrorPanel";
import { LangToggle } from "@/components/ui/LangToggle";
import { useTranslations } from "@/lib/i18n";

export default function Home() {
  const { t } = useTranslations();
  const [seed, setSeed] = useState("");
  const relay = useRelaySSE();

  const handleStart = () => {
    const trimmed = seed.trim();
    if (!trimmed) return;
    relay.start(trimmed, 5);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && relay.status !== "loading") {
      handleStart();
    }
  };

  const handleCopy = () => {
    const text = relay.chain
      .map((n) => `《${n.movie_title}》: "${n.text}"`)
      .join("\n");
    navigator.clipboard.writeText(text);
  };

  const handleRegenerate = () => {
    if (seed.trim()) {
      relay.start(seed.trim(), 5);
    }
  };

  return (
    <main className="min-h-screen px-4 py-12 sm:px-8 sm:py-16 flex flex-col">
      <div className="max-w-2xl mx-auto w-full flex-1">
        <header className="mb-8 flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
            <p className="text-sm text-muted-foreground mt-1">
              {t("subtitle")}
            </p>
          </div>
          <LangToggle />
        </header>

        <div className="flex gap-2">
          <Input
            placeholder={t("placeholder")}
            value={seed}
            onChange={(e) => setSeed(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={relay.status === "loading"}
            className="flex-1"
          />
          <Button
            onClick={handleStart}
            disabled={relay.status === "loading" || !seed.trim()}
          >
            {relay.status === "loading" ? t("generating") : t("startRelay")}
          </Button>
        </div>

        {relay.status === "error" && relay.errorMessage && (
          <ErrorPanel message={relay.errorMessage} onRetry={handleStart} />
        )}

        {(relay.chain.length > 0 || relay.status === "loading") && (
          <RelayChain
            state={relay}
            onCopy={handleCopy}
            onRegenerate={handleRegenerate}
          />
        )}
      </div>

      <footer className="w-full max-w-2xl mx-auto mt-16 pt-6 border-t border-border">
        <p className="text-xs text-muted-foreground text-center leading-relaxed max-w-lg mx-auto">
          {t("disclaimer")}
        </p>
      </footer>
    </main>
  );
}
