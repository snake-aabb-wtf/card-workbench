#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_card —— 角色卡通用构建器（源码→产物，V2 spec）。

方法论：JSON 是编译产物，人是不该直接编辑 JSON 的——弯引号、转义、diff 可读性全完蛋。
源码用 markdown/JSON 混合目录，编译出干净的 V2 卡。

用法：
    python3 build_card.py <卡片源码目录> -o <输出.json>

源码目录结构：
    card.json        # 元数据（必需）：name, creator, tags, character_version,
                     #   creator_notes / alternate_greetings / extensions（均可省）
    description.md   # 必需
    personality.md   # 可省
    scenario.md      # 可省
    first_mes.md     # 可省
    mes_example.md   # 可省
    lorebook.json    # 可省：{"name": "...", "entries": [
                     #   {"keys": [...], "content": "...", "constant": false,
                     #    "enabled": true, "insertion_order": 100, ...透传字段}]}

条目里 keys 支持数组或逗号分隔字符串；除 keys/content 外的字段原样透传
（constant/enabled/insertion_order/extensions 等全部保留）。
"""
import argparse
import json
import sys
from pathlib import Path

MD_FIELDS = ['description', 'personality', 'scenario', 'first_mes', 'mes_example']
REQUIRED_MD = ['description']


def read_md(src: Path, field: str) -> str:
    p = src / f'{field}.md'
    if not p.exists():
        if field in REQUIRED_MD:
            sys.exit(f'[E] 缺少必需源文件: {p}')
        return ''
    return p.read_text(encoding='utf-8').strip()


def normalize_entry(e: dict, idx: int) -> dict:
    e = dict(e)
    keys = e.get('keys')
    if isinstance(keys, str):
        keys = [k.strip() for k in keys.split(',') if k.strip()]
    e['keys'] = keys or []
    e.setdefault('content', '')
    e.setdefault('extensions', {})
    e.setdefault('enabled', True)
    e.setdefault('insertion_order', 100 + idx)
    return e


def build(src: Path) -> dict:
    meta = json.loads((src / 'card.json').read_text(encoding='utf-8'))
    if not meta.get('name'):
        sys.exit('[E] card.json 缺少 name')
    data = {
        'name': meta['name'],
        'first_mes': read_md(src, 'first_mes'),
        'description': read_md(src, 'description'),
        'personality': read_md(src, 'personality'),
        'scenario': read_md(src, 'scenario'),
        'mes_example': read_md(src, 'mes_example'),
        'creator_notes': meta.get('creator_notes', ''),
        'system_prompt': meta.get('system_prompt', ''),
        'post_history_instructions': meta.get('post_history_instructions', ''),
        'tags': meta.get('tags', []),
        'creator': meta.get('creator', ''),
        'character_version': meta.get('character_version', ''),
        'alternate_greetings': meta.get('alternate_greetings', []),
        'extensions': meta.get('extensions', {}),
    }
    lb_path = src / 'lorebook.json'
    if lb_path.exists():
        lb = json.loads(lb_path.read_text(encoding='utf-8'))
        entries = [normalize_entry(e, i) for i, e in enumerate(lb.get('entries', []))]
        data['character_book'] = {'name': lb.get('name', 'Lorebook'), 'entries': entries}
    return {'spec': 'chara_card_v2', 'spec_version': '2.0', 'data': data}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src', help='卡片源码目录')
    ap.add_argument('-o', '--out', required=True, help='输出 V2 JSON 路径')
    args = ap.parse_args()

    card = build(Path(args.src))
    out = Path(args.out)
    out.write_text(json.dumps(card, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    json.load(open(out, encoding='utf-8'))  # 自校验
    n_lb = len(card['data'].get('character_book', {}).get('entries', []))
    print(f'OK: {out} ({out.stat().st_size} bytes, {n_lb} lorebook entries)')


if __name__ == '__main__':
    main()
