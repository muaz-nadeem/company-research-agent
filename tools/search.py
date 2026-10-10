import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse


@dataclass
class SearchResult:
    content: str
    sources: list[dict]


def search_company(company_name: str, user_question: str, validation_feedback: str | None = None) -> SearchResult:
    from langchain_tavily import TavilySearch
    today = datetime.now(timezone.utc).date().isoformat()
    # Preserve historical dates in the user's request instead of forcing a recent year.
    queries = build_queries(company_name, user_question, today)
    if validation_feedback:
        queries.append(f"{company_name} {user_question} {validation_feedback[:500]}")

    def search(query, domains=None):
        tool = TavilySearch(max_results=4, search_depth=os.getenv("TAVILY_SEARCH_DEPTH", "basic"),
                            include_answer=False, include_raw_content=False, **({'include_domains': domains} if domains else {}))
        return tool.invoke({"query": query})

    sources, seen, failures = [], set(), 0
    with ThreadPoolExecutor(max_workers=len(queries)) as pool:
        futures = [pool.submit(search, query) for query in queries]
        for future in futures:
            try:
                result = future.result(timeout=60)
            except Exception:
                failures += 1
                continue
            items = result.get("results", []) if isinstance(result, dict) else result if isinstance(result, list) else []
            for item in items:
                url = str(item.get("url", ""))
                if url in seen or urlparse(url).scheme not in ("http", "https") or not urlparse(url).hostname:
                    continue
                seen.add(url)
                sources.append({"id": f"S{len(sources) + 1}", "url": url,
                    "title": str(item.get("title") or urlparse(url).hostname),
                    "excerpt": str(item.get("content", ""))[:1200],
                    "published_at": item.get("published_date"), "retrieved_at": today})
    if failures == len(queries):
        raise RuntimeError("Search provider unavailable")
    # Discover plausible company domains from actual results, then search within
    # them for the requested period. This is a relevance heuristic, not verification.
    names = {re.sub(r'[^a-z0-9]', '', name.lower()) for name in re.split(r',| and ', company_name)}
    domains = sorted({urlparse(s['url']).hostname.removeprefix('www.') for s in sources
        if urlparse(s['url']).hostname and any(len(name) >= 3 and name in urlparse(s['url']).hostname.split('.') for name in names)})
    if domains:
        try:
            primary = search(f"{company_name} {user_question}", domains)
            for item in primary.get('results', []) if isinstance(primary, dict) else []:
                url = str(item.get('url', ''))
                if url not in seen and urlparse(url).scheme in ('http', 'https') and urlparse(url).hostname:
                    seen.add(url)
                    sources.append({'id': '', 'url': url, 'title': str(item.get('title') or url),
                        'excerpt': str(item.get('content', ''))[:1600], 'published_at': item.get('published_date'), 'retrieved_at': today})
        except Exception:
            pass  # Keep already retrieved evidence; its limitations remain visible.
    sources.sort(key=lambda s: 0 if urlparse(s['url']).hostname.removeprefix('www.') in domains else 1)
    for i, source in enumerate(sources):
        source['id'] = f'S{i + 1}'
    content = "\n\n".join(f"[{s['id']}] {s['title']}\nURL: {s['url']}\n"
        f"Published: {s['published_at'] or 'unknown'}; retrieved: {today}\n{s['excerpt']}" for s in sources)
    return SearchResult(content or "No supporting sources found. Disclose this limitation.", sources)


def build_queries(company, question, today):
    historical = bool(re.search(r'\b(?:19|20)\d{2}\b', question))
    current = bool(re.search(r'\b(latest|recent|current|today)\b', question, re.I))
    suffix = f' as of {today}' if current and not historical else ''
    return [f'{company} {question}{suffix}', f'{company} official annual report newsroom {question}{suffix}']
