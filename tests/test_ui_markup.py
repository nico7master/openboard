"""UI render-integrity pin (2026-09-21 visual pass): every dashboard view
container must be a SIBLING, never nested inside another view's container.

The shipped RC1 UI had an unclosed <div> in the policy (Lab) section, which
made the browser nest chronicle/break/civic/seat INSIDE the hidden policy
container: their tabs activated, data polled, but nothing could ever paint.
613 tests + every API check passed — only a real browser click saw it.
This pin parses the markup so the bug class dies here."""
import re
from pathlib import Path

INDEX = Path(__file__).resolve().parents[1] / "dashboard" / "static" / "index.html"


def _containers():
    lines = INDEX.read_text().splitlines()
    opens = [i for i, l in enumerate(lines) if re.search(r'x-show="view === \'\w+\'"', l) and "<div" in l]
    for idx, start in enumerate(opens):
        end = opens[idx + 1] if idx + 1 < len(opens) else len(lines)
        depth = 0
        for i in range(start, end):
            depth += len(re.findall(r"<div\b", lines[i])) - lines[i].count("</div>")
        name = re.search(r"view === '(\w+)'", lines[start]).group(1)
        yield name, depth, end < len(lines)


def test_every_view_container_closes_before_the_next():
    for name, depth, has_next in _containers():
        if has_next:  # the last container closes at the x-data close
            assert depth == 0, (
                f"view '{name}' is unbalanced (+{depth}) at the next view open — "
                "later views would be nested inside its hidden container and "
                "could never render (the 2026-09-21 blank-tab bug)"
            )


def test_all_six_views_exist():
    names = {name for name, _, _ in _containers()}
    assert {"world", "policy", "chronicle", "break", "civic", "seat"} <= names
