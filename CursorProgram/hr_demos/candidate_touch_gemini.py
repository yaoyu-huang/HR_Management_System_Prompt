#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
「千人千面」候选人触达 CLI（逻辑见项目根目录 hr_tools.py）。
环境变量：DEEPSEEK_API_KEY
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from hr_tools import generate_touch_letter  # noqa: E402

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "你的密钥")

CANDIDATE_PROFILE = {
    "name": "张三",
    "role": "前端开发",
    "hr_feedback": "技术底子不错，但沟通太闷，且期望薪资超出部门预算",
    "decision": "淘汰",
}


def main() -> int:
    print("\n--- 千人千面候选人触达 · Gemini ---\n")
    try:
        letter = generate_touch_letter(
            DEEPSEEK_API_KEY,
            CANDIDATE_PROFILE["name"],
            CANDIDATE_PROFILE["role"],
            CANDIDATE_PROFILE["hr_feedback"],
            CANDIDATE_PROFILE["decision"],
        )
    except (ValueError, RuntimeError) as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 1

    print("=" * 72)
    print(letter)
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
