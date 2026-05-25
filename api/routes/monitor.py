"""Realtime monitor control and persisted event views."""
from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, List

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from investment.agents.llm import get_llm_client
from investment.data.stock_picker import PROJECT_ROOT, get_stock_picker_service


router = APIRouter()
STORAGE_DIR = PROJECT_ROOT / "storage" / "realtime_monitor"
EVENTS_PATH = STORAGE_DIR / "events.jsonl"
LOGS_PATH = STORAGE_DIR / "logs.jsonl"
DECISIONS_PATH = STORAGE_DIR / "decisions.jsonl"
ALERTS_PATH = STORAGE_DIR / "alerts.jsonl"
STATE_PATH = STORAGE_DIR / "runtime_state.json"
PROFILE_PATH = PROJECT_ROOT / "USER.md"


def _read_jsonl(path: Path, limit: int) -> List[dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
        except Exception:
            continue
    return rows


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + "\n")


def _now() -> str:
    return datetime.now().isoformat()


def _parse_decision_analysis(value: str) -> dict[str, Any] | None:
    text = str(value or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(text[start:end + 1])
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None


def _decision_view(value: dict[str, Any]) -> dict[str, Any]:
    trace = value.get("tool_trace") if isinstance(value.get("tool_trace"), list) else []
    alerts = value.get("alerts") if isinstance(value.get("alerts"), list) else []
    return {
        "started_at": value.get("started_at"),
        "finished_at": value.get("finished_at"),
        "new_events": value.get("new_events"),
        "analysis": value.get("analysis"),
        "dry_run": value.get("dry_run"),
        "tool_trace": [
            {"type": item.get("type"), "tool": item.get("tool")}
            for item in trace
            if isinstance(item, dict)
        ],
        "alerts": [{"sent": item.get("sent"), "dry_run": item.get("dry_run")} for item in alerts if isinstance(item, dict)],
    }


class MonitorRequest(BaseModel):
    interval_seconds: int = Field(default=60, ge=20, le=3600)
    dry_run: bool = True
    channels: List[str] = Field(default_factory=lambda: ["flashes", "macro", "tech"])


class AnalyzeRequest(BaseModel):
    dry_run: bool = True
    limit: int = Field(default=20, ge=1, le=100)
    channels: List[str] = Field(default_factory=lambda: ["flashes", "macro", "tech"])


class UserProfileRequest(BaseModel):
    content: str


class RealtimeMonitorController:
    def __init__(self) -> None:
        self.running = False
        self.config = MonitorRequest()
        self.started_at: str | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def status(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "started_at": self.started_at,
            "interval_seconds": self.config.interval_seconds,
            "dry_run": self.config.dry_run,
            "channels": self.config.channels,
            "event_count": len(_read_jsonl(EVENTS_PATH, 100000)),
            "decision_count": len(_read_jsonl(DECISIONS_PATH, 100000)),
            "last_log": (_read_jsonl(LOGS_PATH, 1) or [None])[-1],
        }

    def start(self, request: MonitorRequest) -> dict[str, Any]:
        self.config = request
        if self.running:
            return self.status()
        self.running = True
        self.started_at = _now()
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self._log("info", "实时盯盘已启动", channels=request.channels, dry_run=request.dry_run)
        return self.status()

    def stop(self) -> dict[str, Any]:
        self.running = False
        self._stop.set()
        self._log("info", "实时盯盘已停止")
        return self.status()

    def analyze_once(self, request: AnalyzeRequest) -> dict[str, Any]:
        self._log("info", "手动刷新事件流", channels=request.channels, dry_run=request.dry_run)
        service = get_stock_picker_service()
        rows = service._fetch_macrostream_recent(limit=request.limit)
        fetch_errors = list(getattr(service, "last_macrostream_errors", []))
        if fetch_errors:
            self._log("error", "MacroStream 拉取失败", errors=fetch_errors)
        existing = {str(row.get("id")) for row in _read_jsonl(EVENTS_PATH, 10000)}
        added = 0
        new_events: List[dict[str, Any]] = []
        for row in reversed(rows):
            if row.get("id") and str(row["id"]) not in existing:
                _append_jsonl(EVENTS_PATH, {**row, "source": "macrostream", "status": "new"})
                existing.add(str(row["id"]))
                added += 1
                new_events.append(row)
        decision = self._record_decision(list(reversed(new_events)), request.dry_run) if new_events else None
        self._log("info", "事件流刷新完成", added=added, fetched=len(rows))
        return {
            "added": added,
            "fetched": len(rows),
            "events": list(reversed(_read_jsonl(EVENTS_PATH, request.limit))),
            "decision": decision,
        }

    def _record_decision(self, events: List[dict[str, Any]], dry_run: bool) -> dict[str, Any]:
        profile = PROFILE_PATH.read_text(encoding="utf-8") if PROFILE_PATH.exists() else ""
        compact_events = [
            {
                "id": item.get("id"),
                "channel": item.get("channel"),
                "title": item.get("title"),
                "summary": str(item.get("summary") or "")[:600],
                "published_at": item.get("published_at"),
                "source_url": item.get("source_url"),
            }
            for item in events[:20]
        ]
        prompt = f"""请判断本轮实时盯盘新增事件中哪些需要用户立即关注。
仅输出 JSON，不要 Markdown 代码块，结构为：
{{
  "summary": "本轮判断摘要",
  "reviewed_event_ids": ["事件id"],
  "important_events": [
    {{"event_id": "事件id", "title_cn": "简洁中文标题", "content_summary": "用一至两句话概述事件内容", "sector_impact": "用一至两句话说明对用户关注板块的可能影响"}}
  ],
  "ignored_reason": {{"事件id": "忽略原因"}}
}}
必须为每条事件给出 important_events 或 ignored_reason 之一；important_events 的标题必须翻译为中文，内容概述与板块影响都应简洁、具体，不要输出建议动作，不构成投资建议。所有字符串必须为纯文本，不要包含 Markdown 标题、列表、加粗、链接或代码标记。

用户偏好：
{profile[:3000]}

新增事件：
{json.dumps(compact_events, ensure_ascii=False)}"""
        analysis = get_llm_client().chat(
            prompt,
            system_prompt="你是实时市场事件分析员，负责输出可解释的事件筛选决策。请严格输出合法 JSON，字段内容使用简洁中文纯文本，禁止 Markdown。",
            temperature=0.2,
            max_tokens=1800,
        )
        if analysis.startswith("[LLM "):
            analysis = json.dumps(
                {
                    "summary": "决策模型暂不可用，已保留新增事件供人工复核。",
                    "reviewed_event_ids": [str(item.get("id")) for item in compact_events],
                    "important_events": [],
                    "ignored_reason": {
                        str(item.get("id")): "模型调用失败，暂未形成自动重要性结论。"
                        for item in compact_events
                    },
                },
                ensure_ascii=False,
            )
        decision = {
            "started_at": _now(),
            "finished_at": _now(),
            "new_events": len(events),
            "events": compact_events,
            "analysis": analysis,
            "tool_trace": [{"type": "tool_call", "tool": "realtime_event_reasoning", "input": {"event_count": len(events)}}],
            "alerts": [],
            "dry_run": dry_run,
        }
        decision["alerts"] = self._send_important_alerts(analysis, compact_events, dry_run=dry_run)
        _append_jsonl(DECISIONS_PATH, decision)
        return decision

    def _send_important_alerts(
        self,
        analysis: str,
        events: List[dict[str, Any]],
        *,
        dry_run: bool,
    ) -> List[dict[str, Any]]:
        parsed = _parse_decision_analysis(analysis)
        important = parsed.get("important_events") if isinstance(parsed, dict) else None
        if not isinstance(important, list):
            return []
        event_lookup = {str(item.get("id")): item for item in events}
        prior_alerts = _read_jsonl(ALERTS_PATH, 10000)
        already_sent = {
            str(item.get("event_id"))
            for item in prior_alerts
            if item.get("sent") or item.get("would_send")
        }
        service = get_stock_picker_service()
        results: List[dict[str, Any]] = []
        for item in important:
            if not isinstance(item, dict):
                continue
            event_id = str(item.get("event_id") or "")
            if not event_id:
                continue
            event = event_lookup.get(event_id, {})
            title = str(item.get("title_cn") or item.get("title") or event.get("title") or event.get("summary") or "实时盯盘重点事件")[:120]
            content_summary = str(item.get("content_summary") or item.get("reason") or "该事件被识别为需要及时关注的市场动态。")
            sector_impact = str(item.get("sector_impact") or item.get("action") or item.get("action_taken") or "可能影响相关市场情绪与关注板块走势，需继续观察后续变化。")
            text = (
                f"【实时盯盘】{title}\n\n"
                f"内容概述：{content_summary}\n\n"
                f"关注板块影响：{sector_impact}\n\n"
                f"原文：{event.get('source_url') or '--'}"
            )
            record: dict[str, Any] = {
                "timestamp": _now(),
                "event_id": event_id,
                "title": title,
                "severity": "medium",
                "text": text,
                "dry_run": dry_run,
                "trigger_source": "decision_important_event",
            }
            if event_id in already_sent:
                record.update({"sent": False, "deduped": True, "reason": "event already alerted"})
            elif dry_run:
                record.update({"sent": False, "would_send": True})
                already_sent.add(event_id)
            else:
                send_result = service._send_feishu_text(text)
                record.update({"sent": bool(send_result.get("ok")), "send_result": send_result})
                if record["sent"]:
                    already_sent.add(event_id)
            _append_jsonl(ALERTS_PATH, record)
            results.append(record)
            self._log(
                "info" if record.get("sent") or record.get("would_send") or record.get("deduped") else "error",
                "飞书提醒处理完成",
                event_id=event_id,
                sent=record.get("sent", False),
                dry_run=dry_run,
                deduped=record.get("deduped", False),
            )
        return results

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.analyze_once(
                    AnalyzeRequest(
                        dry_run=self.config.dry_run,
                        limit=20,
                        channels=self.config.channels,
                    )
                )
            except Exception as exc:
                self._log("error", "事件流刷新失败", error=str(exc)[:240])
            self._stop.wait(self.config.interval_seconds)

    def _log(self, level: str, message: str, **extra: Any) -> None:
        _append_jsonl(LOGS_PATH, {"timestamp": _now(), "level": level, "message": message, **extra})


controller = RealtimeMonitorController()


@router.get("/monitor/status")
async def monitor_status():
    return {"status": "ok", "result": controller.status()}


@router.post("/monitor/start")
async def monitor_start(request: MonitorRequest):
    return {"status": "ok", "result": controller.start(request)}


@router.post("/monitor/stop")
async def monitor_stop():
    return {"status": "ok", "result": controller.stop()}


@router.post("/monitor/analyze-once")
async def monitor_analyze_once(request: AnalyzeRequest):
    result = await asyncio.to_thread(controller.analyze_once, request)
    return {"status": "ok", "result": result}


@router.get("/monitor/events")
async def monitor_events(limit: int = Query(default=100, ge=1, le=500)):
    return {"status": "ok", "result": list(reversed(_read_jsonl(EVENTS_PATH, limit)))}


@router.get("/monitor/logs")
async def monitor_logs(limit: int = Query(default=100, ge=1, le=500)):
    return {"status": "ok", "result": list(reversed(_read_jsonl(LOGS_PATH, limit)))}


@router.get("/monitor/decisions")
async def monitor_decisions(limit: int = Query(default=50, ge=1, le=200)):
    return {"status": "ok", "result": [_decision_view(item) for item in _read_jsonl(DECISIONS_PATH, limit)]}


@router.get("/monitor/alerts")
async def monitor_alerts(limit: int = Query(default=100, ge=1, le=500)):
    return {"status": "ok", "result": list(reversed(_read_jsonl(ALERTS_PATH, limit)))}


@router.get("/user-profile")
async def get_user_profile():
    return {"status": "ok", "result": {"content": PROFILE_PATH.read_text(encoding="utf-8") if PROFILE_PATH.exists() else ""}}


@router.put("/user-profile")
async def update_user_profile(request: UserProfileRequest):
    PROFILE_PATH.write_text(request.content, encoding="utf-8")
    return {"status": "ok", "result": {"saved_at": _now()}}
