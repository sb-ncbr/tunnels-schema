#!/usr/bin/env python3
"""
ddl2_dict_summary.py  –  DDL‑2/mmCIF dictionary reporter + ER‑diagram generator

Usage examples
--------------
# concise report + DOT on stdout
python ddl2_dict_summary.py  my_dict.dic  --dot -

# full report with wrapped descriptions and DOT to file
python ddl2_dict_summary.py  my_dict.dic  --desc  --dot schema.gv
dot -Tpng schema.gv -o schema.png
"""
import argparse, re, sys
from collections import defaultdict, OrderedDict
import textwrap, gemmi


# ───────────────────────── helpers ─────────────────────────
def clean(s: str) -> str:
    return s.strip().strip('\'"')


def cat_of(tag: str) -> str:
    return tag.split('.', 1)[0].lstrip('_')


def tail_of(tag: str) -> str:
    return tag.split('.', 1)[1] if '.' in tag else tag


def wrap(text: str, width: int = 50):
    """Return list of lines ≤ width chars, no word broken."""
    return textwrap.wrap(text, width=width, break_long_words=False,
                         replace_whitespace=True)


def strip_cif_semicolons(txt: str) -> str:
    """Remove leading/ending CIF semicolon lines and surrounding blanks."""
    txt = txt.strip('\n')
    if txt.startswith(';'):
        txt = txt.lstrip(';\n')
    if txt.endswith(';'):
        txt = txt[:-1]
    return txt.strip()


def num_or_none(x: str):
    return None if x in ('', '.', '?') else float(x)


def format_range(m):
    if 'min' not in m and 'max' not in m:
        return ''
    lo, hi = m.get('min'), m.get('max')
    lbr = '[' if m.get('min_inc') and lo is not None else '('
    rbr = ']' if m.get('max_inc') and hi is not None else ')'
    lo_s = str(lo) if lo is not None else '-inf'
    hi_s = str(hi) if hi is not None else 'inf'
    return f'{lbr}{lo_s}..{hi_s}{rbr}'


def escape_html(s: str) -> str:
    return (s.replace('&', '&amp;')
              .replace('<', '&lt;')
              .replace('>', '&gt;')
              .replace('"', '&quot;'))


def list_save_frames(path):
    with open(path, encoding='utf-8', errors='replace') as fh:
        return re.findall(r'(?m)^\s*save_([^\s;]+)', fh.read())


# ─────────────────── dictionary parser ────────────────────
def parse_dictionary(doc, frame_names):
    root = doc[0]
    frames = [root] + [root.find_frame(n) for n in frame_names]

    cats, items = set(), defaultdict(set)
    cat_meta = defaultdict(dict)   # NEW  ❱  cat → {'desc': …}
    meta = defaultdict(dict)              # item_tag → {...}
    keys = defaultdict(OrderedDict)       # cat → OrderedDict(pk_tag→None)
    fks  = defaultdict(lambda: defaultdict(set))  # cat → gid → {(child,parent)}

    def add_fk(child, parent, gid='—'):
        child, parent, gid = map(clean, (child, parent, gid or '—'))
        if child and parent:
            cats.add(cat_of(child))
            fks[cat_of(child)][gid].add((child, parent))

    for fr in frames:
        if fr is None:
            continue

        # ── category meta (description) ──────────────────────────
        cat_id = fr.find_value('_category.id')
        if cat_id:
            cat_id = clean(cat_id)
            desc_raw = fr.find_value('_category.description')
            if desc_raw:
                cat_meta[cat_id]['desc'] = strip_cif_semicolons(desc_raw)

        # --- items & metadata ---
        for tag in fr.find_values('_item.name'):
            tag = clean(tag)
            if not tag:
                continue
            cat = cat_of(tag)
            cats.add(cat)
            items[cat].add(tag)
            m = meta[tag]

            m.setdefault('type', clean(fr.find_value('_item_type.code') or ''))
            m.setdefault('unit', clean(fr.find_value('_item_units.code') or ''))

            desc_raw = fr.find_value('_item_description.description')
            if desc_raw and not m.get('desc'):
                m['desc'] = strip_cif_semicolons(desc_raw)

            # range rows
            rows = []
            rng_loop = fr.find('_item_range.', ['maximum', 'minimum'])
            if rng_loop:
                for row in rng_loop:
                    rows.append((clean(row[1]), clean(row[0])))
            else:
                mn = clean(fr.find_value('_item_range.minimum') or
                           fr.find_value('_item_range.minimum_value') or '')
                mx = clean(fr.find_value('_item_range.maximum') or
                           fr.find_value('_item_range.maximum_value') or '')
                if mn or mx:
                    rows.append((mn, mx))

            if rows:
                mins, maxs, unb_min, unb_max = [], [], False, False
                for mn, mx in rows:
                    nmn, nmx = num_or_none(mn), num_or_none(mx)
                    if nmn is None: unb_min = True
                    else: mins.append(nmn)
                    if nmx is None: unb_max = True
                    else: maxs.append(nmx)
                m['min'] = None if unb_min else (min(mins) if mins else None)
                m['max'] = None if unb_max else (max(maxs) if maxs else None)
                m['min_inc'] = any(num_or_none(a) is not None and
                                   num_or_none(a) == m['min'] == num_or_none(b)
                                   for a, b in rows) if m['min'] is not None else False
                m['max_inc'] = any(num_or_none(a) is not None and
                                   num_or_none(b) == m['max'] == num_or_none(a)
                                   for a, b in rows) if m['max'] is not None else False

        # --- primary keys ---
        pk_tags = fr.find_values('_category_key.name')
        pk_cids = fr.find_values('_category_key.category_id')
        for i, pk in enumerate(pk_tags):
            pk = clean(pk)
            if not pk: continue
            cat = clean(pk_cids[i]) if i < len(pk_cids) and pk_cids[i] else cat_of(pk)
            cats.add(cat)
            keys[cat][pk] = None

        # --- foreign keys ---
        lk_loop = fr.find('_item_linked.', ['child_name', 'parent_name', '?group_id'])
        if lk_loop:
            gid_col = 2 if lk_loop.has_column(2) else -1
            for row in lk_loop:
                add_fk(row[0], row[1], row[gid_col] if gid_col != -1 else '—')
        child, parent = fr.find_value('_item_linked.child_name'), fr.find_value('_item_linked.parent_name')
        if child and parent:
            add_fk(child, parent, fr.find_value('_item_linked.group_id') or '—')

    return sorted(cats), items, meta, keys, fks, cat_meta


# ───────────────────── Graphviz DOT ─────────────────────
def generate_dot(cats, items, meta, keys, fks, cat_meta,
                 *, layout='dot', show_desc=False):

    fk_children = {c: {ch for prs in g.values() for ch, _ in prs}
                   for c, g in fks.items()}

    lines = [
        'digraph ER {',
        f'  layout = {layout};',
        '  rankdir = TB;',
        '  node [shape=plaintext,fontsize=10,fontname="Helvetica"];'
    ]

    for cat in cats:
        pk_set, fk_set = set(keys[cat]), fk_children.get(cat, set())
        order = list(keys[cat]) + sorted(t for t in items[cat] if t not in pk_set)

        header = f'  <tr><td bgcolor="#cccccc"><b>{escape_html(cat)}</b>'
        if show_desc and cat_meta.get(cat, {}).get('desc'):
            hdr_desc = '<br/><br/><font point-size="8">' + \
                    '<br/>'.join(escape_html(l)
                                    for l in wrap(cat_meta[cat]["desc"], 60)) + \
                    '</font>'
            header += hdr_desc
        header += '</td></tr>'
        rows = [header]

        for tag in order:
            name = escape_html(tail_of(tag))

            # bold / italic for PK / FK
            if tag in pk_set and tag in fk_set:
                name = f'<b><i>{name}</i></b>'
            elif tag in pk_set:
                name = f'<b>{name}</b>'
            elif tag in fk_set:
                name = f'<i>{name}</i>'

            # annotation pieces
            ann = []
            if tag in pk_set: ann.append('PK')
            if tag in fk_set: ann.append('FK')
            m = meta[tag]
            if m.get('type'): ann.append(m['type'])
            if m.get('unit'): ann.append(m['unit'])
            rng = format_range(m)

            # build main cell text
            cell = name
            if ann:
                cell += ' ' + ' '.join(f'[{escape_html(a)}]' for a in ann)
            if rng:
                cell += ' ' + escape_html(rng)

            # append wrapped description in same cell
            if show_desc and m.get('desc'):
                desc_html = '<br/><br/><font point-size="8">' + \
                            '<br/>'.join(escape_html(l) for l in wrap(m['desc'])) + \
                            '</font>'
                cell += desc_html

            rows.append(f'  <tr><td align="left">{cell}</td></tr>')


        label = ('<<table border="1" cellspacing="0" cellpadding="4">\n' +
                 '\n'.join(rows) + '\n</table>>')
        lines.append(f'"{cat}" [label={label}];')

    for ch_cat, gid_map in fks.items():
        for prs in gid_map.values():
            for child, parent in prs:
                lines.append(f'"{ch_cat}" -> "{cat_of(parent)}" '
                             f'[label="{escape_html(tail_of(child))}'
                             f'→{escape_html(tail_of(parent))}",fontsize=8];')
    lines.append('}')
    return '\n'.join(lines)


# ───────────────────── text report ─────────────────────
def print_text_report(cats, items, meta, keys, fks, show_desc=False):
    fk_lookup = {c: {ch for prs in g.values() for ch, _ in prs}
                 for c, g in fks.items()}

    for cat in cats:
        print(f'Category: {cat}')
        order = list(keys[cat]) + sorted(t for t in items[cat] if t not in keys[cat])
        for tag in order:
            prefix = ('*' if tag in keys[cat] else '') + ('~' if tag in fk_lookup.get(cat, set()) else '')
            parts = []
            if tag in keys[cat]: parts.append('PK')
            if tag in fk_lookup.get(cat, set()): parts.append('FK')
            m = meta[tag]
            if m.get('type'): parts.append(m['type'])
            if m.get('unit'): parts.append(m['unit'])
            rng = format_range(m)
            line = f'  - {prefix}{tail_of(tag)}'
            if parts: line += ' ' + ' '.join(f'[{p}]' for p in parts)
            if rng: line += f' {rng}'
            print(line)
            if show_desc and m.get('desc'):
                for l in wrap(m['desc']):
                    print('       ', l)
        print()


# ────────────────────────── main ──────────────────────────
def main():
    pa = argparse.ArgumentParser(description='DDL‑2/mmCIF dictionary summary & ER diagram.')
    pa.add_argument('dictionary', help='path to *.dic / *.cif dictionary')
    pa.add_argument('--dot', metavar='FILE', nargs='?', const='-',
                    help='write DOT to FILE (use "-" for stdout)')
    pa.add_argument('--layout', default='dot',
                    choices=['dot', 'neato', 'fdp', 'sfdp', 'twopi', 'circo'],
                    help='Graphviz layout engine (default: dot)')
    pa.add_argument('--desc', action='store_true',
                    help='add wrapped description rows')
    args = pa.parse_args()

    frames = list_save_frames(args.dictionary)
    if not frames:
        sys.exit('No save_ frames found — not a DDL‑2 dictionary?')
    doc = gemmi.cif.read_file(args.dictionary)
    if not doc:
        sys.exit('Could not read dictionary.')

    cats, items, meta, keys, fks, cat_meta = parse_dictionary(doc, frames)

    print_text_report(cats, items, meta, keys, fks, show_desc=args.desc)

    if args.dot is not None:
        dot = generate_dot(cats, items, meta, keys, fks, cat_meta,
                        layout=args.layout, show_desc=args.desc)

        if args.dot == '-':
            print('----- Graphviz DOT -----')
            print(dot)
        else:
            with open(args.dot, 'w', encoding='utf-8') as fh:
                fh.write(dot)
            print(f'DOT written to {args.dot}')


if __name__ == '__main__':
    main()
