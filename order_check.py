"""
order_check.py — checks JS and HTML ordering/dependency issues.
Run as part of the build pipeline after gen.py.
"""
import re, sys

with open('/home/claude/mlf-final.html') as f: html = f.read()
js = html[html.index('<script>')+8:html.index('</script>')]

results = []
def ok(name): results.append(('✓', name, ''))
def fail(name, detail): results.append(('✗', name, detail))
def warn(name, detail): results.append(('⚠', name, detail))

# ── 1. HTML STRUCTURE ────────────────────────────────────────────────────
head_pos   = html.find('<head')
body_pos   = html.find('<body')
script_pos = html.find('<script>')
style_pos  = html.find('<style>')

if head_pos < body_pos:   ok('HTML: <head> before <body>')
else: fail('HTML: <head> before <body>', f'head={head_pos}, body={body_pos}')
if style_pos < script_pos: ok('HTML: <style> before <script>')
else: fail('HTML: <style> before <script>', f'style={style_pos}, script={script_pos}')

# ── 2. REQUIRED IDs EXIST IN DOM ────────────────────────────────────────
html_ids = set(re.findall(r'id=["\']([^"\']+)["\']', html))
js_ids   = set(re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)", js))
missing  = js_ids - html_ids
if not missing: ok(f'HTML: all {len(js_ids)} getElementById targets exist in DOM')
else: fail('HTML: getElementById targets missing from DOM', str(sorted(missing)))

# ── 3. EXTERNAL DEPENDENCIES ─────────────────────────────────────────────
fonts = re.findall(r'href=["\']https://fonts\.googleapis[^"\']+["\']', html)
if fonts: warn('External: Google Fonts (requires internet for fonts)', f'{len(fonts)} link(s)')
else: ok('External: no Google Fonts dependency')

ext_scripts = re.findall(r'<script[^>]+src=["\']https?://[^"\']+["\']', html)
if ext_scripts: warn('External: CDN script(s)', str(ext_scripts)[:150])
else: ok('External: no CDN scripts')

# ── 4. TOP-LEVEL CONST/LET USED BEFORE DECLARED ─────────────────────────
# NOTE: function declarations are hoisted by JS engine so they are safe
# to call from anywhere in the script. Only const/let matter here.
# ALSO: variables only used inside function bodies are safe even if the
# variable is declared later — as long as the function isn't *called*
# at parse time. We check only for uses at the TOP LEVEL (not inside
# a function body).

# Find all function body ranges to exclude from "top level" checks
fn_ranges = []
for m in re.finditer(r'\bfunction\s+\w+\s*\([^)]*\)\s*\{', js):
    start = m.end() - 1  # position of opening {
    depth = 0
    for i, ch in enumerate(js[start:], start):
        if ch == '{': depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                fn_ranges.append((start, i))
                break

def in_function(pos):
    return any(s <= pos <= e for s, e in fn_ranges)

# All top-level const/let declarations
top_decls = {}
for m in re.finditer(r'^(?:const|let|var)\s+(\w+)', js, re.MULTILINE):
    if not in_function(m.start()) and m.group(1) not in top_decls:
        top_decls[m.group(1)] = m.start()

ok(f'JS: {len(top_decls)} top-level const/let/var declarations found')

# Check each: any top-level uses before declaration?
order_problems = []
for name, def_pos in top_decls.items():
    pattern = r'\b' + re.escape(name) + r'\b'
    for m in re.finditer(pattern, js):
        use_pos = m.start()
        if use_pos >= def_pos: continue
        if in_function(use_pos): continue  # inside a function body — safe
        # Check it's not part of a comment
        line_start = js.rfind('\n', 0, use_pos) + 1
        line = js[line_start:use_pos+len(name)]
        if '//' in line[:use_pos-line_start]: continue
        ctx = js[max(0,use_pos-60):use_pos+60].replace('\n',' ').strip()
        order_problems.append((name, use_pos, def_pos, ctx))
        break

if not order_problems:
    ok('JS: no top-level const/let used before declaration')
else:
    for name, use_pos, def_pos, ctx in sorted(order_problems, key=lambda x: x[1]):
        fail(f'JS: "{name}" used at top level (pos {use_pos}) before declared (pos {def_pos})',
             ctx[:100])

# ── 5. CRITICAL PAIRS — const/let defined before first use ───────────────
critical = [
    ('const CONFIG',             'CONFIG.'),
    ('const CC=',                'CC['),
    ('const FALLBACK_ELEMENTS',  'FALLBACK_ELEMENTS'),
    ('const FALLBACK_CONNECTIONS','FALLBACK_CONNECTIONS'),
    ('let ELEMENTS',             'ELEMENTS['),
    ('const ELEMENTS_URL',       'ELEMENTS_URL'),
    ('const CONNECTIONS_URL',    'CONNECTIONS_URL'),
]
for defn, usage in critical:
    def_pos = js.find(defn)
    if def_pos == -1:
        warn(f'JS: "{defn}" not found', 'may have been renamed')
        continue
    uses = [m.start() for m in re.finditer(re.escape(usage), js)
            if m.start() != def_pos]
    bad = [p for p in uses if p < def_pos]
    if bad:
        ctx = js[max(0,bad[0]-50):bad[0]+80].replace('\n',' ').strip()
        fail(f'JS: "{usage}" used before "{defn}"', ctx[:100])
    else:
        ok(f'JS: "{defn[:40]}" before all {len(uses)} uses')

# ── 6. CONFIG KEYS — all referenced keys exist ───────────────────────────
config_start = js.find('const CONFIG = {')
config_end   = js.find('\n};', config_start) + 3
config_block = js[config_start:config_end]
config_keys  = re.findall(r'^\s{2}([A-Z_]+)\s*:', config_block, re.MULTILINE)
all_refs     = re.findall(r'CONFIG\.(\w+)', js)
missing_keys = [r for r in set(all_refs) if r not in config_keys]
if not missing_keys: ok(f'JS: all {len(set(all_refs))} CONFIG.X references are valid keys')
else: fail('JS: CONFIG references to undefined keys', str(missing_keys))

# ── 7. SLIDE COUNT CONSISTENCY ───────────────────────────────────────────
slide_divs = len(re.findall(r'class=["\'][^"\']*\bslide\b', html))
sl_array   = re.search(r"const SL=\[([^\]]+)\]", js)
sl_count   = sl_array.group(1).count("'") // 2 if sl_array else 0
if slide_divs == sl_count: ok(f'HTML/JS: slide count consistent ({slide_divs})')
else: fail('HTML/JS: slide count mismatch', f'HTML has {slide_divs}, SL array has {sl_count}')

# ── 8. buildLOI / buildNet scope leaks ───────────────────────────────────
loi_end = js.find('// ════', js.find('function buildLOI'))
net_start = js.find('function buildNet')
# Find just the buildLOI function body (not everything up to buildNet)
loi_fn_start = js.find('function buildLOI')
# Find matching closing brace
depth = 0; loi_fn_end = loi_fn_start
for i, ch in enumerate(js[loi_fn_start:], loi_fn_start):
    if ch == '{': depth += 1
    elif ch == '}':
        depth -= 1
        if depth == 0: loi_fn_end = i; break
loi_section = js[loi_fn_start:loi_fn_end]
# These should NOT appear in buildLOI
banned_in_loi = ['nodeG', 'ringG', 'edgeG', 'netSel', 'netTF']
for b in banned_in_loi:
    if b in loi_section:
        fail(f'JS: "{b}" (buildNet scope) referenced inside buildLOI', '')
    else:
        ok(f'JS: "{b}" not leaked into buildLOI')

# ── PRINT ─────────────────────────────────────────────────────────────────
print('\n══════════════════════════════════════════════════')
print('  ORDER & DEPENDENCY CHECK RESULTS')
print('══════════════════════════════════════════════════')
p=w=f=0
for sym, name, detail in results:
    if sym=='✓': print(f'  ✓  {name}'); p+=1
    elif sym=='⚠': print(f'  ⚠  {name}\n       → {detail}'); w+=1
    else: print(f'  ✗  {name}\n       → {detail}'); f+=1
print('══════════════════════════════════════════════════')
print(f'  {p} passed  |  {w} warnings  |  {f} failed')
print('══════════════════════════════════════════════════')
sys.exit(1 if f > 0 else 0)
