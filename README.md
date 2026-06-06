# my_calendar_events

Automatically generates an `.ics` calendar file with recurring events every N days from a start date.

## Configuration

Edit [`config.json`](config.json):

| Field | Description | Example |
|-------|-------------|---------|
| `start_date` | First event date (YYYY-MM-DD) | `"2026-03-14"` |
| `interval_days` | Days between events | `50` |
| `years_ahead` | How far into the future to generate events | `10` |
| `timezone` | IANA timezone for all-day event dates (optional) | `"Europe/Berlin"` |
| `title_template` | Event title; `{days}` = days since start | `"It is {days} days!"` |

Use any [IANA timezone name](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) (e.g. `America/New_York`, `Asia/Tokyo`). Omit `timezone` to use floating all-day dates with no timezone attached.

With the default config, events appear on March 14, 2026, then every 50 days after that, with titles like **It is 0 days!**, **It is 50 days!**, **It is 100 days!**, and so on.

## GitHub Action

The workflow in [`.github/workflows/generate-calendar.yml`](.github/workflows/generate-calendar.yml):

- Runs on a weekly schedule
- Runs when you push changes to `config.json` or the generator script
- Can be triggered manually from the Actions tab (`workflow_dispatch`)
- Commits the updated [`events.ics`](events.ics) back to the repository

After pushing to GitHub, subscribe to the raw `events.ics` URL in Google Calendar, Apple Calendar, or Outlook.

## Local generation

```bash
python3 scripts/generate_ics.py
```

Optional arguments: `python3 scripts/generate_ics.py [config.json] [output.ics]`
