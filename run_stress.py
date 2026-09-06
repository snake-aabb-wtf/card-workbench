#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_stress —— 角色卡通用压测 runner（卡无关，探针文件驱动）。

用法：
    python3 run_stress.py <card.json> <probes.json> [--models m1,m2] [--out 结果.md]

probes.json 格式：
{
  "name": "芙宁娜「元」卡探针组",
  "defaults": {"max_tokens": 8000, "temperature": 0.9, "init_suffix": "开始"},
  "models": ["z-ai/glm-5.3-flash"],            // 可省略，用 --models 或默认
  "probes": [
    {
      "id": "P1_默认开局",
      "init": "开始",                           // 开局用户输入
      "turns": ["..."],                         // 后续回合（可省）
      "followup": "...",                        // 追问（可省）
      "expect": "应锁定默认：终幕后+旅行者+茶会"  // 预期，仅写入报告供人工比对
    }
  ]
}

模拟 SillyTavern 注入：constant（蓝灯）条目全量常驻 + 命中 keys 的绿灯条目追加。
输出：markdown 报告，逐探针 × 逐模型收对话全文 + expect 提示行。
**增量写盘：每完成一组立即追加到报告（断气不丢已完成组）；--resume 可续跑跳过已完成组。**
"""
import argparse
import json
import time
import urllib.request
from datetime import date
from pathlib import Path

KEY_PATH = Path(__file__).resolve().parents[1] / '.secrets' / 'openrouter-test-o5.key'
API = 'https://openrouter.ai/api/v1/chat/completions'
DEFAULT_MODELS = ['z-ai/glm-5.3-flash']


def build_system(card_data: dict) -> str:
    """按 SillyTavern 习惯拼 system：description+personality+scenario+示例。"""
    parts = [card_data.get('description', ''), card_data.get('personality', ''),
             '【场景】' + card_data.get('scenario', '')]
    sys = '\n\n'.join(p for p in parts if p.strip())
    mes = card_data.get('mes_example', '').strip()
    if mes:
        sys += '\n\n【示例对话（仅学习语气与格式，勿复述内容）】\n' + mes
    return sys


def lorebook_lookup(card_data: dict, text: str) -> str:
    """constant 全量 + keys 命中条目，拼成【相关设定】块。"""
    entries = (card_data.get('character_book') or {}).get('entries') or []
    const = '\n'.join(e['content'] for e in entries if e.get('constant') and e.get('content'))
    trig = '\n'.join(e['content'] for e in entries
                     if not e.get('constant') and any(k in text for k in (e.get('keys') or []))
                     and e.get('content'))
    parts = [p for p in (const, trig) if p]
    return '\n\n【相关设定】' + '\n'.join(parts) if parts else ''


def call(model: str, msgs: list, max_tokens: int, temperature: float) -> str:
    body = json.dumps({"model": model, "messages": msgs, "max_tokens": max_tokens,
                       "temperature": temperature}).encode()
    req = urllib.request.Request(API, data=body, headers={
        'Authorization': 'Bearer ' + KEY_PATH.read_text().strip(),
        'Content-Type': 'application/json'})
    content = None
    for attempt in range(3):
        try:
            r = json.load(urllib.request.urlopen(req, timeout=240))
            content = r['choices'][0]['message'].get('content')
            if content and content.strip():
                return content
        except Exception as e:
            if attempt == 2:
                return f'(API error after retry: {e})'
            time.sleep(5 * (attempt + 1))
    return content or '(empty after retry)'


def run_probe(card_data: dict, model: str, probe: dict, defaults: dict) -> str:
    max_tokens = probe.get('max_tokens', defaults.get('max_tokens', 8000))
    temperature = probe.get('temperature', defaults.get('temperature', 0.9))
    msgs = [{'role': 'system', 'content': build_system(card_data) + lorebook_lookup(card_data, probe['init'])}]
    msgs.append({'role': 'user', 'content': probe['init']})
    outs = [call(model, msgs, max_tokens, temperature)]
    msgs.append({'role': 'assistant', 'content': outs[-1]})
    for t in probe.get('turns', []):
        lb = lorebook_lookup(card_data, t)
        if lb:
            msgs[0]['content'] += lb
        msgs.append({'role': 'user', 'content': t})
        outs.append(call(model, msgs, max_tokens, temperature))
        msgs.append({'role': 'assistant', 'content': outs[-1]})
    if probe.get('followup'):
        msgs.append({'role': 'user', 'content': probe['followup']})
        outs.append(call(model, msgs, max_tokens, temperature))
    return '\n\n---\n\n'.join(outs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('card')
    ap.add_argument('probes')
    ap.add_argument('--models', help='逗号分隔，覆盖 probes.json 里的 models')
    ap.add_argument('--out', help='输出 md 路径，默认 tests/<card>_stress_<date>.md')
    ap.add_argument('--resume', action='store_true',
                    help='续跑：跳过报告里已有的探针×模型组，增量追加（进程中断后可接上）')
    args = ap.parse_args()

    card_data = json.loads(Path(args.card).read_text(encoding='utf-8'))['data']
    spec = json.loads(Path(args.probes).read_text(encoding='utf-8'))
    defaults = spec.get('defaults', {})
    models = (args.models.split(',') if args.models else spec.get('models', DEFAULT_MODELS))

    out_path = Path(args.out) if args.out else (
        Path(__file__).resolve().parent / 'tests' /
        f"{Path(args.card).stem}_stress_{date.today().isoformat()}.md")
    out_path.parent.mkdir(exist_ok=True)

    done_keys: set[str] = set()
    if args.resume and out_path.exists():
        import re
        for m in re.finditer(r'^===== (.+?) =====$', out_path.read_text(encoding='utf-8'), re.M):
            done_keys.add(m.group(1))
        print(f'resume: {len(done_keys)} 组已完成，跳过')

    header = [f"# 压测报告：{card_data.get('name', '?')}（{date.today().isoformat()}）",
              f"模型：{', '.join(models)} · max_tokens={defaults.get('max_tokens', 8000)} · temp={defaults.get('temperature', 0.9)}"]
    if not out_path.exists():
        out_path.write_text('\n'.join(header), encoding='utf-8')

    for probe in spec['probes']:
        for model in models:
            short = model.split('/')[-1]
            key = f"{probe['id']}@{short}"
            if key in done_keys:
                print(f'== {key} 已有，跳过', flush=True)
                continue
            print(f'== {key} ...', flush=True)
            try:
                text = run_probe(card_data, model, probe, defaults)
            except Exception as e:
                text = f'ERROR: {e}'
            # 一组一落盘：立即追加，断气不丢已完成组（与调查员纪律对齐）
            with open(out_path, 'a', encoding='utf-8') as f:
                f.write(f"\n\n===== {key} =====\n")
                f.write(f"> 预期：{probe.get('expect', '（未注明）')}\n\n")
                f.write(text)

    print(f'done -> {out_path}')


if __name__ == '__main__':
    main()
