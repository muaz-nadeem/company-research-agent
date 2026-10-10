from tools.search import build_queries


def test_historical_queries_do_not_get_current_year_injected():
    queries = build_queries('Stripe', 'Payment volume in 2024', '2026-10-10')
    assert all('2024' in query and '2026' not in query for query in queries)


def test_latest_queries_use_current_date():
    assert all('2026-10-10' in query for query in build_queries('Stripe', 'latest news', '2026-10-10'))
