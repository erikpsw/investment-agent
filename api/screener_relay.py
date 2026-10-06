"""Forward capability-based jobs to a persistent screening service."""
import os
import re
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException

UNAVAILABLE = "筛选任务服务暂不可用，请稍后重试。"
FAILURES = {
    404: "筛选任务不存在或已过期，请重新提交。",
    409: "提交标识已用于其他条件，请重新提交。",
    422: "筛选任务条件无效，请修改后重试。",
    429: "筛选任务繁忙，请稍后重试。",
    503: UNAVAILABLE,
}


def service_origin() -> str | None:
    origin = os.getenv("SCREENER_SERVICE_URL", "").strip()
    if not origin:
        if os.getenv("VERCEL") == "1":
            raise HTTPException(503, "筛选任务服务尚未配置，请稍后重试。")
        return None
    try:
        parts = urlsplit(origin)
        valid_transport = parts.scheme == "https" or (parts.scheme == "http" and parts.hostname in ("localhost", "127.0.0.1", "::1"))
        if not valid_transport or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or parts.path not in ("", "/"):
            raise ValueError("invalid service origin")
        parts.port  # Validate malformed ports before constructing a request.
    except ValueError as exc:
        raise HTTPException(503, "筛选任务服务配置无效，请稍后重试。") from exc
    return origin.rstrip("/")


async def relay_job(origin: str, *, request: dict | None = None, job_id: str | None = None) -> dict:
    method = "POST" if request is not None else "GET"
    path = "/api/ai-screener/jobs" + (f"/{job_id}" if job_id else "")
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.request(method, origin + path, json=request if request is not None else None)
    except httpx.HTTPError as exc:
        raise HTTPException(503, UNAVAILABLE) from exc
    if response.status_code in FAILURES:
        raise HTTPException(response.status_code, FAILURES[response.status_code])
    if response.status_code != (202 if method == "POST" else 200):
        raise HTTPException(503, UNAVAILABLE)
    try:
        payload = response.json()
        job = payload["job"]
        if not isinstance(job, dict) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", job.get("id", "")):
            raise ValueError("invalid job identity")
        expected_id = request.get("submission_id") if request is not None else job_id
        if expected_id and job["id"] != expected_id:
            raise ValueError("different job identity")
        if job.get("status") not in ("running", "completed", "failed", "interrupted") or not isinstance(job.get("request"), dict):
            raise ValueError("invalid job")
        if request is not None and job["request"] != {k: v for k, v in request.items() if k != "submission_id"}:
            raise ValueError("different job conditions")
        if job["status"] == "completed" and not isinstance(job.get("response"), dict):
            raise ValueError("missing completed response")
        return {"job": job}
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(503, UNAVAILABLE) from exc
