"""Entirely synthetic portal markup and HTTP responses."""

import json

JANUARY = 1735686000000
FEBRUARY = 1738364400000


def chart(points=None, unit="kWh", medium="Heizung"):
    """Match the observed chart envelope without copying private data."""
    if points is None:
        points = [
            {"x": JANUARY, "y": 12.5, "isHochrechnung": False},
            {"x": FEBRUARY, "y": 99, "isHochrechnung": True},
        ]
    selected = {
        "name": "Ausgewählter Abrechnungszeitraum",
        "valueType": unit,
        "data": points,
    }
    # Include a JavaScript callback outside the JSON series: never evaluate it.
    return (
        '<script type="text/plain" id="chart-data-chart_0">'
        '{"chart":{"mediumType":'
        + json.dumps(medium)
        + '},"plotOptions":{"series":{"events":{"load":uvi.Callback}}},"series":'
        + json.dumps(
            [{"name": "Vorheriger Abrechnungszeitraum", "data": [{"y": 900}]}, selected]
        )
        + "}</script>"
    )


OVERVIEW = '<a href="/legacy/Uvi/Nutzer/MonthCompare?mediumType=Heizung">Details</a>'
LOGIN = (
    '<div id="authentication" faildAttempts="0"></div>'
    '<input name="__RequestVerificationToken" value="synthetic-csrf">'
)


class FakeContent:
    def __init__(self, body):
        self.body = body.encode()

    async def iter_chunked(self, size):
        yield self.body


class FakeResponse:
    def __init__(self, body="", status=200, headers=None):
        self.status = status
        self.headers = headers or {}
        self.content = FakeContent(body)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
        self.cookie_jar = FakeCookieJar()

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return next(self.responses)


class FakeCookieJar(dict):
    def update_cookies(self, cookies, *, response_url):
        self.response_url = response_url
        self.update(cookies)
