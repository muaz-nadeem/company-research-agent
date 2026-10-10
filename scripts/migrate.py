"""Apply the additive application migration using the configured PostgreSQL URL."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')


def main():
    url = os.getenv('APP_DATABASE_URL') or os.getenv('DATABASE_URL')
    if not url or url.startswith('sqlite:///'):
        print('SQLite application schema is created automatically at startup.')
        return
    import psycopg
    with psycopg.connect(url, connect_timeout=10, autocommit=True) as conn:
        conn.execute((ROOT / 'supabase/migrations/002_research_workspace.sql').read_text(encoding='utf-8'))
    print('Application schema migration applied.')


if __name__ == '__main__':
    main()
