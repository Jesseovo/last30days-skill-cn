# last30days-cn

Agent-facing notes for local development.

## Purpose

`last30days-cn` researches recent Chinese-platform discussion across Weibo, Xiaohongshu, Bilibili, Zhihu, Douyin, WeChat public accounts, Baidu, and Toutiao. The default window is the last 30 days.

## Structure

- `SKILL.md`: root development copy and source of truth for the skill instructions.
- `scripts/`: root development copy and source of truth for the runtime.
- `skills/last30days/`: generated installable Agent Skill payload.
- `scripts/lib/render.py`: Markdown, JSON context, and HTML report rendering.
- `tests/`: focused regression tests.

Only edit the root `SKILL.md` and `scripts/` tree. Regenerate the installable
payload before committing:

```bash
python scripts/build_payload.py
python scripts/build_payload.py --check
```

## Commands

```bash
python scripts/last30days.py "你的主题" --emit compact
python scripts/last30days.py "你的主题" --emit html-path
python scripts/last30days.py --diagnose
```

When validating on this Windows workspace, prefer:

```bash
python -m pytest tests -q
```

The `python` command may resolve to the Windows Store shim on some machines.

## Release Notes

For v3.0.0, the skill payload is self-contained under `skills/last30days`, and the new HTML renderer emits a Guizang-inspired Swiss/IKB report.
