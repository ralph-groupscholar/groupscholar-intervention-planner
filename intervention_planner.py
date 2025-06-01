#!/usr/bin/env python3
import argparse
import csv
import json
from dataclasses import dataclass, asdict
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Tuple

HIGH_IMPACT_FLAGS = {"crisis", "housing", "food", "health", "safety", "financial"}


@dataclass
class ScholarRecord:
    scholar_id: str
    name: str
    cohort: str
    channel_preference: str
    last_touch: Optional[date]
    risk_score: float
    flags: List[str]


@dataclass
class ScoredRecord:
    scholar_id: str
    name: str
    cohort: str
    channel_preference: str
    last_touch: Optional[str]
    risk_score: float
    flags: List[str]
    cadence_days: int
    due_date: Optional[str]
    days_since_touch: Optional[int]
    status: str
    priority_score: float
    recommended_action: str


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


def compute_priority(record: ScholarRecord, today: date, high: float, medium: float, soon_days: int) -> ScoredRecord:
    tier, cadence_days = cadence_for_risk(record.risk_score, high, medium)
    if record.last_touch:
        days_since = (today - record.last_touch).days
        due_date = record.last_touch + timedelta(days=cadence_days)
        overdue = today > due_date
        due_soon = today <= due_date <= today + timedelta(days=soon_days)
    else:
        days_since = None
        due_date = None
        overdue = False
        due_soon = False

    priority = record.risk_score
    if record.last_touch is None:
        priority += 25
    if overdue:
        priority += 30
    elif due_soon:
        priority += 12

    for flag in record.flags:
        if flag in HIGH_IMPACT_FLAGS:
            priority += 8

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
        channel_preference=record.channel_preference,
        last_touch=record.last_touch.isoformat() if record.last_touch else None,
        risk_score=record.risk_score,
        flags=record.flags,
        cadence_days=cadence_days,
        due_date=due_date.isoformat() if due_date else None,
        days_since_touch=days_since,
        status=status,
        priority_score=round(priority, 2),
        recommended_action=recommended_action,
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


def summarize(scored: List[ScoredRecord]) -> Dict[str, int]:
    summary = {
        "total": len(scored),
        "overdue": 0,
        "due_soon": 0,
        "on_track": 0,
        "no_touch": 0,
        "high_risk": 0,
        "medium_risk": 0,
        "low_risk": 0,
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
    return summary


def normalize_channel(channel: str) -> str:
    value = (channel or "").strip().lower()
    if not value:
        return "unknown"
    if value in {"sms", "text"}:
        return "sms"
    if value in {"phone", "call"}:
        return "call"
    return value


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


def print_summary(summary: Dict[str, int]) -> None:
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


def print_action_queue(scored: List[ScoredRecord], limit: int) -> None:
    print("\nPriority Action Queue")
    print("---------------------")
    header = f"{'Score':>6}  {'Scholar':<20} {'Cohort':<10} {'Risk':>5}  {'Status':<9} {'Due':<10}"
    print(header)
    print("-" * len(header))
    for record in scored[:limit]:
        due = record.due_date or "-"
        print(
            f"{record.priority_score:6.1f}  {record.name[:20]:<20} {record.cohort[:10]:<10} "
            f"{record.risk_score:5.1f}  {record.status:<9} {due:<10}"
        )
        print(f"      -> {record.recommended_action}")


def print_cadence_guidance() -> None:
    print("\nCadence Guidance")
    print("----------------")
    print("High risk: touch every 7 days")
    print("Medium risk: touch every 21 days")
    print("Low risk: touch every 45 days")


def build_report(records: List[ScholarRecord], today: date, high: float, medium: float, soon_days: int) -> List[ScoredRecord]:
    scored = [compute_priority(record, today, high, medium, soon_days) for record in records]
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
    parser.add_argument("--today", help="Override today's date (YYYY-MM-DD)")
    parser.add_argument("--json", dest="json_path", help="Optional path to write JSON output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    today = date.today()
    if args.today:
        parsed = parse_date(args.today)
        if not parsed:
            raise SystemExit("Invalid --today date format. Use YYYY-MM-DD.")
        today = parsed

    records = load_csv(args.input)
    scored = build_report(records, today, args.high_risk, args.medium_risk, args.soon_days)
    summary = summarize(scored)
    channel_mix = summarize_channels(scored)
    flag_counts = summarize_flags(scored)
    cohorts = summarize_cohorts(scored)

    print_summary(summary)
    print_channel_mix(channel_mix)
    print_flag_highlights(flag_counts)
    print_cohort_summary(cohorts, args.cohort_limit)
    print_action_queue(scored, args.limit)
    print_cadence_guidance()

    if args.json_path:
        payload = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "today": today.isoformat(),
            "summary": summary,
            "channel_mix": channel_mix,
            "high_impact_flags": flag_counts,
            "cohort_summary": cohorts,
            "records": [asdict(record) for record in scored],
        }
        with open(args.json_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        print(f"\nJSON report written to {args.json_path}")


if __name__ == "__main__":
    main()
