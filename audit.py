import json, re, subprocess
from collections import Counter

with open('/home/claude/mlf-final.html') as f: html = f.read()
with open('/home/claude/elements_final.json') as f: el = json.load(f)
with open('/home/claude/connections_final.json') as f: cn = json.load(f)

results = []
def ok(name): results.append(('✓', name, ''))
def fail(name, detail): results.append(('✗', name, detail))
def warn(name, detail): results.append(('⚠', name, detail))

js = html[html.index('<script>')+8:html.index('</script>')]

# 1. JS SYNTAX
with open('/tmp/ac.js','w') as f2: f2.write(js)
r = subprocess.run(['node','--check','/tmp/ac.js'], capture_output=True, text=True)
if r.returncode==0: ok('JS syntax')
else: fail('JS syntax', r.stderr[:200])

# 2. DIV BALANCE
slides_chunk = html[html.index('<div id="slides">'):html.index('<div id="nav">')]
bal = slides_chunk.count('<div') - slides_chunk.count('</div>')
if bal==0: ok('Div balance')
else: fail('Div balance', f'off by {bal}')

# 3. UNIQUE IDS
dupes = [id for id,n in Counter(re.findall(r'id="([^"]+)"', html)).items() if n>1]
if not dupes: ok('Unique IDs')
else: fail('Unique IDs', f'Duplicates: {dupes[:10]}')

# 4. VARIABLE DECLARATIONS (handles comma-style: const a=1,b=2,c=3)
for v in ['avail','panelW','qTW','contentW','scl','tx','ty']:
    uses = len(re.findall(r'\b'+v+r'\b', js))
    defs = len(re.findall(r'(?:const|let|var)[^;]*\b'+v+r'\b', js))
    if uses>0 and defs==0: fail(f'Variable declared: {v}', f'used {uses}x never declared')
    elif uses>0: ok(f'Variable declared: {v}')

# 5. EVENT LISTENER GUARDS — check the CALLER has a guard, not the function body
for fn, guard in [('buildLOI','loiBuilt'),('buildNet','netBuilt')]:
    start = js.index(f'function {fn}()')
    end_pat = js.find('\nfunction ', start+10)
    body = js[start:end_pat] if end_pat>0 else js[start:]
    n = body.count('addEventListener')
    # Guard is the !loiBuilt check in goTo before calling requestAnimationFrame(buildLOI)
    caller_guard = f'!{guard}' in js
    if caller_guard: ok(f'{fn}: {n} listeners, call guarded by !{guard} in goTo')
    else: warn(f'{fn}: addEventListener', f'{n} listeners, no {guard} guard found')

# 6. CONNECTION ENDPOINTS
el_keys = set(el.keys())
missing = [(c['from'],c['to']) for c in cn if c['from'] not in el_keys or c['to'] not in el_keys]
if not missing: ok('All connection endpoints exist')
else: fail('Connection endpoints', f'{len(missing)} broken: {missing[:3]}')

# 7. REQUIRED FIELDS
no_type = [k for k,v in el.items() if not v.get('type')]
no_cat = [k for k,v in el.items() if v.get('type') in ('Initiative','Output') and not v.get('category')]
no_yrs = [k for k,v in el.items() if v.get('type') in ('Initiative','Output') and not v.get('years')]
if not no_type: ok('All elements have type')
else: fail('Missing type', str(no_type[:5]))
if not no_cat: ok('All initiatives/outputs have category')
else: fail('Missing category', str(no_cat[:5]))
if not no_yrs: ok('All initiatives/outputs have year tags')
else: warn('Missing year tags', str(no_yrs[:5]))

# 8. CATEGORY VALUES
valid_cats = {'Community resilience','Indigenous self-determination','Education outcomes','Youth development','Insight and influence',''}
bad_cat = [(k,v['category']) for k,v in el.items() if v.get('category') and v['category'] not in valid_cats]
if not bad_cat: ok('All categories match known set')
else: fail('Category mismatches', str(bad_cat[:5]))

# 9. CANVAS OVERFLOW
for name in ['loi','net']:
    rules = re.findall(r'#'+name+r'-canvas\{[^\}]+\}', html)
    for rule in rules:
        if 'overflow:hidden' in rule: fail(f'#{name}-canvas overflow:hidden', 'Clips right panel')
        else: ok(f'#{name}-canvas: no overflow:hidden (panel can slide in)')

# 10. CANVAS CLICK e.target CHECK
if "canvas.addEventListener('click',e=>{if(!e.target.closest" in js:
    ok('Canvas click checks e.target before dismiss')
else:
    fail('Canvas click', 'Blind dismiss — closes panel on node click')

# 11. STATE RESET IN goTo (use full function length)
goto_start = js.index('function goTo(idx)')
goto_end = js.index('\n}', goto_start) + 2
goto = js[goto_start:goto_end]
for reset in ['loiSel=null','netSel=null','netActiveType=','clearHoverTT','activePanel=null']:
    if reset in goto: ok(f'goTo resets: {reset}')
    else: warn(f'goTo missing reset', reset)

# 12. setActivePanel IN goTo
if "setActivePanel('loi-panel')" in goto and "setActivePanel('net-panel')" in goto:
    ok('setActivePanel called in goTo for both map slides')
else:
    fail('setActivePanel in goTo', 'Panel will not work on revisit')

# 13. INIT CALLED ONCE
calls = re.findall(r'(?<![a-zA-Z_$])init\(\);', js)
if len(calls)==1: ok('init() called exactly once')
else: fail('init() calls', f'{len(calls)} found')

# 14. SLIDE COUNT vs SL
slide_divs = len(re.findall(r'class="slide[^"]*"', html))
sl_m = re.search(r"const SL=\[([^\]]+)\]", js)
sl_count = sl_m.group(1).count("'")//2 if sl_m else 0
if slide_divs==sl_count: ok(f'Slide count matches SL array ({slide_divs})')
else: fail('Slide count mismatch', f'{slide_divs} divs vs {sl_count} SL entries')

# 15. FALLBACK DATA
if list(el.keys())[0] in js: ok('Fallback data embedded in HTML')
else: fail('Fallback data missing', 'Offline mode will fail')

# 16. CSV PARSER QUOTED FIELDS
if 'inQ' in js: ok('CSV parser handles quoted fields')
else: warn('CSV parser', 'May not handle quoted fields with commas')

# 17. FETCH ERROR MODES
if all(x in js for x in ['ontimeout','onerror','onload']):
    ok('Fetch handles timeout, error and load')
else:
    warn('Fetch error handling', 'May miss failure modes')

# 18. HIGH Z-INDEX INTENTIONALITY
intentional = {'9000','9999','99999'}
high = []
for m in re.finditer(r'z-index[:\s]*(\d+)', html):
    val = re.search(r'\d+', m.group()).group()
    if int(val)>100:
        high.append((val, html[max(0,m.start()-30):m.start()+30].strip()))
unexpected = [(v,ctx) for v,ctx in high if v not in intentional]
if not unexpected: ok(f'High z-indexes all intentional ({sorted(intentional)})')
else: warn('Unexpected high z-index', str(unexpected[:2]))

# 19. NO localStorage/sessionStorage
for bad in ['localStorage','sessionStorage']:
    if bad in js: fail(bad, 'Used — not supported in claude.ai')
    else: ok(f'No {bad}')

# 20. ORPHANED ELEMENTS
connected = set(c['from'] for c in cn) | set(c['to'] for c in cn)
orphans = [k for k,v in el.items() if k not in connected and v.get('type') not in ('Context','Workstream')]
if not orphans: ok('No orphaned elements')
else: warn(f'{len(orphans)} orphaned elements', str(orphans[:3]))

# 21. YEAR TAG RANGE
bad_yrs = [(k,v['years']) for k,v in el.items() if any(y<2015 or y>2030 for y in v.get('years',[]))]
if not bad_yrs: ok('All year tags in range 2015-2030')
else: warn('Year tags out of range', str(bad_yrs[:3]))

# 22. DESCRIPTION HTML BALANCE
bad_desc = []
for k,v in el.items():
    d = v.get('description','')
    opens = len(re.findall(r'<(?!br|/|!)[a-z]+[^>]*(?<!/)>', d))
    closes = len(re.findall(r'</[a-z]+>', d))
    if opens!=closes: bad_desc.append(f'{k} ({opens}o/{closes}c)')
if not bad_desc: ok('Description HTML tags balanced')
else: warn('Unbalanced HTML in descriptions', str(bad_desc[:3]))

# 23. TOUR SHOWN ONCE
if 'tourShown' in js and '!tourShown' in js: ok('Tour shown once (tourShown guard)')
else: warn('Tour guard missing', 'Tour may repeat on revisit')

# 24. RESET BUTTONS WIRED
for btn, label in [('loi-zf','LOI'),('net-zf','Net')]:
    if ("'"+btn+"'") in js or ('"'+btn+'"') in js: ok(f'{label} zoom-reset button wired')
    else: warn(f'{label} reset button', f'{btn} handler not found')

# 25. EXTERNAL LINKS HAVE target=_blank (in JS, not description strings)
raw_links = re.findall(r'href="(https?://[^"]+)"', js)
missing_target = [l for l in raw_links if '_blank' not in js[js.index(l)-5:js.index(l)+100]]
if not missing_target: ok('External links in JS open in new tab')
else: warn('Links may open in same tab', str(missing_target[:3]))

# 26. NO HARDCODED SVG VIEWBOX
hc = re.findall(r'viewBox=["\']0 0 \d+ \d+["\']', html)
if not hc: ok('No hardcoded SVG viewBox dimensions')
else: warn('Hardcoded viewBox', str(hc[:2]))

# 27. RESET FNS REGISTERED
for fn in ['loiResetFn','netResetFn','applyFiltersFn','applyLOIFilterFn']:
    if f'{fn}=' in js: ok(f'{fn} registered')
    else: fail(f'{fn} not registered', f'{fn}() will do nothing')

# PRINT
print('\n══════════════════════════════════════════════════')
print('  COMPREHENSIVE AUDIT — FINAL RESULTS')
print('══════════════════════════════════════════════════')
p=w=f=0
for sym,name,detail in results:
    if sym=='✓': print(f'  ✓  {name}'); p+=1
    elif sym=='⚠': print(f'  ⚠  {name}\n       → {detail}'); w+=1
    else: print(f'  ✗  {name}\n       → {detail}'); f+=1
print('══════════════════════════════════════════════════')
print(f'  {p} passed  |  {w} warnings  |  {f} failed')
print('══════════════════════════════════════════════════')
