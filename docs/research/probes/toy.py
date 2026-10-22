import csv, math, collections
strip=lambda s:s.rsplit('/',1)[-1]
M={'Curie':['Q16084618','Q229354','Q1082171','Q21429443','Q7186','Q37463'],
   'Paris':['Q90','Q483020','Q830149','Q162121','Q3181341'],
   'Nobel Prize':['Q7191','Q37922','Q80061','Q38104','Q44585'],
   'radioactivity':['Q11448','Q317949','Q1081068'],
   'Warsaw':['Q270','Q144488','Q992560','Q1718656'],
   'Sorbonne':['Q209842','Q214654','Q41497113','Q2845896','Q571293']}
m_of={c:m for m,cs in M.items() for c in cs}
BL={'P1889','P460','P31','P279'}  # negative / type edges excluded from coherence
d1=collections.defaultdict(float)
for r in csv.DictReader(open('r1.csv')):
    a,p,b=strip(r['a']),strip(r['p']),strip(r['b'])
    if p in BL or m_of.get(a)==m_of.get(b): continue
    d1[frozenset((a,b))]=1.0
paths=[{k:strip(v) for k,v in r.items()} for r in csv.DictReader(open('r2.csv'))]
deg=collections.defaultdict(set)
for r in paths: deg[r['x']].update([r['a'],r['b']])
print('hub degrees:',sorted(((len(v),k) for k,v in deg.items()),reverse=True)[:6])
d2=collections.defaultdict(float)
for r in paths:
    a,b,x=r['a'],r['b'],r['x']
    if m_of.get(a)==m_of.get(b) or x in (a,b): continue
    d2[frozenset((a,b))]+=1/math.log(1+len(deg[x]))   # Adamic-Adar on local graph
def w(a,b): return d1[frozenset((a,b))]+0.5*min(1.0,d2[frozenset((a,b))])
for m,cs in M.items():
    sc={c:sum(max(w(c,c2) for c2 in M[m2]) for m2 in M if m2!=m)/(len(M)-1) for c in cs}
    print(m, sorted(sc.items(),key=lambda t:-t[1])[:3])
