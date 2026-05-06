#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HR 数据洞察与高管报告 CLI（逻辑见项目根目录 hr_tools.py）。
环境变量：DEEPSEEK_API_KEY
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from hr_tools import run_hr_insight_pipeline  # noqa: E402

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "你的密钥")


def main() -> int:
    print("\n" + "=" * 56)
    print("  HR 数据洞察与高管报告自动生成器 · Demo")
    print("=" * 56 + "\n")

    try:
        result = run_hr_insight_pipeline(DEEPSEEK_API_KEY, n_rows=100)
    except (ValueError, RuntimeError) as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 1

    for line in result["steps"]:
        print(line)
    print()
    print("=" * 56)
    print("【AI 生成 · HR 总监报告】")
    print("=" * 56)
    print(result["report"])
    print("=" * 56)
    print("\n--- Demo 执行完毕 ---\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
