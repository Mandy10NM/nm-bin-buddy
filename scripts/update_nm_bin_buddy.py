import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz

POSTCODE = "GU2 4LL"
TIMEZONE = "Europe/London"
REMINDER_TIME = "T163000"  # 4:30pm
CAL_NAME = "NM Bin Buddy"

REFERENCE_TUESDAY = datetime(2026, 3, 10)  # Tue 10 March = Black

COUNCIL_URL = "https://my.guildford.gov.uk/customers/s/view-bin-collections"


def fetch_council_page():
    s = requests.Session()
    r = s.get(COUNCIL_URL)

    # If postcode form is present, attempt to submit
    if POSTCODE.replace(" ", "") in r.text:
        return r.text

    # Try a POST in case it expects form submission
    payload = {"postcode": POSTCODE}
    r = s.post(COUNCIL_URL, data=payload)
    return r.text


def parse_next_collection_date(html):
    # Look for date patterns like "Tuesday 17 March 2026" or "17/03/2026"
    date_patterns = [
        r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+\d{1,2}\s+[A-Za-z]+\s+\d{4}',
        r'\d{1,2}/\d{1,2}/\d{4}'
    ]
    dates = []

    for pat in date_patterns:
        for m in re.findall(pat, html):
            try:
                d = datetime.strptime(m, "%d/%m/%Y")
                dates.append(d)
            except:
                try:
                    d = datetime.strptime(m, "%A %d %B %Y")
                    dates.append(d)
                except:
                    pass

    # Return the earliest future date if found
    today = datetime.now()
    future = [d for d in dates if d.date() >= today.date()]
    if future:
        return sorted(future)[0]
    return None


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

    html = fetch_council_page()
    next_date = parse_next_collection_date(html)

    # Default: next Tuesday
    scheduled_tuesday = next_tuesday(today)
    collection_date = scheduled_tuesday

    holiday_change = False
    holiday_msg = ""

    if next_date:
        # If council gives a different day for next collection, use it
        if next_date.date() != scheduled_tuesday.date():
            collection_date = next_date
            holiday_change = True
            holiday_msg = f"Collection moved this week: {next_date.strftime('%A')} instead of Tuesday."

    bin_type = bin_type_for_week(collection_date)
    reminder_day = collection_date - timedelta(days=1)

    cal = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//NM Bin Buddy//EN
X-WR-CALNAME:{CAL_NAME}
CALSCALE:GREGORIAN
"""

    # Main reminder
    summary = f"Reminder: put out your {bin_type} bin – and give your neighbour a nudge if theirs is still in!"
    cal += make_event(reminder_day, summary, f"nm-reminder-{reminder_day.strftime('%Y%m%d')}")

    # Holiday change alert
    if holiday_change:
        cal += make_event(reminder_day, holiday_msg, f"nm-holiday-{reminder_day.strftime('%Y%m%d')}")

    cal += "END:VCALENDAR"
    return cal


if __name__ == "__main__":
    cal = generate_calendar()
    with open("nm_bin_buddy.ics", "w") as f:
        f.write(cal)
