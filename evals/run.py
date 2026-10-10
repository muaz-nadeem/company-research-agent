"""Compare the agent workflow with one synthesis call over the same retrieved evidence.

python -m evals.run --limit 1    # paid provider calls
python -m evals.run --offline   # harness smoke test; NOT a quality benchmark
"""
import argparse
import json
import re
import time
import uuid
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from graph.builder import build_graph
from graph.llm import get_llm
from graph.nodes import SYNTHESIS_SYSTEM, normalize_citations
from graph.service import UsageCollector, execute_run
from tools.search import SearchResult, search_company

ROOT = Path(__file__).resolve().parent


def citation_metrics(answer, sources):
    cited = re.findall(r'\]\(#source-(S\d+)\)', answer)
    valid = {s['id'] for s in sources}
    return {'citation_count': len(cited), 'invalid_citations': len([c for c in cited if c not in valid]),
            'source_count': len(sources)}


def run_case(case, offline=False):
    started = time.monotonic()
    evidence = SearchResult('Fixture evidence, not factual research.', [{'id': 'S1', 'title': 'Fixture', 'url': 'https://example.com', 'excerpt': 'Fixture evidence', 'retrieved_at': '2026-10-10'}]) if offline else search_company(case['company'], case['question'])
    search_ms = round((time.monotonic() - started) * 1000)
    rows = []
    for strategy in ('single_pass', 'agent_workflow'):
        start = time.monotonic()
        if offline:
            result = {'answer': 'Fixture answer [1](#source-S1)', 'sources': evidence.sources, 'status': 'completed',
                      'metrics': {'llm_calls': 0, 'input_tokens': 0, 'output_tokens': 0, 'estimated_llm_cost_usd': None}}
        elif strategy == 'single_pass':
            usage = UsageCollector()
            response = get_llm().invoke([SystemMessage(content=SYNTHESIS_SYSTEM),
                HumanMessage(content=f"Question: {case['question']}\nSources: {evidence.content}")], config={'callbacks': [usage]})
            result = {'answer': response.content, 'sources': evidence.sources, 'status': 'completed', 'metrics': usage.metrics()}
        else:
            # Freeze retrieval so the two strategies see identical evidence.
            with patch('graph.nodes.search_company', return_value=evidence):
                result = execute_run({'prompt': case['question'], 'thread_id': str(uuid.uuid4()),
                    'message_id': str(uuid.uuid4()), 'resume': False}, lambda _: None, lambda: False, build_graph(InMemorySaver()))
        result['answer'] = normalize_citations(result['answer'], result['sources'])
        rows.append({'case': case['id'], 'strategy': strategy, 'offline_fixture': offline,
            'status': result['status'], 'answer': result['answer'], 'sources': result['sources'],
            'metrics': {**result['metrics'], 'duration_ms': round((time.monotonic() - start) * 1000), 'shared_search_ms': search_ms,
                        **citation_metrics(result['answer'], result['sources'])},
            'human_review': {'rubric': case['rubric'], 'accuracy_0_to_4': None, 'coverage_0_to_4': None,
                             'claim_support_0_to_4': None, 'notes': ''}})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--limit', type=int, default=5)
    parser.add_argument('--output', default=str(ROOT / 'results.json'))
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    cases = json.loads((ROOT / 'cases.json').read_text(encoding='utf-8'))[:args.limit]
    output = Path(args.output)
    rows = json.loads(output.read_text(encoding='utf-8')) if args.resume and output.exists() else []
    complete = {case['id'] for case in cases if len([row for row in rows if row['case'] == case['id'] and row.get('strategy') and row.get('offline_fixture') == args.offline]) == 2}
    if not args.offline:
        get_llm()  # Exclude provider library import time from model latency.
    for case in cases:
        if case['id'] in complete:
            continue
        rows = [row for row in rows if row['case'] != case['id']]
        try:
            rows.extend(run_case(case, args.offline))
        except Exception as exc:
            rows.append({'case': case['id'], 'error_type': type(exc).__name__, 'status': 'failed'})
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix('.tmp')
        temporary.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding='utf-8')
        temporary.replace(output)
        print(f"Finished {case['id']}", flush=True)
    print(f'Results: {args.output}. Human rubric scores must be supplied before claiming a quality improvement.')
    if any(row.get('status') == 'failed' for row in rows):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
