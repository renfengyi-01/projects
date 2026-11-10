# -*- coding: utf-8 -*-
"""时间与闰年工具：跨平台取当前时间、按完整历法规则判定闰年。"""
from __future__ import annotations

import datetime as _dt

from .base import BaseTool


class CurrentTimeTool(BaseTool):
    name = "get_current_time"
    description = "获取当前系统日期与时间（本地时区），返回 ISO 格式字符串与年月日时分秒字段。"
    parameters = {
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "可选，时区偏移小时数，如 8 表示东八区；不传则用系统本地时区。",
            }
        },
        "required": [],
    }

    def execute(self, timezone: float | None = None) -> dict:
        if timezone is None:
            now = _dt.datetime.now().astimezone()
        else:
            tz = _dt.timezone(_dt.timedelta(hours=float(timezone)))
            now = _dt.datetime.now(tz)
        return {
            "iso": now.isoformat(timespec="seconds"),
            "year": now.year,
            "month": now.month,
            "day": now.day,
            "hour": now.hour,
            "minute": now.minute,
            "second": now.second,
            "weekday": now.strftime("%A"),
            "timestamp": int(now.timestamp()),
        }


class LeapYearTool(BaseTool):
    name = "is_leap_year"
    description = (
        "判定给定年份是否为闰年。规则：能被 4 整除但不能被 100 整除，"
        "或能被 400 整除（整百年必须被 400 整除）。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "year": {"type": "integer", "description": "公历年份，如 2000、1900、2024"}
        },
        "required": ["year"],
    }

    def execute(self, year: int) -> dict:
        y = int(year)
        if y <= 0:
            return {"year": y, "is_leap": False, "reason": "公历年份应大于 0"}
        div4 = y % 4 == 0
        div100 = y % 100 == 0
        div400 = y % 400 == 0
        is_leap = div4 and (not div100 or div400)
        if div400:
            reason = f"{y} 能被 400 整除，是闰年"
        elif div100:
            reason = f"{y} 能被 100 整除但不能被 400 整除，不是闰年"
        elif div4:
            reason = f"{y} 能被 4 整除且不能被 100 整除，是闰年"
        else:
            reason = f"{y} 不能被 4 整除，不是闰年"
        return {"year": y, "is_leap": is_leap, "days_in_february": 29 if is_leap else 28, "reason": reason}
