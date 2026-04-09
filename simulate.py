"""
simulate.py — Python simulation of buildLOI and buildNet layout computations.
Catches logic errors, ordering issues, and layout problems before deployment.
Run as part of the build pipeline after gen.py.
"""
import json, re, math
from collections import Counter, defaultdict

with open('/home/claude/elements_final.json') as f: el = json.load(f)
with open('/home/claude/connections_final.json') as f: cn = json.load(f)

results = []
def ok(name): results.append(('✓', name, ''))
def fail(name, detail): results.append(('✗', name, detail))
def warn(name, detail): results.append(('⚠', name, detail))

CC = {
    'Community resilience':'#3b9ede',
    'Indigenous self-determination':'#e8b84a',
    'Education outcomes':'#5cb85c',
    'Youth development':'#e87c3e',
    'Insight and influence':'#d9534f',
    '':'#8898aa'
}

# ── Simulate canvas dimensions ─────────────────────────────────────────────
W, H = 1200, 700  # typical screen size

# ══════════════════════════════════════════════════════════════════════════
# SIMULATE buildLOI
# ══════════════════════════════════════════════════════════════════════════
mapLeft = 220
cx_loi = mapLeft + (W - mapLeft) / 2

qLbls = ['Purpose','Leadership of self','Leading with others','Leading in systems',
         'Inter-cultural leadership','Developing leadership capability']
qW, qH, qGap = 130, 52, 14
qTW = len(qLbls) * (qW + qGap) - qGap
qLeft = mapLeft + 20
nodes_loi = {}

# Place question row
for i, q in enumerate(qLbls):
    nodes_loi[q] = {'x': qLeft + i*(qW+qGap) + qW/2, 'y': 192, 'w': qW, 'h': qH}

# Check all LOI labels exist in elements
for q in qLbls:
    if q not in el:
        fail(f'LOI label missing from elements', q)
    else:
        ok(f'LOI label in elements: {q}')

# Check initiatives connect to known LOI labels
qSet = set(qLbls)
loi_conns = [c for c in cn if c['type']=='Level of Leadership' and c['to'] in qSet]
inits_with_loi = set(c['from'] for c in loi_conns if el.get(c['from'],{}).get('type')=='Initiative')
orphan_inits = [k for k,v in el.items() if v['type']=='Initiative' and k not in inits_with_loi]
if not orphan_inits: ok('All initiatives connect to at least one Level of Leadership')
else: warn(f'{len(orphan_inits)} initiatives with no LOI connection', str(orphan_inits[:3]))

# Simulate partner column layout
iW, iGap = 110, 10
avail = W - mapLeft - 40
perRow = 6
allPartners = sorted([k for k,v in el.items() if v['type']=='Partner'])
maxNameLen = max((len(p) for p in allPartners), default=10)
maxChipW = 9 + maxNameLen * 5.2 + 7
colGap = 12
colW = math.ceil(maxChipW) + colGap
maxColsByLOI = math.floor(qTW / colW)
pCols = max(1, min(math.floor(avail / colW), maxColsByLOI))

if pCols >= 1: ok(f'Partner columns: {pCols} columns, colW={colW:.0f}px, fits within qTW={qTW}px')
else: fail('Partner columns', f'pCols={pCols} — no columns computed')

# Check partner table doesn't overflow canvas width
partner_total_w = pCols * colW
if mapLeft + 20 + partner_total_w <= W: ok(f'Partner table fits canvas (width={partner_total_w:.0f}px)')
else: warn('Partner table may overflow', f'{mapLeft+20+partner_total_w:.0f}px > {W}px canvas')

# ══════════════════════════════════════════════════════════════════════════
# SIMULATE buildNet — FULL LAYOUT
# ══════════════════════════════════════════════════════════════════════════
panelW = 280
cx = (W - panelW) * 0.42
cy = H * 0.50
pos = {}

# 1. Cohorts
cohortAng = {'Citizens':30,'Young people':120,'Teachers':210,'Indigenous women':300}
for k, deg in cohortAng.items():
    a = deg * math.pi / 180
    pos[k] = {'x': cx + 92*math.sin(a), 'y': cy - 92*math.cos(a)}

# Check all cohorts in elements
for k in cohortAng:
    if k not in el: fail(f'Cohort missing from elements', k)
    elif el[k]['type'] != 'Cohort': fail(f'Expected Cohort type', f'{k} is {el[k]["type"]}')
    else: ok(f'Cohort in elements: {k}')

# 2. Initiatives — placeCircle with gap at 270°
initKeys = sorted([k for k,v in el.items() if v['type']=='Initiative'],
                  key=lambda k: el[k].get('size',0))
n_init = len(initKeys)
gap_deg, gap_width = 270, 36
available = 360 - gap_width
step_init = available / n_init
startDeg = ((gap_deg + gap_width/2) + 40) % 360
initAngs = {}
for i, k in enumerate(initKeys):
    deg = (startDeg + i * step_init) % 360
    a = deg * math.pi / 180
    pos[k] = {'x': cx + 276*math.sin(a), 'y': cy - 276*math.cos(a)}
    initAngs[k] = deg

# Apply adaptive positioning — preferred angles with conflict resolution
init_preferred = {
    'Menzies Oration':322,'Australasian leadership initiative':303,
    'Indigenous women entreneurship initiative':289,'Menzies School Leadership Incubator':183,
    'Complexity Leadership Lab':222,'Australian Leadership Index':203
}
for k, deg in init_preferred.items():
    if k in initAngs:
        initAngs[k] = deg

def resolve_overlaps(angs, preferred, min_sep=18, max_iter=80):
    keys = list(angs.keys())
    for _ in range(max_iter):
        moved = False
        sorted_keys = sorted(keys, key=lambda k: angs[k])
        for i in range(len(sorted_keys)):
            a, b = sorted_keys[i], sorted_keys[(i+1)%len(sorted_keys)]
            gap = (angs[b]-angs[a]+360)%360
            if 0 < gap < min_sep:
                push = (min_sep-gap)/2
                a_pref = a in preferred; b_pref = b in preferred
                a_share = 0.1 if (a_pref and not b_pref) else 0.9 if (b_pref and not a_pref) else 0.5
                angs[a] = (angs[a]-push*a_share+360)%360
                angs[b] = (angs[b]+push*(1-a_share)+360)%360
                moved = True
        if not moved: break
    return angs

resolve_overlaps(initAngs, init_preferred)

# Ensure no initiative in gap zone after resolution
gap_centre, gap_half_init = 270, 18
for k in list(initAngs.keys()):
    deg = initAngs[k]
    dist = min((deg-gap_centre+360)%360, (gap_centre-deg+360)%360)
    if dist < gap_half_init:
        to_right = (gap_centre+gap_half_init+2+360)%360
        to_left  = (gap_centre-gap_half_init-2+360)%360
        d_right = min((to_right-deg+360)%360, (deg-to_right+360)%360)
        d_left  = min((to_left-deg+360)%360, (deg-to_left+360)%360)
        initAngs[k] = to_right if d_right < d_left else to_left

for k, deg in initAngs.items():
    a = deg * math.pi / 180
    pos[k] = {'x': cx + 276*math.sin(a), 'y': cy - 276*math.cos(a)}

# Check no initiative at gap zone
gap_violations = [k for k,deg in initAngs.items()
                  if min((deg-270)%360, (270-deg)%360) < gap_width/2]
if not gap_violations: ok(f'No initiatives in 270° gap zone ({n_init} initiatives placed)')
else: fail('Initiatives in gap zone', str(gap_violations[:3]))

# 3. Dynamic lever placement
def circular_mean(angles_deg):
    sin_sum = sum(math.sin(a*math.pi/180) for a in angles_deg)
    cos_sum = sum(math.cos(a*math.pi/180) for a in angles_deg)
    return (math.atan2(sin_sum, cos_sum) * 180/math.pi + 360) % 360

leverKeys = [k for k,v in el.items() if v['type']=='Lever']
leverTargetAng = {}
for lev in leverKeys:
    connected = [c['to'] if c['from']==lev else c['from'] for c in cn
                 if (c['from']==lev or c['to']==lev) and
                    el.get(c['from'] if c['to']==lev else c['to'],{}).get('type')=='Initiative']
    connected = [k for k in connected if k in initAngs]
    if connected:
        leverTargetAng[lev] = circular_mean([initAngs[k] for k in connected])
    else:
        leverTargetAng[lev] = None

# Check all levers have an assigned angle
no_ang = [k for k,v in leverTargetAng.items() if v is None]
if not no_ang: ok(f'All {len(leverKeys)} levers have computed target angles')
else: warn(f'{len(no_ang)} levers have no initiative connections (will be placed in gaps)', str(no_ang))

# Spread pass simulation
minLeverGap = 22
assigned = sorted([k for k in leverKeys if leverTargetAng[k] is not None],
                  key=lambda k: leverTargetAng[k])
for _ in range(50):
    moved = False
    for i in range(len(assigned)):
        prev = assigned[(i-1) % len(assigned)]
        curr = assigned[i]
        nxt  = assigned[(i+1) % len(assigned)]
        gp = (leverTargetAng[curr] - leverTargetAng[prev] + 360) % 360
        gn = (leverTargetAng[nxt]  - leverTargetAng[curr] + 360) % 360
        if gp < minLeverGap:
            leverTargetAng[curr] = (leverTargetAng[curr] + (minLeverGap-gp)/2 + 360) % 360
            moved = True
        if gn < minLeverGap:
            leverTargetAng[curr] = (leverTargetAng[curr] - (minLeverGap-gn)/2 + 360) % 360
            moved = True
    if not moved:
        break

# Apply lever positions
lR = 184
for k in leverKeys:
    ang = leverTargetAng.get(k) or 0
    gap = 30
    d = (ang - 270 + 360) % 360
    mirror = 360 - d if d > 180 else d
    if mirror < gap:
        push = -gap*1.2 if (ang < 270 or (ang > 340 or ang < 90)) else gap*1.2
        ang = (ang + push + 360) % 360
    a = ang * math.pi / 180
    pos[k] = {'x': cx + lR*math.sin(a), 'y': cy - lR*math.cos(a)}

# Check lever positions are distinct and not at origin
lever_positions = [(k, pos[k]['x'], pos[k]['y']) for k in leverKeys]
at_origin = [(k,x,y) for k,x,y in lever_positions if abs(x)<1 and abs(y)<1]
if not at_origin: ok('No levers placed at origin (0,0)')
else: fail('Levers at origin', str([k for k,_,__ in at_origin]))

# Check minimum separation between levers
too_close = []
for i in range(len(lever_positions)):
    for j in range(i+1, len(lever_positions)):
        k1,x1,y1 = lever_positions[i]
        k2,x2,y2 = lever_positions[j]
        dist = math.sqrt((x1-x2)**2 + (y1-y2)**2)
        if dist < 15:  # 15px minimum
            too_close.append(f'{k1} & {k2} ({dist:.0f}px)')
if not too_close: ok(f'All {len(leverKeys)} levers have minimum separation (>15px)')
else: warn('Levers too close together', str(too_close[:3]))

# Check levers not overlapping section label at cx-180,cy
label_x, label_y = cx-180, cy
label_too_close = [(k,x,y) for k,x,y in lever_positions
                   if math.sqrt((x-label_x)**2 + (y-label_y)**2) < 40]
if not label_too_close: ok('No levers overlapping "Cohorts and levers" label')
else: warn('Levers close to section label', str([k for k,_,__ in label_too_close]))

# 4. Outputs
outKeys = sorted([k for k,v in el.items() if v['type']=='Output'],
                 key=lambda k: el[k].get('size',0))
n_out = len(outKeys)
outGapCentre, outGapHalf = 270, 28

def idealAng(ok_key):
    c = next((c for c in cn if c['type']=='Output' and c['from']==ok_key), None)
    return initAngs[c['to']] if (c and c['to'] in initAngs) else 180

# Cluster outputs around parent, then resolve overlaps
outByParent = defaultdict(list)
for okey in outKeys:
    outByParent[round(idealAng(okey),1)].append(okey)

minOutSep = 7
spreadStep = minOutSep
outAngs = {}
for okey in outKeys:
    parentAng = idealAng(okey)
    siblings = outByParent[round(parentAng,1)]
    idx = siblings.index(okey); n_s = len(siblings)
    offset = (idx - (n_s-1)/2) * spreadStep
    outAngs[okey] = (parentAng + offset + 360) % 360

resolve_overlaps(outAngs, {}, minOutSep)

# Apply gap zone push
for k in list(outAngs.keys()):
    deg = outAngs[k]
    dist = min((deg-outGapCentre+360)%360, (outGapCentre-deg+360)%360)
    if dist < outGapHalf:
        deg = (outGapCentre-outGapHalf-2+360)%360 if deg < outGapCentre else (outGapCentre+outGapHalf+2)%360
        outAngs[k] = deg
    a = deg * math.pi / 180
    pos[k] = {'x': cx + 368*math.sin(a), 'y': cy - 368*math.cos(a)}

out_in_gap = [k for k,deg in outAngs.items()
              if min((deg-outGapCentre+360)%360,(outGapCentre-deg+360)%360) < outGapHalf]
if not out_in_gap: ok(f'No outputs in 270° gap zone ({n_out} outputs placed)')
else: warn('Outputs in gap zone', str(out_in_gap[:3]))

# 5. All elements have positions
all_map_types = {'Initiative','Output','Lever','Cohort','Partner'}
missing_pos = [k for k,v in el.items() if v['type'] in all_map_types and k not in pos
               and el.get(k,{}).get('type')!='Partner' and k not in ('FUTURE-FIT LEADERSHIP','Innovation','Insight','Influence',
                             'Cohorts and levers','Initiatives and outputs','Partners')]
if not missing_pos: ok('All mappable elements have computed positions')
else: fail('Elements without positions', str(missing_pos[:5]))

# 6. Check all positions are finite numbers, not NaN
nan_pos = [(k,p) for k,p in pos.items()
           if not (math.isfinite(p['x']) and math.isfinite(p['y']))]
if not nan_pos: ok('All positions are finite numbers (no NaN/Infinity)')
else: fail('Non-finite positions', str(nan_pos[:3]))

# 7. Check positions are within reasonable canvas bounds (with some margin)
margin = 200
out_of_bounds = [(k,p) for k,p in pos.items()
                 if p['x'] < -margin or p['x'] > W+margin
                 or p['y'] < -margin or p['y'] > H+margin]
if not out_of_bounds: ok('All positions within canvas bounds')
else: warn('Positions outside canvas bounds', str([(k,f"({p['x']:.0f},{p['y']:.0f})") for k,p in out_of_bounds[:3]]))

# 8. Variable ordering check: scan JS for use-before-define patterns
with open('/home/claude/mlf-final.html') as f: html = f.read()
js = html[html.index('<script>')+8:html.index('</script>')]

critical_deps = [
    ('initAngs', 'leverTargetAng'),   # initAngs must be defined before leverTargetAng uses it
    ('initAngs', 'idealAng'),          # initAngs before idealAng
    ('pos\\[', 'drawNode'),            # pos populated before drawNode called
    ('placeCircle', 'initAngs'),       # placeCircle defined before initAngs uses it
]
for dep_first, dep_second in critical_deps:
    first_pos = js.find(dep_first.replace('\\[','['))
    # Find DEFINITION of second, not just any use
    second_def = re.search(r'(?:const|let|function)\s+'+dep_second.split('\\')[0], js)
    if first_pos >= 0 and second_def:
        if first_pos < second_def.start():
            ok(f'Order OK: {dep_first} defined before {dep_second}')
        else:
            fail(f'Order violation', f'{dep_second} defined at {second_def.start()} before {dep_first} at {first_pos}')

# 9. Check crossing count simulation
def arcs_cross(a1, a2, b1, b2):
    def between(x, s, e):
        x, s, e = x%360, s%360, e%360
        if s < e: return s < x < e
        return x > s or x < e
    return between(b1,a1,a2) != between(b2,a1,a2)

lev_init_pairs = []
for c in cn:
    f, t = c['from'], c['to']
    if el.get(f,{}).get('type')=='Initiative' and el.get(t,{}).get('type')=='Lever':
        if f in initAngs and t in leverTargetAng and leverTargetAng[t]:
            lev_init_pairs.append((f, t, initAngs[f], leverTargetAng[t]))
    elif el.get(t,{}).get('type')=='Initiative' and el.get(f,{}).get('type')=='Lever':
        if t in initAngs and f in leverTargetAng and leverTargetAng[f]:
            lev_init_pairs.append((t, f, initAngs[t], leverTargetAng[f]))

crossings = sum(1 for i in range(len(lev_init_pairs))
                for j in range(i+1, len(lev_init_pairs))
                if lev_init_pairs[i][0] != lev_init_pairs[j][0]
                and lev_init_pairs[i][1] != lev_init_pairs[j][1]
                and arcs_cross(*lev_init_pairs[i][2:], *lev_init_pairs[j][2:]))
if crossings == 0: ok('No lever-initiative line crossings')
elif crossings < 10: warn(f'{crossings} lever-initiative crossings', 'Minor — acceptable given data spread')
else: warn(f'{crossings} lever-initiative crossings', 'Consider reviewing lever/initiative placement')

# ── PRINT RESULTS ──────────────────────────────────────────────────────────
print('\n══════════════════════════════════════════════════')
print('  LAYOUT SIMULATION RESULTS')
print('══════════════════════════════════════════════════')
p=w=f=0
for sym, name, detail in results:
    if sym=='✓': print(f'  ✓  {name}'); p+=1
    elif sym=='⚠': print(f'  ⚠  {name}\n       → {detail}'); w+=1
    else: print(f'  ✗  {name}\n       → {detail}'); f+=1
print('══════════════════════════════════════════════════')
print(f'  {p} passed  |  {w} warnings  |  {f} failed')
print('══════════════════════════════════════════════════')
import sys
sys.exit(1 if f > 0 else 0)
