const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

export async function healthCheck() {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
}

export function getRelayStreamUrl(seed: string, rounds: number = 5): string {
  const params = new URLSearchParams({ seed, rounds: String(rounds) });
  return `${API_BASE}/api/relay/stream?${params}`;
}
