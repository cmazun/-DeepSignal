import json
import math
import itertools
import datetime
import urllib.request
from pathlib import Path

indicators = {
 "SP.DYN.LE00.IN": "Life expectancy",
 "NY.GDP.PCAP.CD": "GDP per capita",
 "SP.DYN.TFRT.IN": "Fertility rate",
 "SH.XPD.CHEX.GD.ZS": "Health expenditure (% GDP)",
 "SP.URB.TOTL.IN.ZS": "Urban population (%)",
 "SP.POP.TOTL": "Population",
}
countries = {"US":"United States","GB":"United Kingdom","CA":"Canada","DE":"Germany","FR":"France","JP":"Japan","AU":"Australia","BR":"Brazil","IN":"India","CN":"China"}
rows = []
for code in indicators:
    url = "https://api.worldbank.org/v2/country/" + ";".join(countries) + "/indicator/" + code + "?format=json&per_page=20000&date=1990:2025"
    with urllib.request.urlopen(url, timeout=60) as response:
        payload = json.load(response)
    if not isinstance(payload, list) or len(payload)<2 or not isinstance(payload[1],list):
        raise RuntimeError("Invalid World Bank response for " + code)
    for item in payload[1]:
        cc = item.get("country",{}).get("id")
        if cc not in countries or item.get("value") is None:
            continue
        try:
            value = float(item["value"])
            year = int(item["date"])
        except (TypeError,ValueError):
            continue
        if math.isfinite(value):
            rows.append(dict(country=cc,indicator=code,year=year,value=value))
if len(rows)<300:
    raise RuntimeError("Incomplete data: " + str(len(rows)))
lookup={}
for row in rows:
    lookup.setdefault((row["country"],row["indicator"]),{})[row["year"]]=row["value"]
def pearson(a,b):
    n=len(a)
    if n<12: return None
    ma=sum(a)/n; mb=sum(b)/n
    sa=sum((v-ma)**2 for v in a); sb=sum((v-mb)**2 for v in b)
    if not sa or not sb: return None
    return sum((x-ma)*(y-mb) for x,y in zip(a,b))/math.sqrt(sa*sb)
discoveries=[]
for cc in countries:
    for a,b in itertools.combinations(indicators,2):
        aa=lookup.get((cc,a),{}); bb=lookup.get((cc,b),{})
        years=sorted(set(aa)&set(bb))
        av=[aa[y] for y in years]; bv=[bb[y] for y in years]
        r=pearson(av,bv)
        if r is None or abs(r)<0.7: continue
        pairs=[(i-1,i) for i in range(1,len(years)) if years[i]==years[i-1]+1]
        dr=pearson([av[j]-av[i] for i,j in pairs],[bv[j]-bv[i] for i,j in pairs])
        discoveries.append(dict(country=countries[cc],a=a,b=b,a_name=indicators[a],b_name=indicators[b],r=round(r,4),n=len(years),diff_r=round(dr,4) if dr is not None else None,trend_warning=dr is None or abs(dr)<0.4))
discoveries.sort(key=lambda x:abs(x["r"]),reverse=True)
data=dict(updated=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),indicators=[dict(code=k,name=v) for k,v in indicators.items()],countries=[dict(code=k,name=v) for k,v in countries.items()],rows=rows,discoveries=discoveries[:250],sources=[dict(name="World Bank Open Data",status="connected")])
Path("data").mkdir(exist_ok=True)
Path("data/latest.json").write_text(json.dumps(data,allow_nan=False),encoding="utf-8")
print("Observations:",len(rows),"correlations:",len(discoveries))
