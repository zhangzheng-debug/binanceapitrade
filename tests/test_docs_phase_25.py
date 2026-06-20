from pathlib import Path


def test_rightbars_2_means_two_15m_bars_delay_documented() -> None:
    text = Path("docs/trading_rules.md").read_text(encoding="utf-8")
    assert "rightBars=2" in text
    assert "15m" in text
    assert "30 minutes" in text
    assert "must not confirm pivots early" in text

