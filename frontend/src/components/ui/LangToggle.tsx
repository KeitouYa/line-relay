"use client";

import { useTranslations } from "@/lib/i18n";

export function LangToggle() {
  const { lang, setLang } = useTranslations();

  return (
    <button
      onClick={() => setLang(lang === "en" ? "zh" : "en")}
      className="text-sm text-muted-foreground hover:text-foreground transition-colors"
      title={lang === "en" ? "Switch to 中文" : "Switch to English"}
    >
      {lang === "en" ? "中" : "EN"}
    </button>
  );
}
