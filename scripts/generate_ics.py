#!/usr/bin/env python3
"""Generate an ICS calendar with events every N days from a start date."""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "config.json"
DEFAULT_OUTPUT = REPO_ROOT / "events.ics"


def load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def escape_ics_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def fold_ics_line(line: str, limit: int = 75) -> list[str]:
    if len(line) <= limit:
        return [line]
    lines = [line[:limit]]
    rest = line[limit:]
    while rest:
        lines.append(" " + rest[: limit - 1])
        rest = rest[limit - 1 :]
    return lines


def format_date(value: date) -> str:
    return value.strftime("%Y%m%d")


def format_offset(offset: timedelta | None) -> str:
    if offset is None:
        return "+0000"
    total_seconds = int(offset.total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    total_seconds = abs(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    return f"{sign}{hours:02d}{minutes:02d}"


def find_year_transitions(
    tz: ZoneInfo, year: int
) -> list[tuple[datetime, timedelta, timedelta]]:
    transitions: list[tuple[datetime, timedelta, timedelta]] = []
    cursor = datetime(year, 1, 1, tzinfo=tz)
    end = datetime(year + 1, 1, 1, tzinfo=tz)
    previous_offset = cursor.utcoffset()
    while cursor < end:
        cursor += timedelta(hours=1)
        current_offset = cursor.utcoffset()
        if current_offset != previous_offset:
            transitions.append((cursor, previous_offset, current_offset))
            previous_offset = current_offset
    return transitions


def build_vtimezone(tzname: str) -> list[str]:
    tz = ZoneInfo(tzname)
    lines = ["BEGIN:VTIMEZONE", f"TZID:{escape_ics_text(tzname)}"]

    transitions = find_year_transitions(tz, 2024)
    if not transitions:
        offset = format_offset(datetime(2024, 1, 15, 12, 0, tzinfo=tz).utcoffset())
        lines.extend(
            [
                "BEGIN:STANDARD",
                "DTSTART:19700101T000000",
                f"TZOFFSETFROM:{offset}",
                f"TZOFFSETTO:{offset}",
                "END:STANDARD",
            ]
        )
    elif len(transitions) == 2:
        (spring, spring_from, spring_to), (autumn, autumn_from, autumn_to) = transitions
        if spring_to > spring_from:
            daylight = (spring, spring_from, spring_to)
            standard = (autumn, autumn_from, autumn_to)
        else:
            daylight = (autumn, autumn_from, autumn_to)
            standard = (spring, spring_from, spring_to)

        daylight_start, daylight_from, daylight_to = daylight
        standard_start, standard_from, standard_to = standard
        lines.extend(
            [
                "BEGIN:DAYLIGHT",
                f"DTSTART:{daylight_start.strftime('%Y%m%dT%H%M%S')}",
                f"TZOFFSETFROM:{format_offset(daylight_from)}",
                f"TZOFFSETTO:{format_offset(daylight_to)}",
                "END:DAYLIGHT",
                "BEGIN:STANDARD",
                f"DTSTART:{standard_start.strftime('%Y%m%dT%H%M%S')}",
                f"TZOFFSETFROM:{format_offset(standard_from)}",
                f"TZOFFSETTO:{format_offset(standard_to)}",
                "END:STANDARD",
            ]
        )
    else:
        offset = format_offset(datetime(2024, 1, 15, 12, 0, tzinfo=tz).utcoffset())
        lines.extend(
            [
                "BEGIN:STANDARD",
                "DTSTART:19700101T000000",
                f"TZOFFSETFROM:{offset}",
                f"TZOFFSETTO:{offset}",
                "END:STANDARD",
            ]
        )

    lines.append("END:VTIMEZONE")
    return lines


def resolve_timezone(config: dict) -> str | None:
    tzname = config.get("timezone")
    if tzname is None or tzname == "":
        return None
    if not isinstance(tzname, str):
        raise ValueError("timezone must be a string IANA timezone name")
    if tzname.upper() in {"UTC", "Z"}:
        return "UTC"
    try:
        ZoneInfo(tzname)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {tzname!r}") from exc
    return tzname


def format_event_template(template: str, day_offset: int, event_date: date) -> str:
    return template.format(days=day_offset, date=event_date.isoformat())


def build_event(
    day_offset: int,
    event_date: date,
    title: str,
    description: str,
    stamp: datetime,
    tzname: str | None,
) -> str:
    uid = f"day-{day_offset}@my-calendar-events"
    if tzname:
        dtstart = f"DTSTART;TZID={escape_ics_text(tzname)};VALUE=DATE:{format_date(event_date)}"
    else:
        dtstart = f"DTSTART;VALUE=DATE:{format_date(event_date)}"
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{stamp.strftime('%Y%m%dT%H%M%SZ')}",
        dtstart,
        f"SUMMARY:{escape_ics_text(title)}",
        f"DESCRIPTION:{escape_ics_text(description)}",
        "END:VEVENT",
    ]
    return "\r\n".join(lines)


def generate_ics(config: dict) -> str:
    start = parse_date(config["start_date"])
    interval = int(config["interval_days"])
    years_ahead = int(config.get("years_ahead", 10))
    title_template = config.get("title_template", "It is {days} days!")
    description_template = config.get(
        "description_template", "{days} days since the start date."
    )
    tzname = resolve_timezone(config)

    if interval <= 0:
        raise ValueError("interval_days must be positive")

    end = date.today() + timedelta(days=365 * years_ahead)
    stamp = datetime.now(timezone.utc)

    events: list[str] = []
    day_offset = 0
    event_date = start

    while event_date <= end:
        title = format_event_template(title_template, day_offset, event_date)
        description = format_event_template(description_template, day_offset, event_date)
        events.append(
            build_event(day_offset, event_date, title, description, stamp, tzname)
        )
        day_offset += interval
        event_date = start + timedelta(days=day_offset)

    header = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//my_calendar_events//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    if tzname:
        header.append(f"X-WR-TIMEZONE:{escape_ics_text(tzname)}")

    timezone_block: list[str] = []
    if tzname and tzname != "UTC":
        timezone_block = build_vtimezone(tzname)

    footer = ["END:VCALENDAR"]

    body = "\r\n".join(header + timezone_block + events + footer) + "\r\n"
    folded: list[str] = []
    for line in body.splitlines():
        folded.extend(fold_ics_line(line))
    return "\r\n".join(folded) + "\r\n"


def main() -> int:
    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CONFIG
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT

    config = load_config(config_path)
    ics_content = generate_ics(config)

    output_path.write_text(ics_content, encoding="utf-8")
    event_count = ics_content.count("BEGIN:VEVENT")
    print(f"Wrote {event_count} events to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
