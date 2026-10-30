"""DeepSignal: sourced World Bank data, reproducible correlation screening."""
import datetime
import json
import math
import pathlib
import time
import urllib.request
import duckdb

OUT = pathlib.Path("data")
OUT.mkdir(exist_ok=True)
# World Bank API includes indicators supplied by several international organizations.
INDICATORS = {
 "NY.GDP.PCAP.CD":"GDP per capita (current US$)",
 "NY.GDP.PCAP.KD.ZG":"GDP per capita growth (annual %)",
 "NY.GDP.MKTP.KD.ZG":"GDP growth (annual %)",
 "FP.CPI.TOTL.ZG":"Inflation, consumer prices (annual %)",
 "SL.UEM.TOTL.ZS":"Unemployment (% of labor force)",
 "SI.POV.GINI":"Gini index",
 "SP.DYN.LE00.IN":"Life expectancy at birth (years)",
 "SP.DYN.TFRT.IN":"Fertility rate (births per woman)",
 "SP.DYN.IMRT.IN":"Infant mortality (per 1,000 live births)",
 "SH.DYN.MORT":"Under-five mortality (per 1,000 live births)",
 "SH.XPD.CHEX.GD.ZS":"Current health expenditure (% GDP)",
 "SH.MED.BEDS.ZS":"Hospital beds (per 1,000 people)",
 "SH.STA.SUIC.P5":"Suicide mortality rate (per 100,000)",
 "SP.URB.TOTL.IN.ZS":"Urban population (% of total)",
 "SP.POP.GROW":"Population growth (annual %)",
 "SP.POP.65UP.TO.ZS":"Population ages 65+ (% of total)",
 "SP.DYN.CDRT.IN":"Death rate, crude (per 1,000)",
 "SE.XPD.TOTL.GD.ZS":"Government education expenditure (% GDP)",
 "SE.SEC.ENRR":"Secondary school enrollment (% gross)",
 "SE.TER.ENRR":"Tertiary school enrollment (% gross)",
 "EG.USE.PCAP.KG.OE":"Energy use (kg oil equivalent per capita)",
 "EG.ELC.ACCS.ZS":"Access to electricity (% population)",
 "EG.FEC.RNEW.ZS":"Renewable energy consumption (% total)",
 "EN.ATM.CO2E.PC":"CO2 emissions (metric tons per capita)",
 "EN.ATM.PM25.MC.M3":"PM2.5 air pollution (micrograms/m3)",
 "AG.LND.AGRI.ZS":"Agricultural land (% land area)",
 "AG.CON.FERT.ZS":"Fertilizer consumption (kg per hectare arable land)",
 "IT.NET.USER.ZS":"Internet users (% population)",
 "IT.CEL.SETS.P2":"Mobile cellular subscriptions (per 100 people)",
 "NE.TRD.GNFS.ZS":"Trade (% GDP)",
 "GC.DOD.TOTL.GD.ZS":"Central government debt (% GDP)",
 "NV.IND.TOTL.ZS":"Industry value added (% GDP)",
 "NV.AGR.TOTL.ZS":"Agriculture value added (% GDP)",
 "SH.H2O.BASW.ZS":"Basic drinking water services (% population)",
 "SH.STA.BASS.ZS":"Basic sanitation services (% population)"
}
COUNTRIES={"USA":"United States","CAN":"Canada","GBR":"United Kingdom","JPN":"Japan","DEU":"Germany","BRA":"Brazil","FRA":"France","IND":"India","CHN":"China","AUS":"Australia","MEX":"Mexico","ZAF":"South Africa"}
def fetch(country,indicator):
 url=f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}?format=json&per_page=100"
 for attempt in range(3):
  try:
   req=urllib.request.Request(url,headers={"User-Agent":"DeepSignal/1.4 research"})
   with urllib.request.urlopen(req,timeout=35) as response: data=json.load(response)
   if not isinstance(data,list) or len(data)<2: return []
   return [(country,indicator,int(p["date"]),float(p["value"])) for p in (data[1] or []) if p.get("value") is not None and str(p.get("date","")).isdigit() and math.isfinite(float(p["value"]))]
  except Exception as exc:
   print(f"Retry {attempt+1}: {country}/{indicator}: {exc}")
   time.sleep(attempt+1)
 return []

rows=[]
for country in COUNTRIES:
 for indicator in INDICATORS:
  rows.extend(fetch(country,indicator))
if len(rows)<500:
 raise RuntimeError(f"Only {len(rows)} observations downloaded; refusing to replace published data")
con=duckdb.connect(":memory:")
con.execute("CREATE TABLE observations(country VARCHAR, indicator VARCHAR, year INTEGER, value DOUBLE)")
con.executemany("INSERT INTO observations VALUES (?,?,?,?)",rows)
con.execute("COPY observations TO 'data/observations.parquet' (FORMAT PARQUET)")
# First differences mitigate correlations caused solely by common trends.
# This is still screening, not causal inference.
pairs=con.execute("""
WITH changes AS (
 SELECT country,indicator,year,value,
 value-lag(value) OVER(PARTITION BY country,indicator ORDER BY year) AS change,
 year-lag(year) OVER(PARTITION BY country,indicator ORDER BY year) AS gap
 FROM observations
)
SELECT a.country,a.indicator,b.indicator,count(*) AS n,
 corr(a.value,b.value) AS r,
 corr(CASE WHEN a.gap=1 AND b.gap=1 THEN a.change END,
      CASE WHEN a.gap=1 AND b.gap=1 THEN b.change END) AS diff_r,
 count(CASE WHEN a.gap=1 AND b.gap=1 THEN 1 END) AS diff_n
FROM changes a JOIN changes b
 ON a.country=b.country AND a.year=b.year AND a.indicator<b.indicator
WHERE a.year>=1990
GROUP BY 1,2,3
HAVING count(*)>=15 AND abs(corr(a.value,b.value))>=0.8
ORDER BY abs(corr(a.value,b.value)) DESC
LIMIT 250
""").fetchall()
discoveries=[]
for country,a,b,n,r,dr,dn in pairs:
 if r is None:continue
 discoveries.append({"country":COUNTRIES[country],"a":a,"b":b,"a_name":INDICATORS[a],"b_name":INDICATORS[b],"n":n,"r":round(r,4),"diff_r":round(dr,4) if dr is not None else None,"diff_n":dn,"trend_warning":dr is None or dn<12 or abs(dr)<0.3})
# The 250 strongest pairs are a ranked shortlist, not a statistically validated sample.
# No p-values or FDR claims are made without testing the full hypothesis family.
data={
 "updated":datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
 "source":"World Bank API",
 "sources":[{"name":"World Bank Open Data","url":"https://data.worldbank.org/","status":"connected"},
 {"name":"WHO","url":"https://www.who.int/data","status":"planned"},
 {"name":"CDC","url":"https://data.cdc.gov/","status":"planned"},
 {"name":"USDA","url":"https://www.ers.usda.gov/data-products/","status":"planned"},
 {"name":"EPA","url":"https://www.epa.gov/environmental-topics/data","status":"planned"}],
 "indicators":[{"code":k,"name":v} for k,v in INDICATORS.items() if any(row[1]==k for row in rows)],
 "countries":[{"code":k,"name":v} for k,v in COUNTRIES.items()],
 "rows":[{"country":c,"indicator":i,"year":y,"value":v} for c,i,y,v in rows],
 "discoveries":discoveries,
 "method":"Pearson r across matched country-years; first-difference r for annual changes. No causal or multiple-testing claims.",
 "screened_pairs":"Candidate shortlist; not all pairs pass data sufficiency."
}
(OUT/"latest.json").write_text(json.dumps(data,separators=(",",":")),encoding="utf-8")
print(f"Published {len(rows)} observations, {len(data['indicators'])} indicators and {len(discoveries)} candidate correlations")
