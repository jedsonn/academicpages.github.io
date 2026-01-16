#!/usr/bin/env python3
# research-radar/main.py
"""
Research Radar - Main crawler orchestrator.

Usage:
    python main.py                      # Run with defaults
    python main.py --days 3             # Look back 3 days
    python main.py --sources arxiv-qfin # Only crawl arXiv
    python main.py --no-summarize       # Skip summarization
    python main.py --email              # Send email digest
    python main.py --list-sources       # List available sources
"""

import argparse
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Set
from pathlib import Path

from config import Paper, SOURCES, PRESETS, DEFAULT_LOOKBACK_DAYS, EMAIL_CONFIG
from sources.arxiv import ArxivCrawler
from sources.ssrn import SSRNCrawler
from sources.nber import NBERCrawler
from summarizer import summarize_papers_batch, generate_digest_html


# Data storage
DATA_DIR = Path(__file__).parent / "data"
SEEN_PAPERS_FILE = DATA_DIR / "seen_papers.json"
PAPERS_HISTORY_FILE = DATA_DIR / "papers_history.json"


def load_seen_papers() -> Set[str]:
    """Load set of previously seen paper IDs."""
    if SEEN_PAPERS_FILE.exists():
        with open(SEEN_PAPERS_FILE, 'r') as f:
            data = json.load(f)
            return set(data.get('seen_ids', []))
    return set()


def save_seen_papers(seen_ids: Set[str]):
    """Save seen paper IDs."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SEEN_PAPERS_FILE, 'w') as f:
        json.dump({'seen_ids': list(seen_ids), 'updated_at': datetime.now().isoformat()}, f)


def save_papers_to_history(papers: List[Paper]):
    """Append papers to history file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    history = []
    if PAPERS_HISTORY_FILE.exists():
        with open(PAPERS_HISTORY_FILE, 'r') as f:
            history = json.load(f)

    for paper in papers:
        history.append(paper.to_dict())

    with open(PAPERS_HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)


def get_crawler(source_id: str, source_config: dict):
    """Create appropriate crawler for a source."""
    source_type = source_config['type']

    if source_type == 'arxiv':
        return ArxivCrawler(source_id, source_config.get('category', 'q-fin'))
    elif source_type == 'ssrn':
        network = source_config.get('network_id', 'accounting')
        network_map = {v: k for k, v in SSRNCrawler.NETWORKS.items()}
        network_name = network_map.get(network, network)
        return SSRNCrawler(source_id, network_name)
    elif source_type == 'nber':
        return NBERCrawler(source_id)
    else:
        raise ValueError(f"Unknown source type: {source_type}")


def crawl_sources(
    source_ids: List[str] = None,
    since: datetime = None,
    skip_seen: bool = True
) -> List[Paper]:
    """Crawl specified sources for new papers."""
    if since is None:
        since = datetime.now() - timedelta(days=DEFAULT_LOOKBACK_DAYS)

    if source_ids is None:
        sources_to_crawl = {k: v for k, v in SOURCES.items() if v.get('enabled', True)}
    else:
        sources_to_crawl = {k: SOURCES[k] for k in source_ids if k in SOURCES}

    if not sources_to_crawl:
        print("No sources to crawl!")
        return []

    seen_ids = load_seen_papers() if skip_seen else set()
    all_papers = []

    for source_id, source_config in sources_to_crawl.items():
        print(f"\n{'='*60}")
        print(f"Crawling: {source_config['name']}")
        print(f"{'='*60}")

        try:
            crawler = get_crawler(source_id, source_config)
            papers = crawler.fetch_papers(since=since)

            new_papers = [p for p in papers if p.external_id not in seen_ids]
            print(f"Found {len(papers)} papers, {len(new_papers)} are new")

            all_papers.extend(new_papers)

            for p in new_papers:
                seen_ids.add(p.external_id)

        except Exception as e:
            print(f"Error crawling {source_id}: {e}")
            import traceback
            traceback.print_exc()

    save_seen_papers(seen_ids)
    return all_papers


def format_digest_text(papers: List[Paper]) -> str:
    """Format papers as plain text digest."""
    if not papers:
        return "No new papers found today."

    by_source: Dict[str, List[Paper]] = {}
    for paper in papers:
        if paper.source not in by_source:
            by_source[paper.source] = []
        by_source[paper.source].append(paper)

    lines = [
        f"Research Radar - {datetime.now().strftime('%A, %B %d, %Y')}",
        f"Found {len(papers)} new papers\n",
        "=" * 60,
    ]

    for source, source_papers in by_source.items():
        lines.append(f"\n## {source.upper().replace('-', ' ')}\n")

        for paper in source_papers:
            authors = ', '.join(paper.authors[:3]) if paper.authors else 'Unknown'
            if len(paper.authors) > 3:
                authors += ' et al.'

            lines.append(f"* {paper.title}")
            lines.append(f"   Authors: {authors}")
            if paper.published_at:
                lines.append(f"   Date: {paper.published_at.strftime('%Y-%m-%d')}")
            if paper.summary:
                lines.append(f"   Summary: {paper.summary}")
            lines.append(f"   Link: {paper.url}")
            lines.append("")

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Research Radar - Academic Paper Crawler')
    parser.add_argument('--days', type=int, default=DEFAULT_LOOKBACK_DAYS,
                        help='How many days back to look for papers')
    parser.add_argument('--sources', nargs='+',
                        help='Specific sources to crawl')
    parser.add_argument('--preset', choices=list(PRESETS.keys()),
                        help='Use a preset source configuration')
    parser.add_argument('--no-summarize', action='store_true',
                        help='Skip AI summarization')
    parser.add_argument('--output', choices=['console', 'file', 'html'], default='console',
                        help='Output format')
    parser.add_argument('--output-file', type=str,
                        help='Output file path')
    parser.add_argument('--email', action='store_true',
                        help='Send email digest')
    parser.add_argument('--email-method', choices=['resend', 'gmail'], default='gmail',
                        help='Email sending method')
    parser.add_argument('--include-seen', action='store_true',
                        help='Include previously seen papers')
    parser.add_argument('--list-sources', action='store_true',
                        help='List available sources and exit')

    args = parser.parse_args()

    if args.list_sources:
        print("\nAvailable Sources:")
        print("-" * 40)
        for source_id, config in SOURCES.items():
            status = "+" if config.get('enabled', True) else "-"
            print(f"  {status} {source_id}: {config['name']}")

        print("\nPresets:")
        print("-" * 40)
        for preset_id, preset in PRESETS.items():
            print(f"  {preset_id}: {preset['name']}")
            print(f"     Sources: {', '.join(preset['sources'])}")
        return

    source_ids = None
    if args.preset:
        source_ids = PRESETS[args.preset]['sources']
        print(f"Using preset: {args.preset}")
    elif args.sources:
        source_ids = args.sources

    since = datetime.now() - timedelta(days=args.days)
    print(f"\nLooking for papers since: {since.strftime('%Y-%m-%d')}")

    papers = crawl_sources(
        source_ids=source_ids,
        since=since,
        skip_seen=not args.include_seen
    )

    if not papers:
        print("\n* No new papers found!")
        return

    print(f"\n{'='*60}")
    print(f"Found {len(papers)} new papers total")
    print(f"{'='*60}")

    if not args.no_summarize:
        print("\n* Generating summaries with GPT-5-mini...")
        try:
            papers = summarize_papers_batch(papers)
        except Exception as e:
            print(f"Warning: Summarization failed: {e}")
            print("Continuing without summaries...")

    save_papers_to_history(papers)

    # Output
    if args.output == 'console':
        print("\n" + format_digest_text(papers))

    elif args.output == 'file':
        output_path = args.output_file or f"digest_{datetime.now().strftime('%Y%m%d')}.txt"
        with open(output_path, 'w') as f:
            f.write(format_digest_text(papers))
        print(f"\n+ Digest saved to: {output_path}")

    elif args.output == 'html':
        output_path = args.output_file or f"digest_{datetime.now().strftime('%Y%m%d')}.html"
        html = generate_digest_html(papers)
        with open(output_path, 'w') as f:
            f.write(html)
        print(f"\n+ HTML digest saved to: {output_path}")

    # Email
    if args.email:
        print("\n* Sending email digest...")
        from email_sender import send_digest_email

        html = generate_digest_html(papers)
        subject = f"{EMAIL_CONFIG['subject_prefix']} - {len(papers)} new papers - {datetime.now().strftime('%Y-%m-%d')}"

        try:
            send_digest_email(
                to_email=EMAIL_CONFIG['to_email'],
                subject=subject,
                html_content=html,
                method=args.email_method
            )
            print("+ Email sent!")
        except Exception as e:
            print(f"- Failed to send email: {e}")


if __name__ == "__main__":
    main()
