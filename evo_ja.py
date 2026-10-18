#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assetto Corsa EVO 日本語化パッチ（非公式・個人利用向け）

  python evo_ja.py status   # 何も書かない。状態と計画を表示
  python evo_ja.py apply    # 日本語を書き込む（EVO を完全に終了してから）
  python evo_ja.py verify   # 今の状態が日本語化済みか確認（読むだけ）
  python evo_ja.py revert   # バックアップから完全に元へ戻す
  オプション: --pkg <content.kspkg のパス>   --yes（確認なしで実行）

仕組み:
  ・EVO は画面の文言を uiresources\\localization\\<言語>.loc から読みます。言語は en/es/de/fr/it/cn のみで日本語はありません。
  ・日本語（漢字・かな）が出るフォントは「cn」のときにだけ使われるため、cn の枠（簡体中文）に日本語を入れます。
    設定の言語で「日本語」（元は简体中文）を選ぶと日本語になります。
  ・あなた自身のゲームから英語の .loc を読み出し、同梱の ja_translation.json（キー→日本語）を当てはめて作ります。
    Kunos の英語原文はこのパッチに含まれていません。
  ・日本語が元の枠に入らない時は、使わない言語（fr/it/es/de）の隣り合った枠を借ります。借りた範囲の元データは
    必ず backup\\ に退避します。そのため日本語化中は フランス語・イタリア語・スペイン語・ドイツ語 は表示が壊れます（英語は無事）。
  ・ゲームが更新されると content.kspkg が置き換わり、日本語化は消えるか、一部だけ残ります。
    Steam の「ファイルの整合性を確認」→ backup フォルダを削除 → もう一度 apply してください。

パッケージ形式は Nenkai/ACEvo.Package (MIT) の公開されている実装を参考にしています。
"""
import os, sys, re, json, time, struct, hashlib, subprocess

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
TRANS = os.path.join(HERE, 'ja_translation.json')
BACKUP = os.path.join(HERE, 'backup')
MANIFEST = os.path.join(BACKUP, 'manifest.json')

KEY = 0x9F9721A97D1135C1
ENTRY = 0x100
TABLE_SIZES = (0x4000000, 0x2000000)
FLAG_DIR = 1
FLAG_ENC = 0x100
LOC = 'uiresources\\localization\\'
LABEL_FILE = 'uiresources\\js\\components.js'
LABEL_OLD = '"cn": "简体中文"'.encode('utf-8')
_new = '"cn": "日本語"'
LABEL_NEW = (_new + ' ' * (len(LABEL_OLD) - len(_new.encode('utf-8')))).encode('utf-8')
TOKEN = re.compile(r'\{[^}]*\}|<[^>]+>|%[sd]|\\n|v\$')
KANA = re.compile('[\u3040-\u30ff]')

# \u65e5\u672c\u8a9e\u306f\u82f1\u8a9e\u3088\u308a\u6587\u5b57\u5e45\u304c\u5e83\u304f\u3001\u30e1\u30a4\u30f3\u30e1\u30cb\u30e5\u30fc\u4e0a\u6bb5\u306e\u30bf\u30d6\uff08\u30a2\u30ab\u30c7\u30df\u30fc/\u30c9\u30e9\u30a4\u30d0\u30fc/\u30ae\u30e3\u30e9\u30ea\u30fc\uff09\u3067\u672b\u5c3e\u306e\u300c\u30fc\u300d\u304c
# \u6b21\u306e\u884c\u306b\u6298\u308a\u8fd4\u3055\u308c\u3066\u3057\u307e\u3046\u3002\u30bf\u30d6\u306e\u5de6\u53f3\u306e\u4f59\u767d\u3092\u8a70\u3081\u3001\u6298\u308a\u8fd4\u3057\u3092\u7981\u6b62\u3059\u308b CSS \u3092\u672b\u5c3e\u306b\u8db3\u3059\u3002
# \uff08\u3042\u306a\u305f\u306e\u30b2\u30fc\u30e0\u306e CSS \u306e\u5148\u982d\u30a4\u30f3\u30c7\u30f3\u30c8\u3092\u524a\u3063\u3066\u5143\u3088\u308a\u5c0f\u3055\u304f\u3057\u3066\u304b\u3089\u8db3\u3059\u306e\u3067\u3001\u5143\u306e\u67a0\u306b\u305d\u306e\u307e\u307e\u5165\u308b\uff09
CSS_FILE = 'uiresources\\css\\uicomponents.css'
CSS_MARK = b'/* ja-fix */'
CSS_RULE = (b'html[lang="cn"] ks-page-main #panelMenu ks-btnbasic,'
            b'html[lang="cn"] ks-page-academy #panelMenu ks-btnbasic'
            b'{padding-left:.5rem;padding-right:.5rem;overflow-wrap:normal;word-break:keep-all;white-space:nowrap}')


def css_fix(data):
    """\u8fd4\u308a\u5024: \u4fee\u6b63\u5f8c\u306e bytes / None=\u3059\u3067\u306b\u4fee\u6b63\u6e08\u307f / False=\u5143\u306e\u67a0\u306b\u5165\u3089\u306a\u3044"""
    if CSS_MARK in data:
        return None
    nl = b'\r\n' if b'\r\n' in data else b'\n'
    s = re.sub(rb'(?m)^[ \t]+', b'', data)  # \u884c\u982d\u306e\u30a4\u30f3\u30c7\u30f3\u30c8\u3060\u3051\u524a\u308b\uff08\u610f\u5473\u306f\u5909\u308f\u3089\u306a\u3044\uff09
    s = s.rstrip() + nl + CSS_MARK + nl + CSS_RULE + nl
    return s if len(s) <= len(data) else False

# 書き込み先(cn の枠)と、足りない時に借りてよい他言語の同種ファイル
TARGETS = [
    ('cn.loc', ['fr.loc', 'it.loc', 'es.loc', 'de.loc']),
    ('cn.tooltips.loc', ['fr.tooltips.loc', 'es.tooltips.loc', 'de.tooltips.loc', 'it.tooltips.loc']),
    ('cn.cars.loc', ['fr.cars.loc', 'es.cars.loc', 'de.cars.loc', 'it.cars.loc']),
    ('cn.cars.release.loc', ['fr.cars.loc', 'es.cars.loc', 'de.cars.loc', 'it.cars.loc']),
    ('cn_extra strings.loc', []),
]


# ====================== kspkg の読み書き ======================
def xor(data, key=KEY):
    """先頭から 8 バイトずつ key を XOR、端数は key を 8bit ずつ右にずらして XOR"""
    n8 = len(data) // 8
    out = bytearray(len(data))
    if n8:
        kb = key.to_bytes(8, 'little') * n8
        x = int.from_bytes(data[:n8 * 8], 'little') ^ int.from_bytes(kb, 'little')
        out[:n8 * 8] = x.to_bytes(n8 * 8, 'little')
    k = key
    for i in range(n8 * 8, len(data)):
        out[i] = data[i] ^ (k & 0xFF)
        k >>= 8
    return bytes(out)


def path_hash(p):
    h = 0xCBF29CE484222325
    for c in p.lower().replace('/', '\\').encode('utf-16-le'):
        h ^= c
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


class Entry:
    def __init__(self, raw, index):
        self.index = index
        self.raw = raw
        nlen = struct.unpack_from('<h', raw, 0xE6)[0]
        self.name = raw[:nlen].decode('ascii', 'replace')
        self.flags = struct.unpack_from('<H', raw, 0xE4)[0]
        self.hash, self.size, self.offset = struct.unpack_from('<Qqq', raw, 0xE8)

    @property
    def encrypted(self):
        return bool(self.flags & FLAG_ENC)


class Pack:
    def __init__(self, path):
        self.path = path
        self.length = os.path.getsize(path)
        with open(path, 'rb') as f:
            self.table_size = self._detect(f)
            self.table_start = self.length - self.table_size
            f.seek(self.table_start)
            tbl = xor(f.read(self.table_size))
        self.entries = []
        for i in range(self.table_size // ENTRY):
            raw = tbl[i * ENTRY:(i + 1) * ENTRY]
            if struct.unpack_from('<Q', raw, 0xE8)[0] == 0:
                break
            self.entries.append(Entry(raw, i))
        self.by_name = {e.name.lower(): e for e in self.entries}

    def _detect(self, f):
        for ts in TABLE_SIZES:
            if self.length < ts:
                continue
            f.seek(self.length - ts)
            raw = xor(f.read(ENTRY))
            h = struct.unpack_from('<Q', raw, 0xE8)[0]
            nlen = struct.unpack_from('<h', raw, 0xE6)[0]
            name = raw[:nlen]
            if h and 0 < nlen <= 260 and all(32 <= c < 127 for c in name) and h == path_hash(name.decode('ascii')):
                return ts
        raise SystemExit('エラー: これは AC EVO の content.kspkg ではないようです（ファイルテーブルが見つかりません）。')

    def has(self, name):
        return name.lower() in self.by_name

    def get(self, name):
        return self.by_name[name.lower().replace('/', '\\')]

    def read(self, e):
        with open(self.path, 'rb') as f:
            f.seek(e.offset)
            d = f.read(e.size)
        return xor(d) if e.encrypted else d

    def entry_pos(self, e):
        return self.table_start + e.index * ENTRY


# ====================== 翻訳の当てはめ ======================
def h12(s):
    return hashlib.sha1(s.encode('utf-8')).hexdigest()[:12]


def tokens(s):
    return sorted(TOKEN.findall(s))


def kv_split(text):
    lines = text.replace('\r\n', '\n').split('\n')
    idx = []
    for i, ln in enumerate(lines):
        if not ln or ln.lstrip().startswith('#'):
            continue
        k, sep, _ = ln.partition('=')
        if sep and k:
            idx.append(i)
    return lines, idx


def render(en_bytes, table, by_key):
    """英語 .loc に日本語を当てはめる。返り値: (bytes, 未訳の行数, 総行数)"""
    text = en_bytes.decode('utf-8')
    lines, idx = kv_split(text)
    miss = 0
    for i in idx:
        k, _, v = lines[i].partition('=')
        ja = None
        found = False
        if by_key:
            for hh, j in table.get(k, []):
                if hh == h12(v):
                    found, ja = True, j
                    break
        else:
            if h12(v) in table:
                found, ja = True, table[h12(v)]
        if not found:
            miss += 1
        elif ja is not None and tokens(ja) == tokens(v):
            lines[i] = '%s=%s' % (k, ja)
        elif ja is not None:
            miss += 1  # 記号 {0} などが合わない訳は使わない（英語のまま）
    return '\r\n'.join(lines).encode('utf-8'), miss, len(idx)


def build_all(pack, tr):
    """ユーザーのゲームの英語から、cn 枠に入れる日本語ファイル一式を作る"""
    def en(n):
        return pack.read(pack.get(LOC + n))
    built, stats = {}, {}
    ui, m1, n1 = render(en('en.loc'), tr['ui'], True)
    extra = ''.join('\r\n%s=%s' % (k, v) for k, v in tr.get('extra_only', {}).items())
    built['cn.loc'] = ui.rstrip(b'\r\n') + extra.encode('utf-8') + b'\r\n'
    stats['UI'] = (m1, n1)
    tt, m2, n2 = render(en('en.tooltips.loc'), tr['tooltips'], True)
    built['cn.tooltips.loc'] = tt
    stats['ツールチップ'] = (m2, n2)
    cars, m3, n3 = render(en('en.cars.loc'), tr['cars'], False)
    built['cn.cars.loc'] = cars
    stats['車の項目'] = (m3, n3)
    if pack.has(LOC + 'en.cars.release.loc') and en('en.cars.release.loc') != en('en.cars.loc'):
        built['cn.cars.release.loc'], _, _ = render(en('en.cars.release.loc'), tr['cars'], False)
    else:
        built['cn.cars.release.loc'] = cars
    built['cn_extra strings.loc'] = b'# ja\r\n'
    return built, stats


# ====================== 配置の計画 ======================
def plan(pack, built):
    cursors, placed, items = {}, {}, []
    for name, donors in TARGETS:
        if not pack.has(LOC + name):
            continue  # 古い/新しい版で無いファイルは飛ばす
        e = pack.get(LOC + name)
        data = built[name]
        it = {'name': LOC + name, 'entry': e, 'data': data}
        digest = hashlib.sha1(data).hexdigest()
        if digest in placed:
            it.update(mode='share', offset=placed[digest], region=None, shared=True)
        elif len(data) <= e.size:
            it.update(mode='in-place', offset=e.offset, region=(e.offset, e.offset + len(data)))
            placed[digest] = e.offset
        else:
            dents = sorted((pack.get(LOC + d) for d in donors if pack.has(LOC + d)), key=lambda x: x.offset)
            runs, cur = [], []
            for d in dents:
                if cur and cur[-1].offset + cur[-1].size == d.offset:
                    cur.append(d)
                else:
                    if cur:
                        runs.append(cur)
                    cur = [d]
            if cur:
                runs.append(cur)
            ok = False
            for run in runs:
                start, end = run[0].offset, run[-1].offset + run[-1].size
                at = cursors.get(start, start)
                if end - at >= len(data):
                    it.update(mode='borrow', offset=at, region=(at, at + len(data)), donors=[os.path.basename(x.name) for x in run])
                    cursors[start] = at + len(data)
                    placed[digest] = at
                    ok = True
                    break
            if not ok:
                it['mode'] = 'no-room'
        items.append(it)
    # メニューのタブの折り返し対策 CSS
    if pack.has(CSS_FILE):
        e = pack.get(CSS_FILE)
        nd = css_fix(pack.read(e))
        if nd:
            items.append({'name': CSS_FILE, 'entry': e, 'data': nd, 'mode': 'in-place', 'offset': e.offset,
                          'region': (e.offset, e.offset + len(nd))})
        elif nd is False:
            print('  （CSS 修正は元の枠に入らないため見送ります。日本語化自体には影響ありません）')
    # 言語名ラベル
    if pack.has(LABEL_FILE):
        e = pack.get(LABEL_FILE)
        d = pack.read(e)
        if d.count(LABEL_OLD) == 1:
            nd = d.replace(LABEL_OLD, LABEL_NEW)
            items.append({'name': LABEL_FILE, 'entry': e, 'data': nd, 'mode': 'in-place', 'offset': e.offset,
                          'region': (e.offset, e.offset + len(nd)), 'same_size': True})
    return items


def show(items):
    ok = True
    for it in items:
        e = it['entry']
        line = '  %-46s 元の枠=%7d 日本語=%7d  -> %s' % (os.path.basename(it['name']), e.size, len(it['data']), it['mode'])
        if it['mode'] == 'borrow':
            line += ' (借用: %s)' % ', '.join(it['donors'])
        if it['mode'] == 'no-room':
            ok = False
        print(line)
    return ok


# ====================== 補助 ======================
def find_pkg():
    cands = []
    try:
        import winreg
        for hive, sub, val in ((winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath'),
                               (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam', 'InstallPath')):
            try:
                k = winreg.OpenKey(hive, sub)
                v, _ = winreg.QueryValueEx(k, val)
                cands.append(v)
            except OSError:
                pass
    except ImportError:
        pass
    cands += [r'C:\Program Files (x86)\Steam', r'C:\Program Files\Steam']
    libs = []
    for c in cands:
        if c and c not in libs:
            libs.append(c)
        vdf = os.path.join(c, 'steamapps', 'libraryfolders.vdf')
        if os.path.exists(vdf):
            try:
                txt = open(vdf, encoding='utf-8', errors='replace').read()
                for m in re.finditer(r'"path"\s+"([^"]+)"', txt):
                    p = m.group(1).replace('\\\\', '\\')
                    if p not in libs:
                        libs.append(p)
            except OSError:
                pass
    for lib in libs:
        p = os.path.join(lib, 'steamapps', 'common', 'Assetto Corsa EVO', 'content.kspkg')
        if os.path.exists(p):
            return p
    return None


def evo_running():
    try:
        out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq AssettoCorsaEVO.exe'], capture_output=True, text=True).stdout
        return 'AssettoCorsaEVO.exe' in out
    except Exception:
        return False


def table_digest(pkg, pack, skip):
    h = hashlib.sha256()
    with open(pkg, 'rb') as f:
        f.seek(pack.table_start)
        buf = f.read(pack.table_size)
    for i in range(pack.table_size // ENTRY):
        if i not in skip:
            h.update(buf[i * ENTRY:(i + 1) * ENTRY])
    return h.hexdigest()


def load_tr():
    if not os.path.exists(TRANS):
        raise SystemExit('エラー: ja_translation.json が evo_ja.py と同じフォルダにありません。')
    return json.load(open(TRANS, encoding='utf-8'))


def current_state(pack, built):
    """cn 枠の今の中身が、日本語になっているか"""
    same = 0
    total = 0
    for name, _ in TARGETS:
        if not pack.has(LOC + name):
            continue
        total += 1
        if pack.read(pack.get(LOC + name)) == built[name]:
            same += 1
    return same, total


def css_applied(pack):
    """メニュー折り返し対策の CSS が入っているか（CSS が無い版は True 扱い）"""
    if not pack.has(CSS_FILE):
        return True
    return CSS_MARK in pack.read(pack.get(CSS_FILE))


def dirty_donors(pack):
    """借りる側の言語ファイルに日本語（かな）が入っていないか（＝前回の日本語化が残っている）"""
    bad = []
    for name, donors in TARGETS:
        for d in donors:
            if pack.has(LOC + d):
                data = pack.read(pack.get(LOC + d))
                try:
                    if KANA.search(data.decode('utf-8', 'ignore')):
                        bad.append(d)
                except Exception:
                    pass
    return sorted(set(bad))


# ====================== コマンド ======================
def cmd_status(pkg):
    pack = Pack(pkg)
    tr = load_tr()
    built, stats = build_all(pack, tr)
    print('パッケージ: %s' % pkg)
    print('翻訳データ: %s' % tr['meta'].get('translated_for', '?'))
    for k, (miss, n) in stats.items():
        print('  %-8s 未訳 %d / %d 行' % (k, miss, n))
    same, total = current_state(pack, built)
    applied = os.path.exists(MANIFEST)
    print('今の状態: %s' % ('日本語化済み' if same == total else ('一部だけ日本語' if same else '未適用（元のまま）')))
    print('メニュー折り返し対策CSS: %s' % ('適用済み' if css_applied(pack) else '未適用'))
    print('このツールのバックアップ: %s' % ('あり' if applied else 'なし'))
    items = plan(pack, built)
    print('書き込み計画:')
    show(items)
    return 0


def cmd_apply(pkg, yes):
    if evo_running():
        print('中止: AssettoCorsaEVO.exe が起動中です。ゲームを完全に終了してから実行してください。')
        return 2
    pack = Pack(pkg)
    tr = load_tr()
    built, stats = build_all(pack, tr)
    same, total = current_state(pack, built)
    if os.path.exists(MANIFEST):
        if same == total and css_applied(pack):
            print('すでに日本語化済みです（backup\\ あり）。元に戻すなら revert。')
            return 0
        if same == total:
            print('日本語は適用済みですが、メニューの折り返し対策（新しい版の機能）が入っていません。')
            print('  一度 revert（元に戻す）してから、もう一度 apply してください。')
            return 1
        print('中止: backup\\ はあるのに、日本語の状態が一致しません。')
        print('  ゲームが更新された/一部だけ元に戻った可能性があります。')
        print('  Steam でファイルの整合性を確認 → backup フォルダを削除 → もう一度 apply してください。')
        return 1
    bad = dirty_donors(pack)
    if bad:
        print('中止: 他の言語ファイルに日本語が混ざっています（前回の日本語化の残り）:', ', '.join(bad))
        print('  このまま書くと「元のデータ」を正しく退避できません。')
        print('  Steam でファイルの整合性を確認 → もう一度 apply してください。')
        return 1
    print('パッケージ: %s' % pkg)
    miss_total = sum(m for m, _ in stats.values())
    for k, (miss, n) in stats.items():
        print('  %-8s 未訳 %d / %d 行（英語のまま表示）' % (k, miss, n))
    if miss_total > 200:
        print('  ★未訳が多いです。ゲームが翻訳データ(%s)より新しい版かもしれません。それでも英語のまま表示されるだけで動作はします。' % tr['meta'].get('translated_for', '?'))
    items = plan(pack, built)
    print('書き込み計画:')
    if not show(items):
        print('中止: 日本語が入る場所が見つかりません。')
        return 1
    if not yes:
        ans = input('これで書き込みます。EVO の本体ファイルを書き換えます（自己責任・バックアップあり）。よろしいですか？ [y/N] ')
        if ans.strip().lower() != 'y':
            print('中止しました。')
            return 0
    # ---- バックアップ（書く前に全部）----
    os.makedirs(BACKUP, exist_ok=True)
    man = {'pkg': pkg, 'length': pack.length, 'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'ranges': [], 'entries': []}
    blobs = open(os.path.join(BACKUP, 'ranges.bin'), 'wb')
    pos = 0
    touched = set()
    with open(pkg, 'rb') as f:
        for it in items:
            if it.get('region'):
                lo, hi = it['region']
                f.seek(lo)
                b = f.read(hi - lo)
                blobs.write(b)
                man['ranges'].append({'off': lo, 'len': hi - lo, 'blob': pos, 'tag': it['name'], 'sha1': hashlib.sha1(b).hexdigest()})
                pos += hi - lo
            e = it['entry']
            touched.add(e.index)
            f.seek(pack.entry_pos(e))
            man['entries'].append({'index': e.index, 'raw': f.read(ENTRY).hex(), 'name': e.name})
    blobs.flush()
    os.fsync(blobs.fileno())
    blobs.close()
    man['table_digest'] = table_digest(pkg, pack, touched)
    json.dump(man, open(MANIFEST, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('バックアップ完了（%s）' % BACKUP)
    # ---- 書き込み: データ → エントリ ----
    with open(pkg, 'r+b') as f:
        for it in items:
            if it.get('shared'):
                continue
            e = it['entry']
            f.seek(it['offset'])
            f.write(xor(it['data']) if e.encrypted else it['data'])
        f.flush()
        os.fsync(f.fileno())
        for it in items:
            if it.get('same_size'):
                continue
            e = it['entry']
            ent = bytearray(e.raw)
            struct.pack_into('<qq', ent, 0xF0, len(it['data']), it['offset'])
            f.seek(pack.entry_pos(e))
            f.write(xor(bytes(ent)))
        f.flush()
        os.fsync(f.fileno())
    print('書き込み完了。検証します…')
    rc = cmd_verify(pkg)
    if rc == 0:
        print('\n完了です。EVO を起動し、設定の言語で「日本語」を選んでください。')
    return rc


def cmd_verify(pkg):
    pack = Pack(pkg)
    tr = load_tr()
    built, _ = build_all(pack, tr)
    bad = 0
    if os.path.exists(MANIFEST):
        man = json.load(open(MANIFEST, encoding='utf-8'))
        if pack.length != man['length']:
            print('NG: ファイル長が変わっています（ゲーム更新?）。')
            return 1
        touched = {x['index'] for x in man['entries']}
        d = table_digest(pkg, pack, touched)
        print('ファイルテーブル（変更した項目以外）: %s' % ('一致' if d == man['table_digest'] else 'NG 変わっている'))
        bad += d != man['table_digest']
    for name, _ in TARGETS:
        if not pack.has(LOC + name):
            continue
        ok = pack.read(pack.get(LOC + name)) == built[name]
        print('  %-28s %s' % (name, 'OK 日本語' if ok else '日本語ではない'))
        bad += not ok
    if pack.has(LABEL_FILE):
        d = pack.read(pack.get(LABEL_FILE))
        print('  言語名の表示: %s' % ('日本語' if d.count(LABEL_NEW) == 1 else ('简体中文のまま' if d.count(LABEL_OLD) == 1 else '不明')))
    css_ok = css_applied(pack)
    print('  メニュー折り返し対策CSS: %s' % ('適用済み' if css_ok else '未適用（古い版で適用した場合。revert → apply で入ります）'))
    bad += not css_ok
    return 1 if bad else 0


def cmd_revert(pkg, yes):
    if evo_running():
        print('中止: AssettoCorsaEVO.exe が起動中です。ゲームを完全に終了してから実行してください。')
        return 2
    if not os.path.exists(MANIFEST):
        print('このツールのバックアップがありません。戻すものはありません（未適用、または別の方法で戻してください）。')
        print('  Steam の「ファイルの整合性を確認」でも元に戻せます。')
        return 0
    man = json.load(open(MANIFEST, encoding='utf-8'))
    if os.path.getsize(pkg) != man['length']:
        print('中止: ファイルの長さが変わっています（ゲームが更新されました）。バックアップを書き戻すと壊れます。')
        print('  日本語化は既に消えているはずです。Steam でファイルの整合性を確認し、backup フォルダを削除してください。')
        return 1
    if not yes:
        if input('元に戻します。よろしいですか？ [y/N] ').strip().lower() != 'y':
            print('中止しました。')
            return 0
    blob = open(os.path.join(BACKUP, 'ranges.bin'), 'rb').read()
    with open(pkg, 'r+b') as f:
        for r in man['ranges']:
            b = blob[r['blob']:r['blob'] + r['len']]
            if hashlib.sha1(b).hexdigest() != r['sha1']:
                print('中止: バックアップが壊れています。Steam の整合性確認で戻してください。')
                return 1
        for r in man['ranges']:
            f.seek(r['off'])
            f.write(blob[r['blob']:r['blob'] + r['len']])
        ts = os.path.getsize(pkg) - 0x4000000
        for en in man['entries']:
            f.seek(ts + en['index'] * ENTRY)
            f.write(bytes.fromhex(en['raw']))
        f.flush()
        os.fsync(f.fileno())
    dst = os.path.join(HERE, 'backup_reverted_%s' % time.strftime('%Y%m%d_%H%M%S'))
    os.rename(BACKUP, dst)
    print('元に戻しました。（バックアップは %s に移動しました。不要なら削除して構いません）' % os.path.basename(dst))
    return 0


def main():
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help', 'help'):
        print(__doc__)
        return 0
    cmd = args[0]
    yes = '--yes' in args
    pkg = None
    if '--pkg' in args:
        pkg = args[args.index('--pkg') + 1]
    pkg = pkg or find_pkg()
    if not pkg or not os.path.exists(pkg):
        print('Assetto Corsa EVO の content.kspkg が見つかりません。')
        print('  --pkg "D:\\SteamLibrary\\steamapps\\common\\Assetto Corsa EVO\\content.kspkg" のように指定してください。')
        return 1
    if cmd == 'status':
        return cmd_status(pkg)
    if cmd == 'apply':
        return cmd_apply(pkg, yes)
    if cmd == 'verify':
        return cmd_verify(pkg)
    if cmd == 'revert':
        return cmd_revert(pkg, yes)
    print('不明なコマンド: %s（status / apply / verify / revert）' % cmd)
    return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('中断しました。')
        sys.exit(130)
