import re
from datetime import datetime, timedelta
import pytz
from playwright.sync_api import sync_playwright

TIMEZONE = "Europe/London"
REMINDER_TIME = "T183000"
CAL_NAME = "NM Bin Buddy"

tz = pytz.timezone(TIMEZONE)
REFERENCE_TUESDAY = tz.localize(datetime(2026, 3, 10))  # Tue 10 March 2026 = Black

COUNCIL_URL = "https://my.guildford.gov.uk/customers/s/view-bin-collections"

WEEKS_AHEAD = 12  # number of future weeks to include in the calendar
TEST_MODE = False  # test off


def fetch_page_text():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(COUNCIL_URL, wait_until="domcontentloaded")

        # Accept cookies if prompted
        try:
            if page.locator("text=Accept").first.is_visible():
                page.locator("text=Accept").first.click()
        except:
            pass

        # Enter postcode only
        textbox = page.get_by_role("textbox").first
        textbox.click()
        textbox.fill("GU2 4LL")

        # Click "Find address"
        page.get_by_role("button", name="Find address").click()
        page.wait_for_timeout(2000)

        # Select the radio option for your address
        page.locator("text=10 NETHER MOUNT, GUILDFORD, GU2 4LL").click()

        # Click Continue
        page.get_by_role("button", name="Continue").click()

        # Wait for results
        page.wait_for_timeout(3000)

        text = page.inner_text("body")
        browser.close()
        return text


def parse_next_collection_date(text):
    matches = re.findall(r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+\d{1,2}\s+[A-Za-z]+\s+\d{4}", text)
    dates = []
    for m in matches:
        try:
            d = datetime.strptime(m, "%A %d %B %Y")
            dates.append(d)
        except:
            pass
    if not dates:
        return None
    today = datetime.now()
    future = [d for d in dates if d.date() >= today.date()]
    return sorted(future)[0] if future else sorted(dates)[0]


def next_tuesday(today):
    weekday_target = 1
    days_ahead = (weekday_target - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


def week_tuesday(d):
    week_start = d - timedelta(days=d.weekday())
    return week_start + timedelta(days=1)


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
    today = datetime.now(tz)

    text = fetch_page_text()
    next_date = parse_next_collection_date(text)

    scheduled_tuesday = next_tuesday(today)
    holiday_change = False
    holiday_msg = ""
    holiday_week_date = None

    # TEST MODE: force a one‑week shift to Wednesday
    if TEST_MODE:
        holiday_change = True
        holiday_week_date = scheduled_tuesday + timedelta(days=1)
        holiday_msg = "Collection moved this week: Wednesday instead of Tuesday."

    # If the council shows a different day for the next collection
    if next_date and next_date.date() != scheduled_tuesday.date():
        holiday_change = True
        holiday_week_date = tz.localize(next_date)
        holiday_msg = f"Collection moved this week: {holiday_week_date.strftime('%A')} instead of Tuesday."

    # Monday reminder day (day before normal Tuesday)
    holiday_notice_day = scheduled_tuesday - timedelta(days=1)

    # Build rolling reminders for the next N weeks
    cal = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//NM Bin Buddy//EN
X-WR-CALNAME:{CAL_NAME}
CALSCALE:GREGORIAN
"""

    for i in range(WEEKS_AHEAD):
        collection_date = scheduled_tuesday + timedelta(days=7 * i)

        # If the holiday shift is this week, use the shifted date
        if holiday_change and holiday_week_date and week_tuesday(collection_date).date() == week_tuesday(holiday_week_date).date():
            collection_date = holiday_week_date

        bin_type = bin_type_for_week(collection_date)
        reminder_day = collection_date - timedelta(days=1)

        summary = f"Reminder: put out your {bin_type} bin – and give your neighbour a wave if theirs is still in!"
        cal += make_event(reminder_day, summary, f"nm-reminder-{reminder_day.strftime('%Y%m%d')}")

        # Holiday alert should always be Monday 4:30pm
        if holiday_change and holiday_week_date and week_tuesday(collection_date).date() == week_tuesday(holiday_week_date).date():
            cal += make_event(holiday_notice_day, holiday_msg, f"nm-holiday-{holiday_notice_day.strftime('%Y%m%d')}")

    cal += "END:VCALENDAR"
    return cal


if __name__ == "__main__":
    cal = generate_calendar()
    with open("nm_bin_buddy.ics", "w") as f:
        f.write(cal)
