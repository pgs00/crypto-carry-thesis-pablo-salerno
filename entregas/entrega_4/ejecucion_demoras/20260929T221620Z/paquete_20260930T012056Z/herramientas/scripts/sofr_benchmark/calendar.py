"""Official US securities calendar and NY Fed exceptions."""

import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from html.parser import HTMLParser

from scripts.return_capital.common import number, truth

DATE_TEXT = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}"
)


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tag, self.parts, self.rows = None, [], []

    def handle_starttag(self, tag, attrs):
        if self.tag is None and tag in {"h2", "h3", "p", "span"}:
            self.tag, self.parts = tag, []

    def handle_data(self, value):
        if self.tag:
            self.parts.append(value)

    def handle_endtag(self, tag):
        if self.tag == tag:
            self.rows.append((tag, " ".join("".join(self.parts).split())))
            self.tag = None


def parse_sifma(html, source_file, current=False):
    parser = Elements()
    parser.feed(html)
    active, year, holiday, result = False, None, None, []
    for ordinal, (tag, text) in enumerate(parser.rows):
        if tag == "h2":
            if current:
                active = text == "U.S. Holiday Recommendations"
                year = 2026
            else:
                active = text.isdigit() and 2022 <= int(text) <= 2025
                year = int(text) if text.isdigit() else None
            holiday = None
        elif tag == "h3" and active:
            holiday = text
        elif active and holiday and tag in {"span", "p"}:
            match = DATE_TEXT.search(text)
            if not match:
                continue
            if tag == "p" and not text.startswith("Early Close"):
                raise ValueError("Unrecognized calendar date statement")
            day = datetime.strptime(match[0], "%B %d, %Y").date()
            result.append(
                dict(
                    date=str(day),
                    sifma_status="early_close" if tag == "p" else "full_close",
                    holiday=holiday,
                    source_file=source_file,
                    source_year=year,
                    source_element=ordinal,
                    source_text=text,
                )
            )
    if not result:
        raise ValueError("No applicable official US calendar dates")
    return result


def calendar_rows(holidays, exceptions, start, end):
    known = defaultdict(list)
    for row in holidays:
        known[date.fromisoformat(row["date"])].append(row)
    overrides = {date.fromisoformat(r["date"]): r for r in exceptions}
    if len(overrides) != len(exceptions):
        raise ValueError("Duplicate calendar exception")
    rows = []
    day = start
    while day <= end:
        entries = known[day]
        states = {r["sifma_status"] for r in entries}
        if not states <= {"full_close", "early_close"} or len(states) > 1:
            raise ValueError("Conflicting SIFMA calendar statements")
        state = next(iter(states), "ordinary_weekday" if day.weekday() < 5 else "weekend")
        page_state = state
        business = day.weekday() < 5 and state != "full_close"
        reason = " | ".join(sorted({r["holiday"] for r in entries})) or state
        sources = sorted({r["source_file"] for r in entries}) or [
            "sifma_2026.html" if day.year == 2026 else "sifma_archivo.html"
        ]
        if day in overrides:
            event = overrides[day]
            business = truth(event["is_business_day"])
            reason = event["reason"]
            sources.append(event["source_file"])
            if "sifma_status" in event:
                if event["sifma_status"] not in {"early_close", "full_close"}:
                    raise ValueError("Invalid notice-sourced SIFMA status")
                state = event["sifma_status"]
        rows.append(
            dict(
                date=str(day),
                weekday=day.weekday(),
                sifma_status=state,
                calendar_page_status=page_state,
                nyfed_exception=day in overrides,
                is_business_day=business,
                reason=reason,
                source_files=sources,
            )
        )
        day += timedelta(days=1)
    return rows


def validate_coverage(days, rates, indexes):
    expected = {r["date"] for r in days if truth(r["is_business_day"])}
    if len({r["date"] for r in days}) != len(days):
        raise ValueError("Duplicate calendar day")
    mappings = []
    for rows, label, field in ((rates, "SOFR", "percentRate"), (indexes, "SOFRAI", "index")):
        mapping = {}
        for ordinal, row in enumerate(rows):
            day = date.fromisoformat(row["effectiveDate"]).isoformat()
            if row["type"] != label or day in mapping:
                raise ValueError("Duplicate date or wrong source type: " + label)
            value = number(row[field])
            if label == "SOFRAI" and value <= 0:
                raise ValueError("Nonpositive official index")
            mapping[day] = ordinal, row
        missing, unexpected = expected - mapping.keys(), mapping.keys() - expected
        if missing:
            raise ValueError(f"Missing {label} on documented business date: {sorted(missing)}")
        if unexpected:
            raise ValueError(
                f"Unexpected {label} outside documented business dates: {sorted(unexpected)}"
            )
        mappings.append(mapping)
    rate_map, index_map = mappings
    return [
        dict(
            r,
            sofr_present=r["date"] in rate_map,
            index_present=r["date"] in index_map,
            sofr_source_row=rate_map[r["date"]][0] if r["date"] in rate_map else None,
            index_source_row=index_map[r["date"]][0] if r["date"] in index_map else None,
            coverage_status="verified",
        )
        for r in days
    ]
