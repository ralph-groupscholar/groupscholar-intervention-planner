#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Tuple

HIGH_IMPACT_FLAGS = {"crisis", "housing", "food", "health", "safety", "financial"}
DEFAULT_DB_SCHEMA = "groupscholar_intervention_planner"


@dataclass
class ScholarRecord:
    scholar_id: str
    name: str
    cohort: str
    owner: str
    channel_preference: str
    last_touch: Optional[date]
    risk_score: float
    flags: List[str]


@dataclass
class ScoredRecord:
    scholar_id: str
    name: str
    cohort: str
    owner: str
    channel_preference: str
    last_touch: Optional[str]
    risk_score: float
    flags: List[str]
    cadence_days: int
    due_date: Optional[str]
    days_since_touch: Optional[int]
    due_in_days: Optional[int]
    overdue_days: Optional[int]
    status: str
    priority_score: float
    recommended_action: str
    priority_reasons: List[str]
    stale_touch: bool
    stale_days: Optional[int]


def parse_date(value: str) -> Optional[date]:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def safe_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_flags(value: str) -> List[str]:
    if not value:
        return []
    return [flag.strip().lower() for flag in value.split(";") if flag.strip()]


def validate_schema_name(schema: str) -> str:
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", schema):
        raise SystemExit("Invalid schema name. Use letters, numbers, and underscores only.")
    return schema


def default_run_label(input_path: str, today: date) -> str:
    stem = Path(input_path).stem or "intervention"
    return f"{stem}-{today.isoformat()}"


def load_csv(path: str) -> List[ScholarRecord]:
    records: List[ScholarRecord] = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            records.append(
                ScholarRecord(
                    scholar_id=(row.get("id") or row.get("scholar_id") or "").strip(),
                    name=(row.get("name") or "").strip(),
                    cohort=(row.get("cohort") or "").strip(),
                    owner=normalize_owner(
                        row.get("owner") or row.get("advisor") or row.get("case_manager") or row.get("coach") or ""
                    ),
                    channel_preference=(row.get("channel_preference") or row.get("preferred_channel") or "").strip(),
                    last_touch=parse_date(row.get("last_touch") or row.get("last_contact") or ""),
                    risk_score=safe_float(row.get("risk_score") or row.get("risk") or "0"),
                    flags=parse_flags(row.get("flags") or ""),
                )
            )
    return records


def cadence_for_risk(score: float, high: float, medium: float) -> Tuple[str, int]:
    if score >= high:
        return "high", 7
    if score >= medium:
        return "medium", 21
    return "low", 45


def compute_priority(
    record: ScholarRecord,
    today: date,
    high: float,
    medium: float,
    soon_days: int,
    stale_days: int,
    stale_boost: float,
) -> ScoredRecord:
    tier, cadence_days = cadence_for_risk(record.risk_score, high, medium)
    reasons: List[str] = []
    stale_touch = False
    stale_days_value: Optional[int] = None
    if record.last_touch:
        days_since = (today - record.last_touch).days
        stale_days_value = days_since
        due_date = record.last_touch + timedelta(days=cadence_days)
        due_delta = (due_date - today).days
        overdue = due_delta < 0
        due_soon = 0 <= due_delta <= soon_days
        overdue_days = max(0, -due_delta)
    else:
        days_since = None
        due_date = None
        due_delta = None
        overdue = False
        due_soon = False
        overdue_days = None

    priority = record.risk_score
    if tier == "high":
        reasons.append("high risk tier")
    elif tier == "medium":
        reasons.append("medium risk tier")
    if record.last_touch is None:
        priority += 25
        reasons.append("no previous touch")
    if record.last_touch and stale_days_value is not None and stale_days_value >= stale_days:
        priority += stale_boost
        stale_touch = True
        reasons.append(f"stale last touch ({stale_days_value} days)")
    if overdue:
        priority += 30
        reasons.append(f"overdue by {overdue_days} days")
    elif due_soon:
        priority += 12
        days_until_due = due_delta if due_delta is not None else 0
        reasons.append(f"due in {days_until_due} days")

    for flag in record.flags:
        if flag in HIGH_IMPACT_FLAGS:
            priority += 8
            reasons.append(f"flag: {flag}")

    if record.last_touch is None:
        status = "no-touch"
    elif overdue:
        status = "overdue"
    elif due_soon:
        status = "due-soon"
    else:
        status = "on-track"

    recommended_action = build_recommendation(tier, record.channel_preference, status)

    return ScoredRecord(
        scholar_id=record.scholar_id,
        name=record.name,
        cohort=record.cohort,
        owner=record.owner,
        channel_preference=record.channel_preference,
        last_touch=record.last_touch.isoformat() if record.last_touch else None,
        risk_score=record.risk_score,
        flags=record.flags,
        cadence_days=cadence_days,
        due_date=due_date.isoformat() if due_date else None,
        days_since_touch=days_since,
        due_in_days=due_delta,
        overdue_days=overdue_days if due_delta is not None else None,
        status=status,
        priority_score=round(priority, 2),
        recommended_action=recommended_action,
        priority_reasons=reasons,
        stale_touch=stale_touch,
        stale_days=stale_days_value if stale_touch else None,
    )


def build_recommendation(tier: str, channel: str, status: str) -> str:
    channel = (channel or "").strip().lower()
    if channel in {"sms", "text"}:
        channel_phrase = "Send a brief text check-in"
    elif channel in {"email"}:
        channel_phrase = "Send a focused email check-in"
    elif channel in {"call", "phone"}:
        channel_phrase = "Schedule a short call"
    else:
        channel_phrase = "Send a check-in"

    if status == "overdue":
        urgency = "within 48 hours"
    elif status == "due-soon":
        urgency = "within the next week"
    elif status == "no-touch":
        urgency = "today"
    else:
        urgency = "during the next touch window"

    if tier == "high":
        tier_phrase = "Confirm support needs and capture blockers"
    elif tier == "medium":
        tier_phrase = "Reconfirm goals and offer resource links"
    else:
        tier_phrase = "Share a light encouragement and next milestone"

    return f"{channel_phrase} {urgency}. {tier_phrase}."


def summarize(scored: List[ScoredRecord]) -> Dict[str, object]:
    summary = {
        "total": len(scored),
        "overdue": 0,
        "due_soon": 0,
        "on_track": 0,
        "no_touch": 0,
        "high_risk": 0,
        "medium_risk": 0,
        "low_risk": 0,
        "stale_touch": 0,
    }
    for record in scored:
        if record.status == "overdue":
            summary["overdue"] += 1
        elif record.status == "due-soon":
            summary["due_soon"] += 1
        elif record.status == "on-track":
            summary["on_track"] += 1
        elif record.status == "no-touch":
            summary["no_touch"] += 1

        if record.cadence_days == 7:
            summary["high_risk"] += 1
        elif record.cadence_days == 21:
            summary["medium_risk"] += 1
        else:
            summary["low_risk"] += 1
        if record.stale_touch:
            summary["stale_touch"] += 1
    summary["overdue_aging"] = summarize_overdue_aging(scored)
    summary["no_touch_by_risk"] = summarize_no_touch_by_risk(scored)
    summary["status_by_risk"] = summarize_status_by_risk(scored)
    summary["touchpoint_horizon"] = summarize_touchpoint_horizon(scored)
    summary["stale_touch_by_risk"] = summarize_stale_touch_by_risk(scored)
    return summary


def summarize_overdue_aging(scored: List[ScoredRecord]) -> Dict[str, int]:
    buckets = {
        "1-7": 0,
        "8-14": 0,
        "15-30": 0,
        "31-60": 0,
        "61+": 0,
    }
    for record in scored:
        if record.status != "overdue" or record.overdue_days is None:
            continue
        days = record.overdue_days
        if days <= 7:
            buckets["1-7"] += 1
        elif days <= 14:
            buckets["8-14"] += 1
        elif days <= 30:
            buckets["15-30"] += 1
        elif days <= 60:
            buckets["31-60"] += 1
        else:
            buckets["61+"] += 1
    return buckets


def summarize_no_touch_by_risk(scored: List[ScoredRecord]) -> Dict[str, int]:
    counts = {"high": 0, "medium": 0, "low": 0}
    for record in scored:
        if record.status != "no-touch":
            continue
        if record.cadence_days == 7:
            counts["high"] += 1
        elif record.cadence_days == 21:
            counts["medium"] += 1
        else:
            counts["low"] += 1
    return counts


def summarize_status_by_risk(scored: List[ScoredRecord]) -> Dict[str, Dict[str, int]]:
    buckets = {
        "high": {"overdue": 0, "due_soon": 0, "on_track": 0, "no_touch": 0},
        "medium": {"overdue": 0, "due_soon": 0, "on_track": 0, "no_touch": 0},
        "low": {"overdue": 0, "due_soon": 0, "on_track": 0, "no_touch": 0},
    }
    status_map = {
        "overdue": "overdue",
        "due-soon": "due_soon",
        "on-track": "on_track",
        "no-touch": "no_touch",
    }
    for record in scored:
        if record.cadence_days == 7:
            tier = "high"
        elif record.cadence_days == 21:
            tier = "medium"
        else:
            tier = "low"
        mapped = status_map.get(record.status)
        if mapped:
            buckets[tier][mapped] += 1
    return buckets


def summarize_touchpoint_horizon(scored: List[ScoredRecord]) -> Dict[str, int]:
    buckets = {
        "overdue": 0,
        "next_7_days": 0,
        "next_14_days": 0,
        "next_30_days": 0,
        "later": 0,
        "no_due_date": 0,
    }
    for record in scored:
        due_in_days = record.due_in_days
        if due_in_days is None:
            buckets["no_due_date"] += 1
        elif due_in_days < 0:
            buckets["overdue"] += 1
        elif due_in_days <= 7:
            buckets["next_7_days"] += 1
        elif due_in_days <= 14:
            buckets["next_14_days"] += 1
        elif due_in_days <= 30:
            buckets["next_30_days"] += 1
        else:
            buckets["later"] += 1
    return buckets


def summarize_owner_horizon(scored: List[ScoredRecord]) -> List[Dict[str, object]]:
    owners: Dict[str, Dict[str, object]] = {}
    for record in scored:
        owner = normalize_owner(record.owner)
        bucket = owners.setdefault(
            owner,
            {
                "owner": owner,
                "total": 0,
                "overdue": 0,
                "next_7_days": 0,
                "next_14_days": 0,
                "next_30_days": 0,
                "later": 0,
                "no_due_date": 0,
                "avg_priority": 0.0,
            },
        )
        bucket["total"] = int(bucket["total"]) + 1
        bucket["avg_priority"] = round(
            (float(bucket["avg_priority"]) * (int(bucket["total"]) - 1) + record.priority_score) / int(bucket["total"]),
            2,
        )
        due_in_days = record.due_in_days
        if due_in_days is None:
            bucket["no_due_date"] = int(bucket["no_due_date"]) + 1
        elif due_in_days < 0:
            bucket["overdue"] = int(bucket["overdue"]) + 1
        elif due_in_days <= 7:
            bucket["next_7_days"] = int(bucket["next_7_days"]) + 1
        elif due_in_days <= 14:
            bucket["next_14_days"] = int(bucket["next_14_days"]) + 1
        elif due_in_days <= 30:
            bucket["next_30_days"] = int(bucket["next_30_days"]) + 1
        else:
            bucket["later"] = int(bucket["later"]) + 1

    return sorted(
        owners.values(),
        key=lambda item: (
            -int(item["overdue"]),
            -int(item["next_7_days"]),
            -int(item["next_14_days"]),
            -int(item["total"]),
            -float(item["avg_priority"]),
        ),
    )


def summarize_touchpoint_forecast(
    scored: List[ScoredRecord],
    today: date,
    window_days: int,
    include_overdue: bool,
) -> Dict[str, object]:
    window_days = max(1, int(window_days))
    daily_counts = [0 for _ in range(window_days + 1)]
    overdue = 0
    no_due_date = 0
    beyond_window = 0
    for record in scored:
        due_in_days = record.due_in_days
        if due_in_days is None:
            no_due_date += 1
            continue
        if due_in_days < 0:
            overdue += 1
            if include_overdue:
                daily_counts[0] += 1
            continue
        if due_in_days <= window_days:
            daily_counts[due_in_days] += 1
        else:
            beyond_window += 1

    daily = [
        {"date": (today + timedelta(days=offset)).isoformat(), "count": count}
        for offset, count in enumerate(daily_counts)
    ]
    return {
        "window_days": window_days,
        "include_overdue": include_overdue,
        "overdue": overdue,
        "no_due_date": no_due_date,
        "beyond_window": beyond_window,
        "daily": daily,
    }


def summarize_owner_capacity(
    scored: List[ScoredRecord],
    window_days: int,
    daily_capacity: int,
    include_overdue: bool,
) -> List[Dict[str, object]]:
    window_days = max(1, int(window_days))
    daily_capacity = max(0, int(daily_capacity))
    buckets: Dict[str, Dict[str, object]] = {}
    for record in scored:
        owner = normalize_owner(record.owner)
        bucket = buckets.setdefault(
            owner,
            {
                "owner": owner,
                "due_within_window": 0,
                "overdue": 0,
                "capacity": daily_capacity * window_days,
                "utilization": 0.0,
                "gap": 0,
                "window_days": window_days,
                "daily_capacity": daily_capacity,
            },
        )
        due_in_days = record.due_in_days
        if due_in_days is None:
            continue
        if due_in_days < 0:
            bucket["overdue"] = int(bucket["overdue"]) + 1
            if include_overdue:
                bucket["due_within_window"] = int(bucket["due_within_window"]) + 1
            continue
        if due_in_days <= window_days:
            bucket["due_within_window"] = int(bucket["due_within_window"]) + 1

    for bucket in buckets.values():
        capacity = int(bucket["capacity"])
        due_within = int(bucket["due_within_window"])
        bucket["gap"] = max(0, due_within - capacity)
        if capacity > 0:
            bucket["utilization"] = round(due_within / capacity, 2)
        else:
            bucket["utilization"] = 0.0

    return sorted(
        buckets.values(),
        key=lambda item: (
            -int(item["gap"]),
            -int(item["overdue"]),
            -int(item["due_within_window"]),
            item["owner"],
        ),
    )


def summarize_stale_touch_by_risk(scored: List[ScoredRecord]) -> Dict[str, int]:
    counts = {"high": 0, "medium": 0, "low": 0}
    for record in scored:
        if not record.stale_touch:
            continue
        if record.cadence_days == 7:
            counts["high"] += 1
        elif record.cadence_days == 21:
            counts["medium"] += 1
        else:
            counts["low"] += 1
    return counts


def normalize_channel(channel: str) -> str:
    value = (channel or "").strip().lower()
    if not value:
        return "unknown"
    if value in {"sms", "text"}:
        return "sms"
    if value in {"phone", "call"}:
        return "call"
    return value


def normalize_owner(owner: str) -> str:
    value = (owner or "").strip()
    return value or "Unassigned"


def summarize_channels(scored: List[ScoredRecord]) -> Dict[str, int]:
    mix: Dict[str, int] = {}
    for record in scored:
        key = normalize_channel(record.channel_preference)
        mix[key] = mix.get(key, 0) + 1
    return dict(sorted(mix.items(), key=lambda item: item[1], reverse=True))


def summarize_flags(scored: List[ScoredRecord]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for record in scored:
        for flag in record.flags:
            if flag in HIGH_IMPACT_FLAGS:
                counts[flag] = counts.get(flag, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: item[1], reverse=True))


def summarize_cohorts(scored: List[ScoredRecord]) -> List[Dict[str, object]]:
    cohorts: Dict[str, Dict[str, object]] = {}
    for record in scored:
        cohort = record.cohort.strip() if record.cohort else "Unassigned"
        bucket = cohorts.setdefault(
            cohort,
            {
                "cohort": cohort,
                "total": 0,
                "overdue": 0,
                "due_soon": 0,
                "no_touch": 0,
                "avg_priority": 0.0,
                "high_risk": 0,
                "medium_risk": 0,
                "low_risk": 0,
            },
        )
        bucket["total"] += 1
        if record.status == "overdue":
            bucket["overdue"] += 1
        elif record.status == "due-soon":
            bucket["due_soon"] += 1
        elif record.status == "no-touch":
            bucket["no_touch"] += 1

        if record.cadence_days == 7:
            bucket["high_risk"] += 1
        elif record.cadence_days == 21:
            bucket["medium_risk"] += 1
        else:
            bucket["low_risk"] += 1
        bucket["avg_priority"] = round(
            (bucket["avg_priority"] * (bucket["total"] - 1) + record.priority_score) / bucket["total"],
            2,
        )

    return sorted(
        cohorts.values(),
        key=lambda item: (
            -int(item["overdue"]),
            -int(item["due_soon"]),
            -float(item["avg_priority"]),
        ),
    )


def summarize_owners(scored: List[ScoredRecord]) -> List[Dict[str, object]]:
    owners: Dict[str, Dict[str, object]] = {}
    for record in scored:
        owner = normalize_owner(record.owner)
        bucket = owners.setdefault(
            owner,
            {
                "owner": owner,
                "total": 0,
                "overdue": 0,
                "due_soon": 0,
                "no_touch": 0,
                "avg_priority": 0.0,
                "high_risk": 0,
                "medium_risk": 0,
                "low_risk": 0,
            },
        )
        bucket["total"] += 1
        if record.status == "overdue":
            bucket["overdue"] += 1
        elif record.status == "due-soon":
            bucket["due_soon"] += 1
        elif record.status == "no-touch":
            bucket["no_touch"] += 1

        if record.cadence_days == 7:
            bucket["high_risk"] += 1
        elif record.cadence_days == 21:
            bucket["medium_risk"] += 1
        else:
            bucket["low_risk"] += 1

        bucket["avg_priority"] = round(
            (bucket["avg_priority"] * (bucket["total"] - 1) + record.priority_score) / bucket["total"],
            2,
        )

    return sorted(
        owners.values(),
        key=lambda item: (
            -int(item["overdue"]),
            -int(item["due_soon"]),
            -float(item["avg_priority"]),
        ),
    )


def build_owner_alerts(
    owners: List[Dict[str, object]],
    overdue_threshold: int,
    no_touch_threshold: int,
    total_threshold: int,
) -> List[Dict[str, object]]:
    alerts: List[Dict[str, object]] = []
    for bucket in owners:
        reasons = []
        overdue = int(bucket["overdue"])
        no_touch = int(bucket["no_touch"])
        total = int(bucket["total"])
        if overdue >= overdue_threshold:
            reasons.append(f"overdue >= {overdue_threshold}")
        if no_touch >= no_touch_threshold:
            reasons.append(f"no-touch >= {no_touch_threshold}")
        if total >= total_threshold:
            reasons.append(f"total >= {total_threshold}")
        if reasons:
            alerts.append(
                {
                    "owner": bucket["owner"],
                    "total": total,
                    "overdue": overdue,
                    "no_touch": no_touch,
                    "avg_priority": float(bucket["avg_priority"]),
                    "reasons": reasons,
                }
            )
    return sorted(
        alerts,
        key=lambda item: (
            -int(item["overdue"]),
            -int(item["no_touch"]),
            -int(item["total"]),
            -float(item["avg_priority"]),
        ),
    )


def build_owner_queue(scored: List[ScoredRecord], limit: int, size: int) -> List[Dict[str, object]]:
    buckets: Dict[str, Dict[str, object]] = {}
    for record in scored:
        owner = normalize_owner(record.owner)
        bucket = buckets.setdefault(
            owner,
            {
                "owner": owner,
                "total": 0,
                "items": [],
            },
        )
        bucket["total"] = int(bucket["total"]) + 1
        if len(bucket["items"]) < size:
            bucket["items"].append(
                {
                    "scholar_id": record.scholar_id,
                    "name": record.name,
                    "cohort": record.cohort,
                    "status": record.status,
                    "priority_score": record.priority_score,
                    "due_date": record.due_date,
                    "recommended_action": record.recommended_action,
                }
            )

    ordered = sorted(
        buckets.values(),
        key=lambda item: (
            -int(item["total"]),
            item["owner"],
        ),
    )
    return ordered[:limit]


def build_channel_batches(scored: List[ScoredRecord], limit: int, size: int) -> List[Dict[str, object]]:
    buckets: Dict[str, Dict[str, object]] = {}
    for record in scored:
        channel = normalize_channel(record.channel_preference)
        bucket = buckets.setdefault(
            channel,
            {
                "channel": channel,
                "total": 0,
                "overdue": 0,
                "due_soon": 0,
                "no_touch": 0,
                "avg_priority": 0.0,
                "items": [],
            },
        )
        bucket["total"] = int(bucket["total"]) + 1
        if record.status == "overdue":
            bucket["overdue"] = int(bucket["overdue"]) + 1
        elif record.status == "due-soon":
            bucket["due_soon"] = int(bucket["due_soon"]) + 1
        elif record.status == "no-touch":
            bucket["no_touch"] = int(bucket["no_touch"]) + 1

        bucket["avg_priority"] = round(
            (float(bucket["avg_priority"]) * (int(bucket["total"]) - 1) + record.priority_score) / int(bucket["total"]),
            2,
        )

        if len(bucket["items"]) < size:
            bucket["items"].append(
                {
                    "scholar_id": record.scholar_id,
                    "name": record.name,
                    "cohort": record.cohort,
                    "owner": record.owner,
                    "status": record.status,
                    "priority_score": record.priority_score,
                    "due_date": record.due_date,
                    "recommended_action": record.recommended_action,
                }
            )

    ordered = sorted(
        buckets.values(),
        key=lambda item: (
            -int(item["overdue"]),
            -int(item["due_soon"]),
            -int(item["total"]),
            -float(item["avg_priority"]),
        ),
    )
    return ordered[:limit]


def build_escalation_list(scored: List[ScoredRecord], limit: int, min_score: float) -> List[Dict[str, object]]:
    candidates: List[Dict[str, object]] = []
    for record in scored:
        if record.cadence_days != 7:
            continue
        if record.status not in {"overdue", "no-touch"}:
            continue
        if record.priority_score < min_score:
            continue
        candidates.append(
            {
                "scholar_id": record.scholar_id,
                "name": record.name,
                "cohort": record.cohort,
                "owner": record.owner,
                "status": record.status,
                "risk_score": record.risk_score,
                "priority_score": record.priority_score,
                "last_touch": record.last_touch,
                "due_date": record.due_date,
                "priority_reasons": record.priority_reasons,
                "recommended_action": record.recommended_action,
            }
        )
    candidates.sort(key=lambda item: (-float(item["priority_score"]), item["name"]))
    return candidates[:limit]


def print_summary(summary: Dict[str, object]) -> None:
    print("\nIntervention Summary")
    print("--------------------")
    print(f"Total scholars: {summary['total']}")
    print(f"High risk: {summary['high_risk']}")
    print(f"Medium risk: {summary['medium_risk']}")
    print(f"Low risk: {summary['low_risk']}")
    print(f"Overdue touches: {summary['overdue']}")
    print(f"Due soon: {summary['due_soon']}")
    print(f"On track: {summary['on_track']}")
    print(f"No prior touch: {summary['no_touch']}")
    print(f"Stale last touch: {summary['stale_touch']}")


def print_overdue_aging(overdue_aging: Dict[str, int]) -> None:
    print("\nOverdue Aging")
    print("-------------")
    if not overdue_aging:
        print("No overdue touches.")
        return
    for label, count in overdue_aging.items():
        print(f"{label:<6} {count}")


def print_no_touch_by_risk(no_touch: Dict[str, int]) -> None:
    print("\nNo-Touch by Risk")
    print("----------------")
    if not no_touch:
        print("No missing-touch data.")
        return
    print(f"High risk: {no_touch.get('high', 0)}")
    print(f"Medium risk: {no_touch.get('medium', 0)}")
    print(f"Low risk: {no_touch.get('low', 0)}")


def print_status_by_risk(status_by_risk: Dict[str, Dict[str, int]]) -> None:
    print("\nStatus by Risk Tier")
    print("-------------------")
    if not status_by_risk:
        print("No risk-tier status data.")
        return
    header = f"{'Risk':<8} {'Overdue':>7} {'DueSoon':>7} {'OnTrack':>7} {'NoTouch':>7}"
    print(header)
    print("-" * len(header))
    for tier in ("high", "medium", "low"):
        bucket = status_by_risk.get(tier, {})
        print(
            f"{tier:<8} {bucket.get('overdue', 0):>7} {bucket.get('due_soon', 0):>7} "
            f"{bucket.get('on_track', 0):>7} {bucket.get('no_touch', 0):>7}"
        )


def print_touchpoint_horizon(horizon: Dict[str, int]) -> None:
    print("\nTouchpoint Horizon")
    print("------------------")
    if not horizon:
        print("No touchpoint horizon data.")
        return
    print(f"Overdue: {horizon.get('overdue', 0)}")
    print(f"Next 7 days: {horizon.get('next_7_days', 0)}")
    print(f"Next 14 days: {horizon.get('next_14_days', 0)}")
    print(f"Next 30 days: {horizon.get('next_30_days', 0)}")
    print(f"Later: {horizon.get('later', 0)}")
    print(f"No due date: {horizon.get('no_due_date', 0)}")


def print_touchpoint_forecast(forecast: Dict[str, object]) -> None:
    print("\nTouchpoint Forecast")
    print("-------------------")
    if not forecast:
        print("No touchpoint forecast data.")
        return
    window_days = int(forecast.get("window_days", 0))
    include_overdue = bool(forecast.get("include_overdue", False))
    overdue = int(forecast.get("overdue", 0))
    no_due_date = int(forecast.get("no_due_date", 0))
    beyond_window = int(forecast.get("beyond_window", 0))
    daily = forecast.get("daily", [])
    print(f"Window: next {window_days} days")
    print(f"Overdue touches: {overdue} ({'included' if include_overdue else 'excluded'} in day 0)")
    print(f"No due date: {no_due_date}")
    print(f"Beyond window: {beyond_window}")
    print("Daily load:")
    for item in daily:
        print(f"  {item['date']}: {item['count']}")


def print_owner_capacity(capacity: List[Dict[str, object]]) -> None:
    print("\nOwner Capacity Plan")
    print("-------------------")
    if not capacity:
        print("No owner capacity data available.")
        return
    header = (
        f"{'Owner':<18} {'DueWin':>7} {'Overdue':>7} {'Capacity':>9} "
        f"{'Util':>6} {'Gap':>5}"
    )
    print(header)
    print("-" * len(header))
    for bucket in capacity:
        print(
            f"{bucket['owner'][:18]:<18} {bucket['due_within_window']:>7} {bucket['overdue']:>7} "
            f"{bucket['capacity']:>9} {bucket['utilization']:>6.2f} {bucket['gap']:>5}"
        )


def print_stale_touch_by_risk(stale_touch: Dict[str, int]) -> None:
    print("\nStale Touches by Risk")
    print("---------------------")
    if not stale_touch:
        print("No stale-touch data.")
        return
    print(f"High risk: {stale_touch.get('high', 0)}")
    print(f"Medium risk: {stale_touch.get('medium', 0)}")
    print(f"Low risk: {stale_touch.get('low', 0)}")


def print_channel_mix(mix: Dict[str, int]) -> None:
    print("\nChannel Mix")
    print("-----------")
    if not mix:
        print("No channel data available.")
        return
    for channel, count in mix.items():
        print(f"{channel:<10} {count}")


def print_flag_highlights(flag_counts: Dict[str, int]) -> None:
    print("\nHigh-Impact Flags")
    print("-----------------")
    if not flag_counts:
        print("No high-impact flags captured.")
        return
    for flag, count in flag_counts.items():
        print(f"{flag:<12} {count}")


def print_cohort_summary(cohorts: List[Dict[str, object]], limit: int) -> None:
    print("\nCohort Hotspots")
    print("---------------")
    if not cohorts:
        print("No cohort data available.")
        return
    header = f"{'Cohort':<16} {'Total':>5} {'Overdue':>7} {'DueSoon':>7} {'NoTouch':>7} {'AvgScore':>9}"
    print(header)
    print("-" * len(header))
    for bucket in cohorts[:limit]:
        print(
            f"{bucket['cohort'][:16]:<16} {bucket['total']:>5} {bucket['overdue']:>7} "
            f"{bucket['due_soon']:>7} {bucket['no_touch']:>7} {bucket['avg_priority']:>9.1f}"
        )


def print_owner_summary(owners: List[Dict[str, object]], limit: int) -> None:
    print("\nOwner Load")
    print("----------")
    if not owners:
        print("No owner data available.")
        return
    header = f"{'Owner':<18} {'Total':>5} {'Overdue':>7} {'DueSoon':>7} {'NoTouch':>7} {'AvgScore':>9}"
    print(header)
    print("-" * len(header))
    for bucket in owners[:limit]:
        print(
            f"{bucket['owner'][:18]:<18} {bucket['total']:>5} {bucket['overdue']:>7} "
            f"{bucket['due_soon']:>7} {bucket['no_touch']:>7} {bucket['avg_priority']:>9.1f}"
        )


def print_owner_horizon(owners: List[Dict[str, object]], limit: int) -> None:
    print("\nOwner Touchpoint Horizon")
    print("-------------------------")
    if not owners:
        print("No owner horizon data available.")
        return
    header = (
        f"{'Owner':<18} {'Overdue':>7} {'Next7':>6} {'Next14':>6} "
        f"{'Next30':>6} {'Later':>5} {'NoDue':>5} {'AvgScore':>9}"
    )
    print(header)
    print("-" * len(header))
    for bucket in owners[:limit]:
        print(
            f"{bucket['owner'][:18]:<18} {bucket['overdue']:>7} {bucket['next_7_days']:>6} "
            f"{bucket['next_14_days']:>6} {bucket['next_30_days']:>6} {bucket['later']:>5} "
            f"{bucket['no_due_date']:>5} {bucket['avg_priority']:>9.1f}"
        )


def print_owner_alerts(alerts: List[Dict[str, object]]) -> None:
    print("\nOwner Alerts")
    print("------------")
    if not alerts:
        print("No owners currently exceed alert thresholds.")
        return
    for alert in alerts:
        reasons = "; ".join(alert["reasons"])
        print(
            f"{alert['owner']}: total {alert['total']}, overdue {alert['overdue']}, "
            f"no-touch {alert['no_touch']} -> {reasons}"
        )


def print_owner_queue(owner_queue: List[Dict[str, object]]) -> None:
    print("\nOwner Action Queue")
    print("------------------")
    if not owner_queue:
        print("No owner queue data available.")
        return
    for bucket in owner_queue:
        print(f"{bucket['owner']} (top {len(bucket['items'])} of {bucket['total']} total)")
        for item in bucket["items"]:
            due = item["due_date"] or "-"
            print(
                f"  {item['priority_score']:6.1f}  {item['name'][:20]:<20} "
                f"{item['cohort'][:10]:<10} {item['status']:<9} {due:<10}"
            )
            print(f"       -> {item['recommended_action']}")


def print_channel_batches(channel_batches: List[Dict[str, object]]) -> None:
    print("\nChannel Batch Plan")
    print("------------------")
    if not channel_batches:
        print("No channel batch data available.")
        return
    for bucket in channel_batches:
        channel = bucket["channel"]
        print(
            f"{channel} (total {bucket['total']}, overdue {bucket['overdue']}, "
            f"due-soon {bucket['due_soon']}, no-touch {bucket['no_touch']})"
        )
        for item in bucket["items"]:
            due = item["due_date"] or "-"
            print(
                f"  {item['priority_score']:6.1f}  {item['name'][:20]:<20} "
                f"{item['cohort'][:10]:<10} {item['owner'][:12]:<12} {item['status']:<9} {due:<10}"
            )
            print(f"       -> {item['recommended_action']}")


def print_escalation_list(escalations: List[Dict[str, object]]) -> None:
    print("\nEscalation Candidates")
    print("---------------------")
    if not escalations:
        print("No escalation candidates based on current thresholds.")
        return
    for item in escalations:
        due = item["due_date"] or "-"
        reasons = "; ".join(item.get("priority_reasons", []))
        print(
            f"{item['priority_score']:6.1f}  {item['name'][:20]:<20} {item['owner'][:14]:<14} "
            f"{item['status']:<9} {due:<10}"
        )
        print(f"      -> {item['recommended_action']}")
        if reasons:
            print(f"      -> Reasons: {reasons}")


def print_action_queue(scored: List[ScoredRecord], limit: int, explain: bool) -> None:
    print("\nPriority Action Queue")
    print("---------------------")
    header = (
        f"{'Score':>6}  {'Scholar':<20} {'Owner':<14} {'Cohort':<10} {'Risk':>5}  "
        f"{'Status':<9} {'Due':<10} {'Delta':>6}"
    )
    print(header)
    print("-" * len(header))
    for record in scored[:limit]:
        due = record.due_date or "-"
        delta = "-" if record.due_in_days is None else f"{record.due_in_days:+d}"
        print(
            f"{record.priority_score:6.1f}  {record.name[:20]:<20} {record.owner[:14]:<14} "
            f"{record.cohort[:10]:<10} {record.risk_score:5.1f}  {record.status:<9} {due:<10} {delta:>6}"
        )
        print(f"      -> {record.recommended_action}")
        if explain and record.priority_reasons:
            reasons = "; ".join(record.priority_reasons)
            print(f"      -> Reasons: {reasons}")


def print_cadence_guidance() -> None:
    print("\nCadence Guidance")
    print("----------------")
    print("High risk: touch every 7 days")
    print("Medium risk: touch every 21 days")
    print("Low risk: touch every 45 days")


def build_report(
    records: List[ScholarRecord],
    today: date,
    high: float,
    medium: float,
    soon_days: int,
    stale_days: int,
    stale_boost: float,
) -> List[ScoredRecord]:
    scored = [compute_priority(record, today, high, medium, soon_days, stale_days, stale_boost) for record in records]
    scored.sort(key=lambda item: item.priority_score, reverse=True)
    return scored


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Group Scholar Intervention Planner: prioritize scholar touchpoints based on risk and cadence."
    )
    parser.add_argument("--input", required=True, help="Path to intake CSV")
    parser.add_argument("--limit", type=int, default=10, help="Number of priority actions to show")
    parser.add_argument("--high-risk", type=float, default=70, help="Risk score threshold for high risk")
    parser.add_argument("--medium-risk", type=float, default=40, help="Risk score threshold for medium risk")
    parser.add_argument("--soon-days", type=int, default=14, help="Days ahead to flag as due soon")
    parser.add_argument("--cohort-limit", type=int, default=5, help="Number of cohorts to list in hotspot summary")
    parser.add_argument("--owner-limit", type=int, default=5, help="Number of owners to list in load summary")
    parser.add_argument("--owner-queue-limit", type=int, default=5, help="Number of owners to show in the action queue")
    parser.add_argument("--owner-queue-size", type=int, default=3, help="Number of actions to show per owner")
    parser.add_argument("--owner-overdue-threshold", type=int, default=2, help="Overdue count to flag an owner")
    parser.add_argument("--owner-no-touch-threshold", type=int, default=1, help="No-touch count to flag an owner")
    parser.add_argument("--owner-total-threshold", type=int, default=8, help="Total count to flag an owner")
    parser.add_argument("--channel-batch-limit", type=int, default=4, help="Number of channels to show in the batch plan")
    parser.add_argument("--channel-batch-size", type=int, default=3, help="Number of actions to show per channel batch")
    parser.add_argument("--escalation-limit", type=int, default=5, help="Number of escalation candidates to show")
    parser.add_argument(
        "--escalation-min-score",
        type=float,
        default=90,
        help="Minimum priority score for escalation candidates",
    )
    parser.add_argument(
        "--forecast-window-days",
        type=int,
        default=21,
        help="Days ahead to include in the touchpoint forecast",
    )
    parser.add_argument(
        "--forecast-include-overdue",
        action="store_true",
        help="Include overdue touches in the forecast day 0 count",
    )
    parser.add_argument(
        "--owner-capacity-window-days",
        type=int,
        default=7,
        help="Window (days) to size owner capacity planning",
    )
    parser.add_argument(
        "--owner-daily-capacity",
        type=int,
        default=3,
        help="Expected daily touch capacity per owner",
    )
    parser.add_argument(
        "--owner-capacity-exclude-overdue",
        action="store_true",
        help="Exclude overdue touches from owner capacity counts",
    )
    parser.add_argument("--stale-days", type=int, default=60, help="Days since last touch to flag as stale")
    parser.add_argument("--stale-boost", type=float, default=15, help="Priority boost for stale last-touch records")
    parser.add_argument("--today", help="Override today's date (YYYY-MM-DD)")
    parser.add_argument("--json", dest="json_path", help="Optional path to write JSON output")
    parser.add_argument("--explain", action="store_true", help="Show priority reasons in the action queue")
    parser.add_argument("--db-write", action="store_true", help="Write the run + records to Postgres")
    parser.add_argument("--db-schema", default=DEFAULT_DB_SCHEMA, help="Postgres schema for planner tables")
    parser.add_argument("--run-label", help="Optional label to tag the database run")
    return parser.parse_args()


def resolve_db_dsn() -> Optional[str]:
    explicit = os.getenv("GS_DB_DSN") or os.getenv("DATABASE_URL")
    if explicit:
        return explicit
    host = os.getenv("GS_DB_HOST")
    port = os.getenv("GS_DB_PORT", "5432")
    name = os.getenv("GS_DB_NAME")
    user = os.getenv("GS_DB_USER")
    password = os.getenv("GS_DB_PASSWORD")
    if not all([host, name, user, password]):
        return None
    sslmode = os.getenv("GS_DB_SSLMODE", "require")
    return f"postgresql://{user}:{password}@{host}:{port}/{name}?sslmode={sslmode}"


def require_psycopg() -> "module":
    try:
        import psycopg  # type: ignore
    except ImportError as exc:
        raise SystemExit("psycopg is required for --db-write. Install with: pip install psycopg[binary]") from exc
    return psycopg


def ensure_db(conn: "object", schema: str) -> None:
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.runs (
                id SERIAL PRIMARY KEY,
                run_label TEXT,
                generated_at TIMESTAMP NOT NULL,
                today DATE NOT NULL,
                input_path TEXT NOT NULL,
                high_risk DOUBLE PRECISION NOT NULL,
                medium_risk DOUBLE PRECISION NOT NULL,
                soon_days INTEGER NOT NULL,
                action_limit INTEGER NOT NULL,
                cohort_limit INTEGER NOT NULL,
                owner_limit INTEGER NOT NULL,
                summary JSONB NOT NULL,
                channel_mix JSONB NOT NULL,
                high_impact_flags JSONB NOT NULL,
                cohort_summary JSONB NOT NULL,
                owner_summary JSONB NOT NULL,
                owner_horizon JSONB NOT NULL,
                owner_capacity JSONB NOT NULL,
                owner_queue JSONB NOT NULL,
                owner_alerts JSONB NOT NULL,
                touchpoint_forecast JSONB NOT NULL,
                channel_batch_limit INTEGER NOT NULL,
                channel_batch_size INTEGER NOT NULL,
                channel_batches JSONB NOT NULL,
                escalation_candidates JSONB NOT NULL
            )
            """
        )
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.run_records (
                id SERIAL PRIMARY KEY,
                run_id INTEGER NOT NULL REFERENCES {schema}.runs(id) ON DELETE CASCADE,
                scholar_id TEXT NOT NULL,
                name TEXT NOT NULL,
                cohort TEXT NOT NULL,
                owner TEXT NOT NULL,
                channel_preference TEXT NOT NULL,
                last_touch DATE,
                risk_score DOUBLE PRECISION NOT NULL,
                flags TEXT[] NOT NULL,
                cadence_days INTEGER NOT NULL,
                due_date DATE,
                days_since_touch INTEGER,
                due_in_days INTEGER,
                overdue_days INTEGER,
                status TEXT NOT NULL,
                priority_score DOUBLE PRECISION NOT NULL,
                priority_reasons TEXT[] NOT NULL,
                recommended_action TEXT NOT NULL,
                stale_touch BOOLEAN NOT NULL DEFAULT FALSE,
                stale_days INTEGER
            )
            """
        )
        cur.execute(
            f"ALTER TABLE {schema}.runs ADD COLUMN IF NOT EXISTS owner_limit INTEGER NOT NULL DEFAULT 0"
        )
        cur.execute(
            f"ALTER TABLE {schema}.runs ADD COLUMN IF NOT EXISTS owner_summary JSONB NOT NULL DEFAULT '{{}}'::jsonb"
        )
        cur.execute(
            f"ALTER TABLE {schema}.runs ADD COLUMN IF NOT EXISTS owner_horizon JSONB NOT NULL DEFAULT '[]'::jsonb"
        )
        cur.execute(
            f"ALTER TABLE {schema}.runs ADD COLUMN IF NOT EXISTS owner_capacity JSONB NOT NULL DEFAULT '[]'::jsonb"
        )
        cur.execute(
            f"ALTER TABLE {schema}.runs ADD COLUMN IF NOT EXISTS owner_queue JSONB NOT NULL DEFAULT '[]'::jsonb"
        )
        cur.execute(
            f"ALTER TABLE {schema}.runs ADD COLUMN IF NOT EXISTS owner_alerts JSONB NOT NULL DEFAULT '[]'::jsonb"
        )
        cur.execute(
            f"ALTER TABLE {schema}.runs ADD COLUMN IF NOT EXISTS channel_batch_limit INTEGER NOT NULL DEFAULT 0"
        )
        cur.execute(
            f"ALTER TABLE {schema}.runs ADD COLUMN IF NOT EXISTS channel_batch_size INTEGER NOT NULL DEFAULT 0"
        )
        cur.execute(
            f"ALTER TABLE {schema}.runs ADD COLUMN IF NOT EXISTS channel_batches JSONB NOT NULL DEFAULT '[]'::jsonb"
        )
        cur.execute(
            f"ALTER TABLE {schema}.runs ADD COLUMN IF NOT EXISTS escalation_candidates JSONB NOT NULL DEFAULT '[]'::jsonb"
        )
        cur.execute(
            f"ALTER TABLE {schema}.runs ADD COLUMN IF NOT EXISTS touchpoint_forecast JSONB NOT NULL DEFAULT '{{}}'::jsonb"
        )
        cur.execute(
            f"ALTER TABLE {schema}.run_records ADD COLUMN IF NOT EXISTS owner TEXT NOT NULL DEFAULT 'Unassigned'"
        )
        cur.execute(
            f"ALTER TABLE {schema}.run_records ADD COLUMN IF NOT EXISTS due_in_days INTEGER"
        )
        cur.execute(
            f"ALTER TABLE {schema}.run_records ADD COLUMN IF NOT EXISTS overdue_days INTEGER"
        )
        cur.execute(
            f"ALTER TABLE {schema}.run_records ADD COLUMN IF NOT EXISTS priority_reasons TEXT[] NOT NULL DEFAULT '{{}}'::text[]"
        )
        cur.execute(
            f"ALTER TABLE {schema}.run_records ADD COLUMN IF NOT EXISTS stale_touch BOOLEAN NOT NULL DEFAULT FALSE"
        )
        cur.execute(
            f"ALTER TABLE {schema}.run_records ADD COLUMN IF NOT EXISTS stale_days INTEGER"
        )
    conn.commit()


def write_run_to_db(
    dsn: str,
    schema: str,
    run_label: Optional[str],
    args: argparse.Namespace,
    payload: Dict[str, object],
) -> None:
    psycopg = require_psycopg()
    with psycopg.connect(dsn) as conn:
        ensure_db(conn, schema)
        with conn.cursor() as cur:
            generated_at = datetime.fromisoformat(str(payload["generated_at"]))
            today_value = date.fromisoformat(str(payload["today"]))
            cur.execute(
                f"""
                INSERT INTO {schema}.runs (
                    run_label,
                    generated_at,
                    today,
                    input_path,
                    high_risk,
                    medium_risk,
                    soon_days,
                    action_limit,
                    cohort_limit,
                    owner_limit,
                    channel_batch_limit,
                    channel_batch_size,
                    summary,
                    channel_mix,
                    high_impact_flags,
                    cohort_summary,
                    owner_summary,
                    owner_horizon,
                    owner_capacity,
                    owner_queue,
                    owner_alerts,
                    touchpoint_forecast,
                    channel_batches,
                    escalation_candidates
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
            (
                run_label,
                generated_at,
                today_value,
                args.input,
                args.high_risk,
                args.medium_risk,
                args.soon_days,
                args.limit,
                args.cohort_limit,
                args.owner_limit,
                args.channel_batch_limit,
                args.channel_batch_size,
                json.dumps(payload["summary"]),
                json.dumps(payload["channel_mix"]),
                json.dumps(payload["high_impact_flags"]),
                json.dumps(payload["cohort_summary"]),
                json.dumps(payload["owner_summary"]),
                json.dumps(payload["owner_horizon"]),
                json.dumps(payload["owner_capacity"]),
                json.dumps(payload["owner_queue"]),
                json.dumps(payload["summary"].get("owner_alerts", [])),
                json.dumps(payload["touchpoint_forecast"]),
                json.dumps(payload["channel_batches"]),
                json.dumps(payload["escalation_candidates"]),
            ),
        )
            run_id = cur.fetchone()[0]
            records = []
            for record in payload["records"]:
                last_touch = record["last_touch"]
                due_date = record["due_date"]
                records.append(
                    (
                        run_id,
                        record["scholar_id"],
                        record["name"],
                        record["cohort"],
                        record["owner"],
                        record["channel_preference"],
                        date.fromisoformat(last_touch) if last_touch else None,
                        record["risk_score"],
                        record["flags"],
                        record["cadence_days"],
                        date.fromisoformat(due_date) if due_date else None,
                        record["days_since_touch"],
                        record["due_in_days"],
                        record["overdue_days"],
                        record["status"],
                        record["priority_score"],
                        record.get("priority_reasons", []),
                        record["recommended_action"],
                        record.get("stale_touch", False),
                        record.get("stale_days"),
                    )
                )
            cur.executemany(
                f"""
                INSERT INTO {schema}.run_records (
                    run_id,
                    scholar_id,
                    name,
                    cohort,
                    owner,
                    channel_preference,
                    last_touch,
                    risk_score,
                    flags,
                    cadence_days,
                    due_date,
                    days_since_touch,
                    due_in_days,
                    overdue_days,
                    status,
                    priority_score,
                    priority_reasons,
                    recommended_action,
                    stale_touch,
                    stale_days
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                records,
            )
        conn.commit()


def main() -> None:
    args = parse_args()
    today = date.today()
    if args.today:
        parsed = parse_date(args.today)
        if not parsed:
            raise SystemExit("Invalid --today date format. Use YYYY-MM-DD.")
        today = parsed

    records = load_csv(args.input)
    scored = build_report(
        records,
        today,
        args.high_risk,
        args.medium_risk,
        args.soon_days,
        args.stale_days,
        args.stale_boost,
    )
    summary = summarize(scored)
    channel_mix = summarize_channels(scored)
    flag_counts = summarize_flags(scored)
    cohorts = summarize_cohorts(scored)
    owners = summarize_owners(scored)
    owner_horizon = summarize_owner_horizon(scored)
    owner_capacity = summarize_owner_capacity(
        scored,
        args.owner_capacity_window_days,
        args.owner_daily_capacity,
        include_overdue=not args.owner_capacity_exclude_overdue,
    )
    owner_alerts = build_owner_alerts(
        owners,
        overdue_threshold=args.owner_overdue_threshold,
        no_touch_threshold=args.owner_no_touch_threshold,
        total_threshold=args.owner_total_threshold,
    )
    owner_queue = build_owner_queue(scored, args.owner_queue_limit, args.owner_queue_size)
    channel_batches = build_channel_batches(scored, args.channel_batch_limit, args.channel_batch_size)
    escalation_candidates = build_escalation_list(scored, args.escalation_limit, args.escalation_min_score)
    touchpoint_forecast = summarize_touchpoint_forecast(
        scored,
        today,
        args.forecast_window_days,
        args.forecast_include_overdue,
    )

    summary["owner_alerts"] = owner_alerts

    print_summary(summary)
    print_overdue_aging(summary["overdue_aging"])
    print_no_touch_by_risk(summary["no_touch_by_risk"])
    print_status_by_risk(summary["status_by_risk"])
    print_touchpoint_horizon(summary["touchpoint_horizon"])
    print_touchpoint_forecast(touchpoint_forecast)
    print_stale_touch_by_risk(summary["stale_touch_by_risk"])
    print_channel_mix(channel_mix)
    print_flag_highlights(flag_counts)
    print_cohort_summary(cohorts, args.cohort_limit)
    print_owner_summary(owners, args.owner_limit)
    print_owner_horizon(owner_horizon, args.owner_limit)
    print_owner_capacity(owner_capacity)
    print_owner_alerts(owner_alerts)
    print_owner_queue(owner_queue)
    print_channel_batches(channel_batches)
    print_escalation_list(escalation_candidates)
    print_action_queue(scored, args.limit, args.explain)
    print_cadence_guidance()

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "today": today.isoformat(),
        "summary": summary,
        "channel_mix": channel_mix,
        "high_impact_flags": flag_counts,
        "cohort_summary": cohorts,
        "owner_summary": owners,
        "owner_horizon": owner_horizon,
        "owner_capacity": owner_capacity,
        "owner_queue": owner_queue,
        "touchpoint_forecast": touchpoint_forecast,
        "channel_batches": channel_batches,
        "escalation_candidates": escalation_candidates,
        "records": [asdict(record) for record in scored],
    }

    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        print(f"\nJSON report written to {args.json_path}")

    if args.db_write:
        dsn = resolve_db_dsn()
        if not dsn:
            raise SystemExit("Database env vars missing. Set GS_DB_DSN or GS_DB_HOST/GS_DB_NAME/GS_DB_USER/GS_DB_PASSWORD.")
        schema = validate_schema_name(args.db_schema)
        run_label = args.run_label or default_run_label(args.input, today)
        write_run_to_db(dsn, schema, run_label, args, payload)
        print(f"\nDatabase run stored in schema '{schema}'.")


if __name__ == "__main__":
    main()
