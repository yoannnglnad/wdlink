import json, time, urllib.parse, urllib.request
UA = "codata-prep/0.1 (yoann@qomment.io)"
API = "https://www.wikidata.org/w/api.php"
REST = "https://www.wikidata.org/w/rest.php/wikibase/v1"
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)
def wbsearch(q, k=50):
    u = API + "?" + urllib.parse.urlencode(dict(action="wbsearchentities", search=q, language="en", uselang="en", type="item", limit=k, format="json"))
    return [r["id"] for r in get(u).get("search", [])]
def cirrus(q, k=50):
    u = API + "?" + urllib.parse.urlencode(dict(action="query", list="search", srsearch=q, srnamespace=0, srlimit=k, format="json"))
    return [r["title"] for r in get(u)["query"]["search"]]
def rest_search(q, k=50):
    u = REST + "/search/items?" + urllib.parse.urlencode(dict(q=q, language="en", limit=k))
    return [r["id"] for r in get(u)["results"]]
def rest_suggest(q, k=50):
    u = REST + "/suggest/items?" + urllib.parse.urlencode(dict(q=q, language="en", limit=k))
    return [r["id"] for r in get(u)["results"]]
gold = [
 ("Jaguar", "Q35694"),        # animal
 ("Jaguar", "Q26742231"),     # Jaguar Cars? placeholder check below
 ("Mercury", "Q308"),         # planet
 ("Mercury", "Q925"),         # element
 ("Java", "Q251"),            # programming language
 ("Java", "Q3757"),           # island
 ("Michael Jordan", "Q41421"),   # basketball
 ("Michael Jordan", "Q3308285"), # ML professor
 ("Big Apple", "Q60"),
 ("NYC", "Q60"),
 ("Einstein", "Q937"),
 ("Washington", "Q61"),       # DC
 ("Washington", "Q23"),       # George Washington
 ("Washington", "Q1223"),     # state
 ("Paris", "Q167646"),        # Paris of Troy
 ("Douglas Adams", "Q42"),
 ("Kennedy", "Q9696"),        # JFK
 ("Amazon", "Q3884"),         # company
 ("Amazon", "Q3783"),         # river
 ("Python", "Q28865"),        # language
]
rows = []
for m, q in gold:
    res = {}
    for name, fn in [("wbsearchentities", wbsearch), ("rest_suggest", rest_suggest), ("rest_search", rest_search), ("cirrus_list_search", cirrus)]:
        try:
            ids = fn(m)
            res[name] = (ids.index(q) + 1) if q in ids else None
        except Exception as e:
            res[name] = "ERR " + str(e)[:40]
        time.sleep(0.15)
    rows.append((m, q, res))
    print(m, q, res, flush=True)
names = ["wbsearchentities", "rest_suggest", "rest_search", "cirrus_list_search"]
for k in (1, 5, 10, 50):
    print(f"recall@{k}", {n: sum(1 for _,_,r in rows if isinstance(r[n], int) and r[n] <= k) for n in names}, "/", len(rows))
