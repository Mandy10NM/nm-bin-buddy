from datetime import datetime, timedelta
import pytz

TIMEZONE = "Europe/London"
REMINDER_TIME = "T163000"
CAL_NAME = "NM Bin Buddy"

tz = pytz.timezone(TIMEZONE)

# Tue 10 March 2026 = Black
REFERENCE_TUESDAY = tz.localize(datetime(2026, 3, 10))

# Manual holiday overrides (add if needed)
# Format: {"YYYY-MM-DD": "YYYY-MM-DD"}  # collection moved FROM Tuesday TO new date
HOLIDAY_OVERRIDES = {
    # Example:
    # "2026-12-29": "2026-12-30"
}

def next_tuesday(today):
    weekday_target = 1  # Tuesday
    days_ahead = (weekday_target - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)

def week_tuesday(d):
    week_start = d - timedelta(days=d.weekday())  # Monday
    return week_start + timedelta(days=1)  # Tuesday

def bin_type_for_week(collection_date):
    tuesday = week_tuesday(collection_date)
    weeks = int((tuesday - REFERENCE_TUESDAY).days / 7)
    return "Black" if weeks % 2 == 0 else "Green/Brown"

def make_event(dt, summary, uid):
    return f"""BEGIN:VEVENT
UID:{uid}
DTSTAMP:{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}
DTSTART;TZID={TIMEZONE}:{dt.strftime("%Y%m%d")}{REMINDER_TIME}
DTEND;TZID={TIMEZONE}:{dt.strftime("%Y%m%d")}{REMINDER_TIME}
SUMMARY:{summary}
END:VEVENT
"""

def generate_calendar():
    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz)

    scheduled_tuesday = next_tuesday(today)
    collection_date = scheduled_tuesday

    holiday_change = False
    holiday_msg = ""

    key = scheduled_tuesday.strftime("%Y-%m-%d")
    if key in HOLIDAY_OVERRIDES:
        new_date = tz.localize(datetime.strptime(HOLIDAY_OVERRIDES[key], "%Y-%m-%d"))
        collection_date = new_date
        holiday_change = True
        holiday_msg = f"Collection moved this week: {new_date.strftime('%A')} instead of Tuesday."

    bin_type = bin_type_for_week(collection_date)
    reminder_day = collection_date - timedelta(days=1)

    cal = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//NM Bin Buddy//EN
X-WR-CALNAME:{CAL_NAME}
CALSCALE:GREGORIAN
"""

    summary = f"Reminder: put out your {bin_type} bin – and give your neighbour a nudge if theirs is still in!"
    cal += make_event(reminder_day, summary, f"nm-reminder-{reminder_day.strftime('%Y%m%d')}")

    if holiday_change:
        cal += make_event(reminder_day, holiday_msg, f"nm-holiday-{reminder_day.strftime('%Y%m%d')}")

    cal += "END:VCALENDAR"
    return cal

if __name__ == "__main__":
    cal = generate_calendar()
    with open("nm_bin_buddy.ics", "w") as f:
        f.write(cal)
