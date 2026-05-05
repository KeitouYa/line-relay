"use client";

import { useState, useEffect, useCallback } from "react";

// ============================================================
// Translation dictionary
// ============================================================

const dict = {
  en: {
    title: "Line Relay",
    subtitle: "Movie Quote Relay · Enter a quote, see where AI takes it",
    placeholder: 'e.g. "I will find you"',
    startRelay: "Start Relay",
    generating: "Generating...",
    thinking: "AI is thinking...",
    elapsed: "elapsed",
    copyChain: "Copy Chain",
    regenerate: "Regenerate",
    relayFailed: "Relay Failed",
    retry: "Retry",
    relayFailedGeneric: "Relay failed, please try again",
    noMatch: "No matching quote found",
    noCandidates: "No candidates left at round {n}",
    disclaimer:
      "This is a non-commercial AI experiment. All quotes belong to their respective copyright holders. For entertainment purposes only — not affiliated with any movie studio.",
    modeSeed: "Seed",
    modeFallback: "Fallback",
    modeFollowUp: "Follow-up",
    modeKeywordTrigger: "Keyword",
    modeTwist: "Twist",
    modeBreak: "Break",
    aiReason: "AI Reason",
  },
  zh: {
    title: "Line Relay",
    subtitle: "AI 台词接龙 · 输入一句电影台词，看 AI 怎么接",
    placeholder: '比如: "I will find you"',
    startRelay: "开始接龙",
    generating: "生成中...",
    thinking: "LLM 正在思考中...",
    elapsed: "已用",
    copyChain: "复制接龙",
    regenerate: "重新生成",
    relayFailed: "接龙失败了",
    retry: "重新生成",
    relayFailedGeneric: "接龙失败，请重试",
    noMatch: "找不到匹配的起始台词",
    noCandidates: "第 {n} 轮没有候选了",
    disclaimer:
      "本网站为非营利的 AI 实验项目。所有台词版权归原作者所有。仅供娱乐，与任何电影公司无关。",
    modeSeed: "起始",
    modeFallback: "兜底",
    modeFollowUp: "顺承",
    modeKeywordTrigger: "关键词触发",
    modeTwist: "反转",
    modeBreak: "断裂",
    aiReason: "AI 理由",
  },
};

export type Lang = "en" | "zh";
export type TextKey = keyof typeof dict.en;

// ============================================================
// Hook
// ============================================================

const LANG_KEY = "line-relay:lang";

function getStoredLang(): Lang {
  if (typeof window === "undefined") return "en";
  const stored = localStorage.getItem(LANG_KEY);
  return stored === "zh" ? "zh" : "en";
}

let _globalLang: Lang = "en";
const _listeners = new Set<() => void>();

export function useTranslations() {
  const [lang, setLangState] = useState<Lang>(() => {
    const stored = getStoredLang();
    _globalLang = stored;
    return stored;
  });

  useEffect(() => {
    const listener = () => setLangState(_globalLang);
    _listeners.add(listener);
    return () => {
      _listeners.delete(listener);
    };
  }, []);

  const t = useCallback(
    (key: TextKey, vars?: Record<string, string | number>): string => {
      let text = dict[lang][key] as string;
      if (vars) {
        for (const [k, v] of Object.entries(vars)) {
          text = text.replaceAll(`{${k}}`, String(v));
        }
      }
      return text;
    },
    [lang],
  );

  const setLang = useCallback((l: Lang) => {
    _globalLang = l;
    localStorage.setItem(LANG_KEY, l);
    _listeners.forEach((fn) => fn());
  }, []);

  return { t, lang, setLang };
}
