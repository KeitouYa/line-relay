"""测试 SRT 字幕解析。

parse_srt 是导入电影台词的核心函数,把 OpenSubtitles 下载的 .srt 文件
解析成 list[dict],存入数据库。
"""
from app.services.subtitle_parser import parse_srt


def test_parse_srt_extracts_basic_quotes():
    """标准 SRT 格式应该能正确解析两条台词,带准确的时间戳。"""
    srt_content = """1
00:00:09,640 --> 00:00:11,350
And it will find you...

2
00:00:11,802 --> 00:00:13,550
You can't escape from me.
"""

    quotes = parse_srt(srt_content)

    assert len(quotes) == 2
    assert quotes[0]["text"] == "And it will find you..."
    assert quotes[0]["start_time"] == 9.640
    assert quotes[0]["end_time"] == 11.350
    assert quotes[1]["text"] == "You can't escape from me."


def test_parse_srt_strips_html_tags():
    """SRT 里的 HTML 标签 (<i>, <b>) 应该被去掉,只保留纯文本。"""
    srt_content = """1
00:00:01,000 --> 00:00:02,000
<i>Italic text content</i>
"""

    quotes = parse_srt(srt_content)

    assert len(quotes) == 1
    assert quotes[0]["text"] == "Italic text content"


def test_parse_srt_skips_too_short_quotes():
    """少于 3 个字符的台词应该被过滤掉(避免无意义片段污染数据)。"""
    srt_content = """1
00:00:01,000 --> 00:00:02,000
ok

2
00:00:03,000 --> 00:00:04,000
This is a longer quote that should pass.
"""

    quotes = parse_srt(srt_content)

    # 只有第 2 条应该被保留
    assert len(quotes) == 1
    assert quotes[0]["text"] == "This is a longer quote that should pass."
