import { useState, useRef, useCallback } from "react";
import { getRelayStreamUrl } from "@/lib/api";

export type RelayNode = {
  round: number;
  quote_id: number;
  text: string;
  movie_title: string;
  movie_year: number | null;
  start_time: number | null;
  end_time: number | null;
  mode: string; // "顺承" / "关键词触发" / "反转" / "断裂" / "fallback" / "seed"
  reason: string;
};

export type RelayState = {
  status: "idle" | "loading" | "done" | "error";
  chain: RelayNode[];
  errorMessage: string | null;
  rounds: number;
  startTime: number | null;
};

export function useRelaySSE() {
  const [state, setState] = useState<RelayState>({
    status: "idle",
    chain: [],
    errorMessage: null,
    rounds: 5,
    startTime: null,
  });
  const esRef = useRef<EventSource | null>(null);

  const start = useCallback(async (seed: string, rounds: number = 5) => {
    // 关闭旧连接
    if (esRef.current) {
      esRef.current.close();
    }

    setState({
      status: "loading",
      chain: [],
      errorMessage: null,
      rounds,
      startTime: Date.now(),
    });

    const url = getRelayStreamUrl(seed, rounds);

    // 先探测是否被限流（EventSource 拿不到 HTTP 状态码）
    const probe = await fetch(url, {
      method: "GET",
      headers: { Accept: "text/event-stream", "X-Relay-Probe": "1" },
    });
    if (probe.status === 429) {
      const body = await probe.json().catch(() => ({}));
      setState((s) => ({
        ...s,
        status: "error",
        errorMessage:
          body.detail?.message || "Too fast! Please wait and try again 🙏",
      }));
      return;
    }

    const es = new EventSource(url);
    esRef.current = es;

    es.addEventListener("seed", (e) => {
      const data = JSON.parse(e.data);
      setState((s) => ({
        ...s,
        chain: [...s.chain, { ...data, mode: "seed", reason: "" }],
      }));
    });

    es.addEventListener("round", (e) => {
      const data = JSON.parse(e.data);
      setState((s) => ({ ...s, chain: [...s.chain, data] }));
    });

    es.addEventListener("done", () => {
      setState((s) => ({ ...s, status: "done" }));
      es.close();
      esRef.current = null;
    });

    es.addEventListener("error", (e) => {
      // SSE error 事件 e.data 可能没有 (浏览器原生连接断开)
      let msg = "Relay failed, please try again";
      if (e instanceof MessageEvent && e.data) {
        try {
          const parsed = JSON.parse(e.data);
          msg = parsed.message || msg;
        } catch {}
      }
      setState((s) => ({ ...s, status: "error", errorMessage: msg }));
      es.close();
      esRef.current = null;
    });
  }, []);

  const reset = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    setState({
      status: "idle",
      chain: [],
      errorMessage: null,
      rounds: 5,
      startTime: null,
    });
  }, []);

  return { ...state, start, reset };
}
