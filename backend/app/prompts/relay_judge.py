RELAY_JUDGE_SYSTEM = """You are a movie-quote relay editor skilled at creating comedic contrast.

4 valid relay modes:
1. follow-up - Natural conversational continuation (use sparingly as setup)
2. keyword-trigger - Grab a word from the previous quote and pivot (most common)
3. twist - Subvert or contradict the previous quote's meaning (funniest)
4. break - Completely unrelated, forced connection via absurd contrast (most surreal)

Your task: Pick the 3 best next quotes from the candidate list. Prioritize modes 2 and 3.

Hard rules:
- Exclude awkward repetitions (semantic overlap with no comedic value)
- Return strict JSON only. No markdown, no explanation, just JSON.
- "mode" must be exactly: "follow-up" / "keyword-trigger" / "twist" / "break"
  (no numbers, no dashes, no variations)
- JSON format: [{"id": <int>, "mode": "<one of the 4>", "reason": "<one-sentence reason (in English)>"}]"""


RELAY_JUDGE_USER_TEMPLATE = """Previous quote: "{seed_text}"
From: {seed_movie}

Candidates ({n_candidates} total):
{candidates_block}

Pick the 3 best next quotes. Return JSON.
Reminder: "mode" must be exactly "follow-up" / "keyword-trigger" / "twist" / "break"."""


def build_user_prompt(seed_quote, candidates: list) -> str:
    """构造 LLM 输入"""
    candidates_block = "\n".join([
        f"[{c.id}] 《{c.movie_title}》: \"{c.text}\""
        for c in candidates
    ])
    return RELAY_JUDGE_USER_TEMPLATE.format(
        seed_text=seed_quote.text,
        seed_movie=seed_quote.movie_title,
        n_candidates=len(candidates),
        candidates_block=candidates_block,
    )


VALID_MODES = {"follow-up", "keyword-trigger", "twist", "break"}
