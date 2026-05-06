# -*- coding: utf-8 -*-
"""
HR 自动化工具集：面试日程 ICS、DeepSeek 候选人触达、招聘数据洞察报告。
供 Flask 与 CLI 共用；不在此文件硬编码 API Key，由调用方传入。
"""

from __future__ import annotations

import io
import json
import os
import random
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

# 页面与 CLI 共用的示例 JSON（面试官下周空闲）
DEFAULT_INTERVIEW_AVAILABILITY_JSON = """{
  "interviewer": "李面试官",
  "timezone": "Asia/Shanghai",
  "slots": [
    {"label": "周一上午", "start": "2026-05-11T09:30:00+08:00", "end": "2026-05-11T10:30:00+08:00"},
    {"label": "周一午休边", "start": "2026-05-11T12:15:00+08:00", "end": "2026-05-11T13:00:00+08:00"},
    {"label": "周二下午", "start": "2026-05-12T14:00:00+08:00", "end": "2026-05-12T15:30:00+08:00"},
    {"label": "周三傍晚", "start": "2026-05-13T17:00:00+08:00", "end": "2026-05-13T18:00:00+08:00"},
    {"label": "周五中午", "start": "2026-05-15T11:30:00+08:00", "end": "2026-05-15T12:30:00+08:00"}
  ]
}"""


# ---------------------------------------------------------------------------
# 面试日程：解析 / 评分 / ICS / 邮件草稿
# ---------------------------------------------------------------------------


def _parse_slot(slot: dict) -> tuple[dict, datetime, datetime]:
    start = datetime.fromisoformat(slot["start"])
    end = datetime.fromisoformat(slot["end"])
    if end <= start:
        raise ValueError(f"时段非法：结束时间不晚于开始时间 —— {slot}")
    return slot, start, end


def pick_best_interview_slots(slots: list[dict], top_n: int = 3) -> list[tuple[dict, datetime, datetime]]:
    """从空闲段中选出最适合面试的 top_n 个（避午休、偏好下午）。"""
    if not slots:
        raise ValueError("空闲列表为空，无法筛选面试时段。")

    scored: list[tuple[float, dict, datetime, datetime]] = []

    for raw in slots:
        s, start, end = _parse_slot(raw)
        duration_h = (end - start).total_seconds() / 3600.0
        h = start.hour + start.minute / 60.0

        score = 0.0
        if 14.0 <= h < 18.0:
            score += 4.0
        elif 10.0 <= h < 12.0:
            score += 2.0
        elif 9.0 <= h < 10.0:
            score += 1.0

        lunch_start, lunch_end = 12.0, 14.0
        slot_end_h = end.hour + end.minute / 60.0 + (end.day - start.day) * 24
        overlap_start = max(h, lunch_start)
        overlap_end = min(slot_end_h, lunch_end)
        if overlap_end > overlap_start:
            overlap_hours = overlap_end - overlap_start
            score -= 5.0 * overlap_hours

        if 0.75 <= duration_h <= 2.0:
            score += 0.5
        elif duration_h < 0.75:
            score -= 0.3

        scored.append((score, s, start, end))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [(s, st, en) for _, s, st, en in scored[:top_n]]


def format_cn_window(start: datetime, end: datetime) -> str:
    return f"{start.strftime('%Y-%m-%d %H:%M')} – {end.strftime('%H:%M')}（{start.tzname() or start.tzinfo}）"


def build_ics_bytes(
    interviewer_name: str,
    candidate_name: str,
    role: str,
    chosen: list[tuple[dict, datetime, datetime]],
) -> bytes:
    """生成标准 .ics 文件二进制内容。"""
    try:
        from ics import Calendar, Event
    except ImportError as e:
        raise RuntimeError("未安装 ics 库，请执行：pip install ics") from e

    cal = Calendar(creator="HR-Interview-Coord")
    for slot, start, end in chosen:
        ev = Event()
        ev.name = f"面试备选时段｜{role}（与 {interviewer_name}）"
        ev.begin = start.astimezone(timezone.utc)
        ev.end = end.astimezone(timezone.utc)
        ev.description = (
            f"候选人：{candidate_name}\n"
            f"岗位：{role}\n"
            f"面试官：{interviewer_name}\n"
            f"原始标签：{slot.get('label', '')}\n"
            "说明：此为备选时段之一，请与 HR 确认最终时间。"
        )
        cal.events.add(ev)

    buf = io.StringIO()
    buf.writelines(cal.serialize_iter())
    return buf.getvalue().encode("utf-8")


def compose_interview_email_draft(
    interviewer: str,
    candidate_name: str,
    role: str,
    company: str,
    chosen: list[tuple[dict, datetime, datetime]],
    ics_filename: str,
) -> str:
    """生成邀约邮件草稿（纯文本，用于页面 <pre> 展示）。"""
    lines = [
        f"收件人：{candidate_name}",
        f"主题：{company}｜{role} 岗位面试时段协调",
        "",
        f"{candidate_name} 您好，",
        "",
        f"感谢您对 {company} 的关注。我们已协调 {interviewer} 的日程，为您预留以下可选面试时段，请您任选其一回复确认：",
        "",
    ]
    for i, (slot, start, end) in enumerate(chosen, 1):
        lines.append(f"  选项 {i}：{format_cn_window(start, end)}  （{slot.get('label', '')}）")

    lines.extend(
        [
            "",
            f"附件为可导入 Outlook / 苹果日历 / Google 日历 的日程文件（{ics_filename}），便于您预览时间冲突。",
            "若以上时间均不合适，请回复您本周可参与的 2～3 个时间段，我们将尽快二次协调。",
            "",
            "祝好！",
            f"{company} 招聘团队",
        ]
    )
    return "\n".join(lines)


def run_interview_coordination(
    availability_json: str,
    candidate_name: str,
    role: str,
    company: str,
    top_n: int = 3,
) -> dict[str, Any]:
    """
    执行完整面试协调流程。
    返回 dict：ok, error?, interviewer, timezone, slot_count, chosen_lines, ics_bytes, email_draft, ics_filename
    """
    try:
        payload = json.loads(availability_json)
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"JSON 解析失败：{e}"}

    slots = payload.get("slots") or []
    interviewer = (payload.get("interviewer") or "面试官").strip() or "面试官"
    tz_name = (payload.get("timezone") or "Asia/Shanghai").strip()

    try:
        chosen = pick_best_interview_slots(slots, top_n=top_n)
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    try:
        ics_bytes = build_ics_bytes(interviewer, candidate_name, role, chosen)
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}

    ics_filename = "interview_options.ics"
    email = compose_interview_email_draft(
        interviewer, candidate_name, role, company, chosen, ics_filename
    )
    chosen_lines = [format_cn_window(st, en) + f" （{sl.get('label', '')}）" for sl, st, en in chosen]

    return {
        "ok": True,
        "interviewer": interviewer,
        "timezone": tz_name,
        "slot_count": len(slots),
        "chosen_count": len(chosen),
        "chosen_lines": chosen_lines,
        "ics_bytes": ics_bytes,
        "ics_filename": ics_filename,
        "email_draft": email,
    }


# ---------------------------------------------------------------------------
# DeepSeek（OpenAI 兼容 /v1/chat/completions）
# ---------------------------------------------------------------------------

DEEPSEEK_DEFAULT_BASE = "https://api.deepseek.com/v1"
DEEPSEEK_DEFAULT_MODEL = "deepseek-chat"


def deepseek_chat_completion(
    api_key: str,
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    base_url: str | None = None,
    timeout_sec: int = 120,
    max_attempts: int = 4,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> str:
    """
    调用 DeepSeek Chat API，带退避重试。
    messages 示例：[{"role":"system","content":"..."},{"role":"user","content":"..."}]
    """
    if not api_key or api_key.strip() == "你的密钥":
        raise ValueError("未配置 DEEPSEEK_API_KEY（环境变量或应用配置）。")

    m = (model or os.environ.get("DEEPSEEK_MODEL") or DEEPSEEK_DEFAULT_MODEL).strip()
    base = (base_url or os.environ.get("DEEPSEEK_BASE_URL") or DEEPSEEK_DEFAULT_BASE).strip().rstrip("/")
    url = f"{base}/chat/completions"

    body: dict[str, Any] = {
        "model": m,
        "messages": messages,
        "temperature": 0.7 if temperature is None else float(temperature),
    }
    if max_tokens is not None:
        body["max_tokens"] = int(max_tokens)
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {api_key.strip()}",
    }

    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            if "error" in data and data["error"]:
                err = data["error"]
                msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                raise RuntimeError(f"DeepSeek API 错误：{msg}")
            choices = data.get("choices") or []
            if not choices:
                raise RuntimeError(f"DeepSeek 返回无 choices 字段：{raw[:500]}")
            content = (choices[0].get("message") or {}).get("content") or ""
            content = content.strip()
            if not content:
                raise RuntimeError("DeepSeek 返回空正文。")
            return content
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode("utf-8", errors="replace")[:1200]
            except Exception:  # noqa: BLE001
                detail = str(e)
            last_err = RuntimeError(f"DeepSeek HTTP {e.code}：{detail}")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError, OSError) as e:
            last_err = e

        wait = min(2**attempt + random.uniform(0, 0.8), 25.0)
        time.sleep(wait)

    raise RuntimeError(f"DeepSeek 调用在 {max_attempts} 次尝试后仍失败：{last_err}") from last_err


# ---------------------------------------------------------------------------
# 候选人触达（DeepSeek）
# ---------------------------------------------------------------------------

TOUCH_SYSTEM_PROMPT = """你是雇主品牌顾问，撰写简洁、有尊重的候选人结果通知邮件。

硬性要求：
1. 淘汰类结果：禁用「能力不行」「沟通差」「不行」等评判人格措辞。
2. 内敛/话少 → 转写为「更适合深度专注/结构化书面表达」等中性积极表述；不提「不适合团队」。
3. 薪资不匹配 → 用「编制与薪酬带宽暂难匹配当前期望」等表述，不贬低要价。
4. 仅 1 条可执行建议（面试表达、作品集或技能沉淀之一），一句话说清，忌空话。
5. 全文约 320～480 字中文；用「您」；结构：主题行 + 称呼 + 2～3 段短正文 + 简短祝颂 + 落款「启明数科 招聘团队」。
6. 不编造候选人未提及的具体技术栈。"""


def generate_touch_letter(
    api_key: str,
    name: str,
    role: str,
    hr_feedback: str,
    decision: str,
    model_name: str | None = None,
    max_attempts: int = 4,
) -> str:
    """调用 DeepSeek 生成高情商通知信正文。"""
    user_prompt = (
        f"候选人姓名：{name}\n"
        f"应聘岗位：{role}\n"
        f"HR 内部面评（仅供你转化语气，请勿原文照抄到邮件）：{hr_feedback}\n"
        f"招聘结果：{decision}\n\n"
        "请直接输出完整邮件（首行「主题：……」），语气真诚但避免重复客套与冗长铺垫。"
    )
    messages = [
        {"role": "system", "content": TOUCH_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    return deepseek_chat_completion(
        api_key,
        messages,
        model=model_name,
        max_attempts=max_attempts,
        max_tokens=900,
        temperature=0.55,
    )


# ---------------------------------------------------------------------------
# 招聘洞察 + 高管报告
# ---------------------------------------------------------------------------

_RNG = np.random.default_rng(42)
_CHANNELS = ["内推", "BOSS直聘", "官网", "牛客", "猎头"]


def build_recruitment_demo_dataframe(n: int = 100) -> pd.DataFrame:
    rows = []
    for cid in range(1, n + 1):
        ch = _CHANNELS[int(_RNG.integers(0, len(_CHANNELS)))]
        screen_hours = float(_RNG.uniform(0.5, 72.0))
        first = "通过" if _RNG.random() < 0.55 else "未通过"
        if first == "未通过":
            offer = "否"
            cycle_days = float(_RNG.uniform(3, 20))
        else:
            offer = "是" if _RNG.random() < 0.22 else "否"
            cycle_days = float(_RNG.uniform(12, 55))

        rows.append(
            {
                "候选人ID": f"C{cid:04d}",
                "岗位来源": ch,
                "初筛耗时": round(screen_hours, 2),
                "一面结果": first,
                "最终是否发Offer": offer,
                "招聘周期_天": round(cycle_days, 1),
            }
        )
    return pd.DataFrame(rows)


def aggregate_recruitment_metrics(df: pd.DataFrame) -> tuple[pd.Series, float, str]:
    conv = (
        df.assign(offer_flag=(df["最终是否发Offer"] == "是").astype(int))
        .groupby("岗位来源")["offer_flag"]
        .mean()
        * 100.0
    ).round(2)

    avg_cycle = float(df["招聘周期_天"].mean())
    top = conv.idxmax()
    bottom = conv.idxmin()
    insight = (
        f"本月{top}渠道最终 Offer 转化率领先，达 {conv[top]:.1f}%；"
        f"{bottom}渠道仅为 {conv[bottom]:.1f}%；"
        f"全样本平均招聘周期为 {avg_cycle:.1f} 天。"
    )
    return conv, avg_cycle, insight


EXEC_REPORT_SYSTEM = """你是集团人力资源总监，正在向 CEO 汇报月度招聘运营情况。
请基于给定的「数据摘要」与「各渠道转化率表」，写一份正式、简洁、可执行的 Markdown 报告，必须严格包含以下三个二级标题（使用 ##）：
## 核心数据表现
## 潜在流程风险
## 下月行动建议

要求：用中文；数据引用要与输入一致；风险部分至少指出一个与「初筛耗时」或「低转化渠道」相关的流程隐患；行动建议 3～5 条，可量化优先。总字数约 600～1000 字。"""


def generate_executive_hr_report(
    api_key: str,
    insight_text: str,
    conv_table: str,
    avg_cycle: float,
    model_name: str | None = None,
    max_attempts: int = 4,
) -> str:
    user = (
        "【数据摘要】\n"
        f"{insight_text}\n\n"
        "【各渠道 Offer 转化率（%）】\n"
        f"{conv_table}\n\n"
        f"【全样本平均招聘周期（天）】{avg_cycle:.2f}\n"
    )
    messages = [
        {"role": "system", "content": EXEC_REPORT_SYSTEM},
        {"role": "user", "content": user},
    ]
    return deepseek_chat_completion(
        api_key,
        messages,
        model=model_name,
        max_attempts=max_attempts,
    )


def run_hr_insight_pipeline(api_key: str, n_rows: int = 100) -> dict[str, Any]:
    """
    造数 → 聚合 → 洞察句 → DeepSeek 报告。
    返回 ok / error / steps(文本列表) / conv_str / insight / report
    """
    if not api_key or api_key.strip() == "你的密钥":
        raise ValueError("未配置 DEEPSEEK_API_KEY（环境变量或应用配置）。")

    steps: list[str] = []
    steps.append("--- 步骤 1/4：正在生成模拟招聘数据 ---")
    df = build_recruitment_demo_dataframe(n_rows)
    steps.append(f"  已生成 {len(df)} 条记录，列：{', '.join(df.columns)}")

    steps.append("--- 步骤 2/4：正在聚合核心指标 ---")
    conv, avg_cycle, insight = aggregate_recruitment_metrics(df)
    conv_str = conv.reset_index().to_string(index=False)
    steps.append("  各渠道 Offer 转化率（%）：\n" + conv_str)
    steps.append(f"  平均招聘周期（天）：{avg_cycle:.2f}")

    steps.append("--- 步骤 3/4：正在拼接业务洞察 ---")
    steps.append(f"  {insight}")

    steps.append("--- 步骤 4/4：正在调用 DeepSeek 生成高管报告 ---")
    report = generate_executive_hr_report(api_key, insight, conv_str, avg_cycle)
    steps.append("  报告已生成。")

    return {
        "ok": True,
        "steps": steps,
        "insight": insight,
        "conv_table": conv_str,
        "avg_cycle": avg_cycle,
        "report": report,
    }
