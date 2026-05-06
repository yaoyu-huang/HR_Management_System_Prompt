#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
面试日程协调 CLI（核心逻辑见项目根目录 hr_tools.py）。
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from hr_tools import (  # noqa: E402
    DEFAULT_INTERVIEW_AVAILABILITY_JSON,
    run_interview_coordination,
)


def main() -> int:
    candidate_name = "王候选人"
    role = "高级后端工程师"
    company = "示例科技有限公司"

    print("--- 无感日程协调 · Demo ---")
    result = run_interview_coordination(
        DEFAULT_INTERVIEW_AVAILABILITY_JSON,
        candidate_name,
        role,
        company,
        top_n=3,
    )
    if not result["ok"]:
        print(f"[错误] {result.get('error')}", file=sys.stderr)
        return 1

    print(f"面试官：{result['interviewer']} ｜ 时区：{result['timezone']}")
    print(f"原始空闲段：{result['slot_count']} → 推荐：{result['chosen_count']}\n")

    out = Path(__file__).resolve().parent / "output" / "interview_options.ics"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(result["ics_bytes"])
    print(f"[OK] 已写入：{out.resolve()}\n")
    print(result["email_draft"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
