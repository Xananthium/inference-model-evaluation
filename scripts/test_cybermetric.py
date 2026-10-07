"""Evaluate CyberMetric-80 through the existing authenticated native vLLM API.

Stores only final answers, choices, token counts, and timing; never saves or
prints private reasoning. Dataset remains local; public reports identify its
source and SHA-256 rather than redistributing the questions.
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import re
import time

import benchmark_client as h

SYSTEM = 'Select the single best answer to the cybersecurity multiple-choice question. Return only the selected letter inside XML tags, for example <xml>A</xml>. Use one of A, B, C, D. Do not include explanations in the final answer.'

def score(final, expected):
    strict = re.fullmatch(r'<xml>\s*([ABCD])\s*</xml>', final, flags=re.I)
    parsed = strict or re.search(r'<xml>\s*([ABCD])\s*</xml>', final, flags=re.I)
    # Accept an unambiguous standalone choice for knowledge scoring while
    # retaining the independent strict XML score. Never inspect reasoning.
    if not parsed:
        for pattern in (r'<\s*([ABCD])\s*>', r'\\boxed\{([ABCD])\}', r'([ABCD])[.]?'):
            parsed = re.fullmatch(pattern, final, flags=re.I)
            if parsed:
                break
    answer = parsed.group(1).upper() if parsed else None
    return {'choice': answer, 'correct': answer == expected,
            'strict_format': bool(strict), 'strict_xml_correct': bool(strict) and answer == expected}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--variant', required=True)
    ap.add_argument('--concurrency', type=int, default=4)
    ap.add_argument('--max-tokens', type=int, default=2048)
    ap.add_argument('--retry-truncated', action='store_true')
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    raw = args.dataset.read_bytes()
    questions = json.loads(raw)['questions']
    assert len(questions) == 80
    def run(item, budget=None):
        i, question = item
        path = args.output/f'question-{i:03d}{"-budget-retry" if budget else ""}.json'
        if path.exists():
            cached = json.loads(path.read_text())
            cached.update(score(cached['final_answer'], question['solution']))
            h.save(path, cached)
            return cached
        prompt = question['question'] + '\n\n' + '\n'.join(f'{k}) {v}' for k,v in question['answers'].items())
        payload = {'model': h.MODEL, 'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': prompt}],
                   'max_tokens': budget or args.max_tokens, 'seed': 42, 'chat_template_kwargs': {'enable_thinking': True}, 'stream': False}
        start = time.monotonic()
        with h.post('/v1/chat/completions', payload) as response:
            value = json.loads(response.read())
        choice = value['choices'][0]
        final = (choice['message'].get('content') or '').strip()
        row = {'index': i, 'expected': question['solution'], **score(final, question['solution']),
               'final_answer': final, 'finish_reason': choice.get('finish_reason'),
               'max_output_tokens': budget or args.max_tokens,
               'usage': value.get('usage'), 'wall_seconds': round(time.monotonic()-start,3)}
        h.save(path,row)
        print(json.dumps({k:row[k] for k in ['index','choice','expected','correct','strict_format','wall_seconds']}),flush=True)
        return row
    started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        rows = list(pool.map(run, enumerate(questions)))
    if args.retry_truncated:
        truncated = [(row['index'],questions[row['index']]) for row in rows if row['finish_reason']=='length']
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            retried = list(pool.map(lambda item: run(item,args.max_tokens*2),truncated))
        for row in retried:
            rows[row['index']]['budget_retry'] = row
    result = {'variant': args.variant, 'benchmark': 'CyberMetric-80-v1',
              'source': 'https://github.com/cybermetric/CyberMetric', 'dataset_sha256': hashlib.sha256(raw).hexdigest(),
              'questions': len(rows), 'correct': sum(r['correct'] for r in rows),
              'accuracy_percent': round(100*sum(r['correct'] for r in rows)/len(rows),2),
              'strict_xml_answers': sum(r['strict_format'] for r in rows),
              'strict_xml_correct': sum(r['strict_xml_correct'] for r in rows),
              'parseable_answers': sum(r['choice'] is not None for r in rows),
              'truncated_answers': sum(r['finish_reason']=='length' for r in rows),
              'max_output_tokens': args.max_tokens, 'seed': 42, 'thinking_enabled': True,
              'concurrency': args.concurrency, 'wall_seconds': round(time.monotonic()-started,3),
              'budget_retry_enabled': args.retry_truncated,
              'correct_after_budget_retry': sum(r.get('budget_retry',r)['correct'] for r in rows),
              'still_truncated_after_retry': sum(r.get('budget_retry',r)['finish_reason']=='length' for r in rows),
              'note': 'Local adapted XML-answer protocol; sampling uses the documented serving profile. This small public knowledge benchmark may overlap training data and does not measure practical exploit or remediation skills.',
              'answers': rows}
    h.save(args.output/'assessment.json', result)
    print(json.dumps({k:v for k,v in result.items() if k!='answers'}),flush=True)

if __name__ == '__main__':
    main()
