import re

def parse_srt(srt_content: str) -> list[dict]:
    """
    解析SRT字幕文件，返回台词列表。
    每条包含：text, start_time, end_time（秒数）
    """
    blocks = re.split(r"\n\s*\n", srt_content.strip())
    quotes = []

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue

        time_match = re.match(
            r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})",
            lines[1],
        )
        if not time_match:
            continue

        g = time_match.groups()
        start_time = int(g[0]) * 3600 + int(g[1]) * 60 + int(g[2]) + int(g[3]) / 1000
        end_time = int(g[4]) * 3600 + int(g[5]) * 60 + int(g[6]) + int(g[7]) / 1000

        text = " ".join(lines[2:])
        text = re.sub(r"<[^>]+>", "", text)  # 去掉HTML标签
        text = re.sub(r"\{[^}]+\}", "", text)  # 去掉ASS样式标签
        text = text.strip()

        if text and len(text) > 2:
            quotes.append({
                "text": text,
                "start_time": round(start_time, 3),
                "end_time": round(end_time, 3),
            })

    return quotes


def merge_short_quotes(quotes: list[dict], min_length: int = 10) -> list[dict]:
    """
    合并过短的台词（如单个词），让每条台词更完整。
    相邻台词间隔<1秒且合并后<200字符则合并。
    """
    if not quotes:
        return []

    merged = [quotes[0]]
    for q in quotes[1:]:
        prev = merged[-1]
        gap = q["start_time"] - prev["end_time"]
        combined_text = prev["text"] + " " + q["text"]

        if (len(prev["text"]) < min_length or len(q["text"]) < min_length) \
                and gap < 1.0 and len(combined_text) < 200:
            merged[-1] = {
                "text": combined_text,
                "start_time": prev["start_time"],
                "end_time": q["end_time"],
            }
        else:
            merged.append(q)

    return merged