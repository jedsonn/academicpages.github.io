# research-radar/summarizer.py
"""
Paper summarizer using OpenAI GPT-5-mini.
Fast, cheap, and reliable.
"""
import os
from typing import List, Dict
from openai import OpenAI

from config import Paper


def get_openai_client():
    """Get OpenAI client, checking for API key."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable not set. "
            "Get your key at: https://platform.openai.com/api-keys"
        )
    return OpenAI(api_key=api_key)


def summarize_paper(paper: Paper, client=None) -> str:
    """Generate a concise summary of a single paper."""
    if client is None:
        client = get_openai_client()

    prompt = f"""Summarize this academic paper in 2-3 sentences for a researcher.
Focus on: (1) the main research question, (2) methodology/approach, (3) key finding or contribution.

Title: {paper.title}
Authors: {', '.join(paper.authors) if paper.authors else 'Not specified'}
Abstract: {paper.abstract if paper.abstract else 'Not available'}

Write in clear academic language. Be concise and specific. No fluff or generic statements."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=250,
        temperature=0.3  # Lower temperature for more consistent output
    )

    return response.choices[0].message.content.strip()


def summarize_papers_batch(papers: List[Paper], client=None) -> List[Paper]:
    """Generate summaries for a batch of papers."""
    if client is None:
        client = get_openai_client()

    for i, paper in enumerate(papers):
        print(f"Summarizing paper {i+1}/{len(papers)}: {paper.title[:50]}...")
        try:
            paper.summary = summarize_paper(paper, client)
        except Exception as e:
            print(f"  Failed to summarize: {e}")
            paper.summary = f"[Summary unavailable] {paper.abstract[:200]}..." if paper.abstract else "[No abstract available]"

    return papers


def generate_digest_html(papers: List[Paper]) -> str:
    """Generate an HTML email digest."""
    from datetime import datetime

    # Group papers by source
    by_source: Dict[str, List[Paper]] = {}
    for paper in papers:
        source_name = paper.source.replace('-', ' ').title()
        if source_name not in by_source:
            by_source[source_name] = []
        by_source[source_name].append(paper)

    sections = []
    for source, source_papers in by_source.items():
        paper_html = ""
        for p in source_papers:
            authors_str = ', '.join(p.authors[:3]) if p.authors else 'Authors not listed'
            if len(p.authors) > 3:
                authors_str += ' et al.'

            summary = p.summary if p.summary else (p.abstract[:300] + '...' if p.abstract else 'No abstract available')

            paper_html += f"""
            <div style="margin-bottom: 24px; padding-bottom: 24px; border-bottom: 1px solid #e5e7eb;">
                <h3 style="margin: 0 0 8px 0; font-size: 16px;">
                    <a href="{p.url}" style="color: #2563eb; text-decoration: none;">{p.title}</a>
                </h3>
                <p style="color: #6b7280; margin: 0 0 8px 0; font-size: 14px;">
                    {authors_str}
                </p>
                <p style="margin: 0; color: #374151; font-size: 14px; line-height: 1.5;">
                    {summary}
                </p>
            </div>
            """

        sections.append(f"""
        <div style="margin-bottom: 32px;">
            <h2 style="color: #1f2937; font-size: 18px; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px; margin-bottom: 16px;">
                {source}
            </h2>
            {paper_html}
        </div>
        """)

    today = datetime.now().strftime("%A, %B %d, %Y")

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9fafb;">
    <div style="background-color: white; padding: 32px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
        <h1 style="color: #1f2937; font-size: 24px; margin: 0 0 8px 0;">Research Radar</h1>
        <p style="color: #6b7280; margin: 0 0 32px 0;">{today} - {len(papers)} new papers</p>

        {''.join(sections)}

        <footer style="margin-top: 32px; padding-top: 24px; border-top: 1px solid #e5e7eb; color: #9ca3af; font-size: 12px;">
            <p>Research Radar - Your daily academic paper digest</p>
        </footer>
    </div>
</body>
</html>
"""
    return html
