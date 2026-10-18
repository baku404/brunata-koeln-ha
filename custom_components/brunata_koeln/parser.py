"""Read structured chart series from HTML without executing JavaScript."""

import json
import math
import re
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlsplit
from zoneinfo import ZoneInfo

from .errors import PortalFormatError
from .models import MediumReadings, MonthlyReading

ORIGIN = "https://online.brunata-koeln.de"
OVERVIEW_PATH = "/legacy/Uvi/Nutzer/Index"
MONTH_PATH = "/legacy/Uvi/Nutzer/MonthCompare"
MEDIA = {"Heizung": "heating", "Kaltwasser": "cold_water", "Warmwasser": "hot_water"}
UNITS = {"kWh": "kWh", "m³": "m³", "m3": "m³"}
BERLIN = ZoneInfo("Europe/Berlin")


class PortalHTML(HTMLParser):
    """Collect only the markup needed for authentication and chart parsing."""

    def __init__(self, source: str):
        super().__init__(convert_charrefs=True)
        self.csrf: str | None = None
        self.is_login = False
        self.captcha = False
        self.captcha_token = ""
        self.links: list[str] = []
        self.charts: list[str] = []
        self._chart: list[str] | None = None
        self.feed(source)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        """Inspect known markup without retaining account details."""
        attributes = dict(attrs)
        if tag == "input":
            if attributes.get("name") == "__RequestVerificationToken":
                self.csrf = attributes.get("value")
            if attributes.get("type") == "password":
                self.is_login = True
        if attributes.get("id") == "authentication":
            self.is_login = True
            self.captcha_token = attributes.get("captchatoken") or ""
            try:
                self.captcha = int(attributes.get("faildattempts") or "0") >= 2
            except ValueError:
                self.captcha = True
        if tag == "a" and attributes.get("href"):
            self.links.append(attributes["href"])
        if tag == "script" and (attributes.get("id") or "").startswith("chart-data-"):
            self._chart = []

    def handle_data(self, data: str):
        """Keep chart text, not arbitrary inline scripts."""
        if self._chart is not None:
            self._chart.append(data)

    def handle_endtag(self, tag: str):
        """Finish chart payload collection."""
        if tag == "script" and self._chart is not None:
            self.charts.append("".join(self._chart))
            self._chart = None


def discover_media(page: PortalHTML) -> dict[str, str]:
    """Discover only same-origin medium links actually advertised by the portal."""
    result = {}
    for link in page.links:
        parsed = urlsplit(urljoin(ORIGIN, link))
        if (
            parsed.scheme != "https"
            or parsed.netloc != urlsplit(ORIGIN).netloc
            or parsed.path != MONTH_PATH
        ):
            continue
        medium = parse_qs(parsed.query).get("mediumType", [""])[0]
        if medium in MEDIA:
            result[medium] = f"{MONTH_PATH}?mediumType={medium}"
    return result


def parse_monthly(
    source: str, medium: str, as_of: date | None = None, *, forecast: bool = False
) -> MediumReadings:
    """Extract actual past-month values; reject ambiguous or malformed series."""
    if medium not in MEDIA:
        raise PortalFormatError("Unsupported medium")
    page = PortalHTML(source)
    if not page.charts:
        raise PortalFormatError("Consumption chart is missing")
    cutoff = (as_of or datetime.now(BERLIN).date()).replace(day=1)
    readings: dict[date, MonthlyReading] = {}
    selected_count = 0
    for chart in page.charts:
        medium_match = re.search(r'"mediumType"\s*:\s*"([^"\\]*)"', chart)
        if medium_match is None or medium_match.group(1) != medium:
            raise PortalFormatError("Consumption medium does not match the request")
        for match in re.finditer(r'"series"\s*:\s*(?=\[)', chart):
            try:
                series, _ = json.JSONDecoder().raw_decode(chart[match.end() :])
            except (ValueError, TypeError):
                raise PortalFormatError("Invalid consumption series") from None
            for item in series:
                if not isinstance(item, dict):
                    raise PortalFormatError("Invalid consumption series")
                if item.get("name") != "Ausgewählter Abrechnungszeitraum":
                    continue
                selected_count += 1
                raw_unit = item.get("valueType")
                unit = UNITS.get(raw_unit) if isinstance(raw_unit, str) else None
                if unit is None:
                    raise PortalFormatError("Unsupported consumption unit")
                points = item.get("data")
                if not isinstance(points, list):
                    raise PortalFormatError("Monthly readings are missing")
                for point in points:
                    if not isinstance(point, dict):
                        raise PortalFormatError("Invalid monthly reading")
                    estimate = point.get("isHochrechnung")
                    if not isinstance(estimate, bool):
                        raise PortalFormatError("Reading estimate flag is missing")
                    if estimate != forecast:
                        continue
                    value, timestamp = point.get("y"), point.get("x")
                    if value is None:
                        continue
                    if (
                        isinstance(value, bool)
                        or not isinstance(value, (float, int))
                        or not math.isfinite(value)
                        or isinstance(timestamp, bool)
                        or not isinstance(timestamp, (float, int))
                        or not math.isfinite(timestamp)
                    ):
                        raise PortalFormatError("Invalid monthly reading")
                    try:
                        day = datetime.fromtimestamp(timestamp / 1000, BERLIN).date()
                    except (ValueError, OverflowError, OSError):
                        raise PortalFormatError("Invalid reading date") from None
                    if day.day != 1:
                        raise PortalFormatError("Reading is not a monthly boundary")
                    if day > cutoff or (day == cutoff and not forecast):
                        continue
                    reading = MonthlyReading(day, float(value), unit)
                    if day in readings and readings[day] != reading:
                        raise PortalFormatError("Conflicting monthly readings")
                    readings[day] = reading
    if selected_count != 1:
        raise PortalFormatError("Selected consumption series is ambiguous or missing")
    return MediumReadings(medium, tuple(readings[key] for key in sorted(readings)))


def parse_property_average(
    source: str, medium: str, as_of: date | None = None, *, forecast: bool = False
):
    """Extract the uniquely identified property average, without personal labels."""
    selected = []
    for chart in PortalHTML(source).charts:
        match = re.search(r'"mediumType"\s*:\s*"([^"\\]*)"', chart)
        if match is None or match.group(1) != medium:
            raise PortalFormatError("Comparison medium does not match the request")
        for marker in re.finditer(r'"series"\s*:\s*(?=\[)', chart):
            try:
                series, _ = json.JSONDecoder().raw_decode(chart[marker.end() :])
            except (ValueError, TypeError):
                raise PortalFormatError("Invalid comparison series") from None
            if not isinstance(series, list) or any(
                not isinstance(x, dict) for x in series
            ):
                raise PortalFormatError("Invalid comparison series")
            selected.extend(
                x for x in series if x.get("name") == "Durchschnitt der Liegenschaft"
            )
    if len(selected) != 1:
        raise PortalFormatError("Property average is ambiguous or missing")
    item = dict(selected[0])
    units = {"kWh je Nutzeinheit": "kWh", "m³ je Nutzeinheit": "m³"}
    if item.get("valueType") not in units:
        raise PortalFormatError("Unsupported property comparison unit")
    item["valueType"] = units[item["valueType"]]
    item["name"] = "Ausgewählter Abrechnungszeitraum"
    synthetic = (
        '<script id="chart-data-comparison">'
        + json.dumps({"mediumType": medium, "series": [item]})
        + "</script>"
    )
    return parse_monthly(synthetic, medium, as_of, forecast=forecast).readings
