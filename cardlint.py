#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cardlint —— 角色卡静态体检（V2 spec）。

用法：
    python3 cardlint.py <card.json> [more.json ...]

检查项：
  [E] 致命：spec 不是 chara_card_v2 / name 或 description 缺失 / JSON 解析失败
  [W] 警告：personality/scenario/first_mes/mes_example 缺失或过短、
           Lorebook keys 空/重复、constant 条目无内容、
           直引号 " 出现在对白/人设文本（规范要求弯引号 ""）、
           description 超长（>8000 字符，多数前端吃力）
输出：逐条 [E]/[W] + 末尾统计。退出码 0=有警告无错误，1=有错误。
"""
import json
import re
import sys
from pathlib import Path

STRAIGHT_QUOTE = '"'


def check_card(path: Path) -> tuple[list[str], int]:
    issues: list[str] = []
    try:
        card = json.loads(path.read_text(encoding='utf-8'))
    except Exception as e:
        return [f"[E] JSON 解析失败: {e}"], 1

    if card.get('spec') != 'chara_card_v2':
        issues.append(f"[W] spec={card.get('spec')!r}，非 chara_card_v2（兼容性之王是 V2，确认是否刻意）")
    data = card.get('data', card)

    # 必填字段
    for field in ('name', 'description'):
        v = data.get(field)
        if not v or not str(v).strip():
            issues.append(f"[E] 必填字段 {field} 缺失或为空")
    name = data.get('name', '?')

    # 建议字段
    for field, min_len in (('personality', 20), ('scenario', 10),
                           ('first_mes', 50), ('mes_example', 50)):
        v = str(data.get(field) or '')
        if len(v.strip()) < min_len:
            issues.append(f"[W] {field} 缺失或过短（<{min_len} 字符）")

    desc = str(data.get('description') or '')
    if len(desc) > 8000:
        issues.append(f"[W] description {len(desc)} 字符，>8000 多数前端吃力（考虑拆 Lorebook）")

    # 弯引号规范：description/first_mes/mes_example 中不应出现直引号
    for field in ('description', 'first_mes', 'mes_example', 'personality'):
        v = str(data.get(field) or '')
        n = v.count(STRAIGHT_QUOTE)
        if n:
            issues.append(f"[W] {field} 含 {n} 个直引号 \"（规范要求弯引号 “” 弹回）")

    # Lorebook 健康度
    book = data.get('character_book') or {}
    entries = book.get('entries') or []
    if entries:
        seen_keys: dict[str, int] = {}
        n_const = 0
        for i, e in enumerate(entries):
            keys = e.get('keys') or []
            content = str(e.get('content') or '').strip()
            is_const = bool(e.get('constant'))
            if is_const:
                n_const += 1
                if not content:
                    issues.append(f"[E] Lorebook #{i}（constant）content 为空")
            else:
                if not keys:
                    issues.append(f"[E] Lorebook #{i} 非 constant 但 keys 为空（永远不会触发）")
            for k in keys:
                seen_keys[k] = seen_keys.get(k, 0) + 1
        dup = {k: c for k, c in seen_keys.items() if c > 1}
        if dup:
            issues.append(f"[W] Lorebook 重复 keys（触发时会重复注入）: {dup}")
        if n_const == 0:
            issues.append("[W] 无 constant（蓝灯）常驻条目——若卡有全局铁律建议常驻")
        issues.append(f"[i] Lorebook 共 {len(entries)} 条，其中蓝灯常驻 {n_const} 条")

    errors = sum(1 for x in issues if x.startswith('[E]'))
    return issues, errors


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    total_e = total_w = 0
    for arg in sys.argv[1:]:
        p = Path(arg)
        print(f"\n=== {p.name} ===")
        issues, errors = check_card(p)
        for x in issues:
            print(x)
        warns = sum(1 for x in issues if x.startswith('[W]'))
        total_e += errors
        total_w += warns
        print(f"--- {errors} errors, {warns} warnings")
    print(f"\n总计: {total_e} errors, {total_w} warnings")
    sys.exit(1 if total_e else 0)


if __name__ == '__main__':
    main()
