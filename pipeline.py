"""Refresh a small set of real World Bank indicators and screen correlations."""
import datetime
import json
import pathlib
import urllib.request
import duckdb

OUT = pathlib.Path("data")
OUT.mkdir(exist_ok=True)
INDICATORS = {
    "NY.GDP.PCAP.CD": "GDP per capita (current US$)",
    "SP.DYN.LE00.IN": "Life expectancy at birth (years)",
    "SP.DYN.TFRT.IN": "Fertility rate (births per woman)",
    "SP.URB.TOTL.IN.ZS": "Urban population (% of total)",
    "SL.UEM.TOTL.ZS": "Unemployment (% of labor force)",
    "SP.POP.GROW": "Population growth (annual %)",
}
COUNTRIES = {"USA": "United States", "CAN": "Canada", "GBR": "United Kingdom", "JPN": "Japan", "DEU": "Germany", "BRA": "Brazil"}
rows = []
for country in COUNTRIES:
    for indicator in INDICATORS:
        url = f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}?format=json&per_page=100"
        req = urllib.request.Request(url, headers={"User-Agent": "DeepSignal/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                payload = json.load(response)
            for point in payload[1] or []:
                if point.get("value") is not None and str(point.get("date", "")).isdigit():
                    rows.append((country, indicator, int(point["date"]), float(point["value"])))
        except Exception as exc:
            print(f"Could not fetch {country}/{indicator}: {exc}")
if not rows:
    raise RuntimeError("No data downloaded; refusing to publish empty results")

con = duckdb.connect(":memory:")
con.execute("CREATE TABLE observations(country VARCHAR, indicator VARCHAR, year INTEGER, value DOUBLE)")
con.executemany("INSERT INTO observations VALUES (?, ?, ?, ?)", rows)
con.execute("COPY observations TO 'data/observations.parquet' (FORMAT PARQUET)")
pairs = con.execute("""
SELECT a.country, a.indicator AS a, b.indicator AS b,
       count(*) AS n, corr(a.value, b.value) AS r
FROM observations a JOIN observations b
  ON a.country=b.country AND a.year=b.year AND a.indicator<b.indicator
WHERE a.year>=1990
GROUP BY 1,2,3
HAVING count(*)>=12 AND abs(corr(a.value,b.value))>=0.8
ORDER BY abs(corr(a.value,b.value)) DESC
LIMIT 30
""").fetchall()
discoveries = [
    {"country": COUNTRIES[c], "a": a, "b": b, "a_name": INDICATORS[a], "b_name": INDICATORS[b], "n": n, "r": round(r, 4)}
    for c, a, b, n, r in pairs if r is not None
]
data = {
    "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    "source": "World Bank API",
    "indicators": [{"code": k, "name": v} for k, v in INDICATORS.items()],
    "countries": [{"code": k, "name": v} for k, v in COUNTRIES.items()],
    "rows": [{"country": c, "indicator": i, "year": y, "value": v} for c, i, y, v in rows],
    "discoveries": discoveries,
}
(OUT / "latest.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
print(f"Published {len(rows)} observations and {len(discoveries)} exploratory correlations")
