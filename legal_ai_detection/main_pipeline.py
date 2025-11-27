"""
Main Pipeline for Legal AI Detection

Orchestrates the full workflow:
1. Compile URL list
2. Scrape websites
3. Run detection
4. Generate reports
"""

import json
import csv
from datetime import datetime
from pathlib import Path
from dataclasses import asdict
from collections import defaultdict

from config import OUTPUT_DIR, DATA_DIR, HTML_CACHE_DIR
from hidden_detector import HiddenContentDetector, AnalysisResult
from legal_scraper import LegalSiteScraper, ScrapedPage


class LegalAIDetectionPipeline:
    """
    End-to-end pipeline for detecting AI-targeted manipulation
    in legal settlement websites.
    """

    def __init__(self):
        self.scraper = LegalSiteScraper()
        self.detector = HiddenContentDetector()
        self.results = []
        self.scraped_pages = []

    def run(self, urls: list, use_cache: bool = True) -> list:
        """
        Run the full detection pipeline.

        Args:
            urls: List of URLs to analyze
            use_cache: Whether to use cached HTML

        Returns:
            List of AnalysisResult objects
        """
        print("=" * 70)
        print("LEGAL AI DETECTION PIPELINE")
        print("=" * 70)
        print(f"URLs to analyze: {len(urls)}")
        print(f"Cache enabled: {use_cache}")
        print(f"Output directory: {OUTPUT_DIR}")
        print()

        # Phase 1: Scrape
        print("-" * 70)
        print("PHASE 1: SCRAPING")
        print("-" * 70)
        self.scraped_pages = self.scraper.fetch_multiple(urls, use_cache=use_cache)

        successful = [p for p in self.scraped_pages if p.status_code == 200]
        print(f"\nScraped {len(successful)}/{len(urls)} successfully")
        print(f"Scraper stats: {self.scraper.get_stats()}")

        # Phase 2: Detect
        print("\n" + "-" * 70)
        print("PHASE 2: DETECTION")
        print("-" * 70)

        self.results = []
        for i, page in enumerate(self.scraped_pages):
            if page.status_code != 200 or not page.html_content:
                continue

            print(f"[{i+1}/{len(self.scraped_pages)}] Analyzing {page.url[:60]}...")
            result = self.detector.analyze(page.html_content, page.url)
            self.results.append(result)

            # Print immediate findings for high-risk sites
            if result.risk_level in ['high', 'critical']:
                print(f"  ⚠️  {result.risk_level.upper()}: Score={result.suspiciousness_score}")

        print(f"\nAnalyzed {len(self.results)} pages")

        # Phase 3: Report
        print("\n" + "-" * 70)
        print("PHASE 3: GENERATING REPORTS")
        print("-" * 70)

        self._generate_summary_report()
        self._generate_detailed_json()
        self._generate_csv_report()
        self._generate_findings_report()

        print("\n" + "=" * 70)
        print("PIPELINE COMPLETE")
        print("=" * 70)

        return self.results

    def _generate_summary_report(self):
        """Generate summary statistics."""
        output_path = OUTPUT_DIR / "summary_report.txt"

        # Calculate statistics
        by_risk = defaultdict(list)
        for r in self.results:
            by_risk[r.risk_level].append(r)

        total_hidden_blocks = sum(len(r.hidden_blocks) for r in self.results)
        total_prompt_hits = sum(len(r.prompt_injection_hits) for r in self.results)
        total_suspicious_comments = sum(len(r.suspicious_comments) for r in self.results)
        total_metadata_issues = sum(len(r.metadata_issues) for r in self.results)

        avg_score = sum(r.suspiciousness_score for r in self.results) / len(self.results) if self.results else 0

        with open(output_path, 'w') as f:
            f.write("=" * 70 + "\n")
            f.write("LEGAL AI MANIPULATION DETECTION - SUMMARY REPORT\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write("=" * 70 + "\n\n")

            f.write("OVERVIEW\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total URLs analyzed: {len(self.results)}\n")
            f.write(f"Average suspiciousness score: {avg_score:.2f}\n\n")

            f.write("RISK DISTRIBUTION\n")
            f.write("-" * 40 + "\n")
            for level in ['critical', 'high', 'medium', 'low']:
                count = len(by_risk[level])
                pct = (count / len(self.results) * 100) if self.results else 0
                f.write(f"  {level.upper():10s}: {count:3d} ({pct:5.1f}%)\n")
            f.write("\n")

            f.write("DETECTION TOTALS\n")
            f.write("-" * 40 + "\n")
            f.write(f"  Hidden content blocks: {total_hidden_blocks}\n")
            f.write(f"  Prompt injection hits: {total_prompt_hits}\n")
            f.write(f"  Suspicious comments: {total_suspicious_comments}\n")
            f.write(f"  Metadata issues: {total_metadata_issues}\n\n")

            f.write("TOP 10 MOST SUSPICIOUS SITES\n")
            f.write("-" * 40 + "\n")
            sorted_results = sorted(self.results, key=lambda x: x.suspiciousness_score, reverse=True)
            for i, r in enumerate(sorted_results[:10]):
                f.write(f"{i+1:2d}. [{r.risk_level.upper():8s}] Score: {r.suspiciousness_score:5.1f} - {r.url[:50]}\n")
            f.write("\n")

            # Sites with prompt injection
            prompt_sites = [r for r in self.results if r.prompt_injection_hits]
            if prompt_sites:
                f.write("SITES WITH PROMPT INJECTION PATTERNS\n")
                f.write("-" * 40 + "\n")
                for r in prompt_sites:
                    patterns = set(h['pattern'] for h in r.prompt_injection_hits)
                    f.write(f"  {r.url[:50]}\n")
                    f.write(f"    Patterns: {', '.join(list(patterns)[:3])}\n")
                f.write("\n")

        print(f"  Summary report: {output_path}")

    def _generate_detailed_json(self):
        """Generate detailed JSON output."""
        output_path = OUTPUT_DIR / "detailed_results.json"

        data = []
        for r in self.results:
            item = {
                'url': r.url,
                'suspiciousness_score': r.suspiciousness_score,
                'risk_level': r.risk_level,
                'summary': r.summary,
                'raw_html_length': r.raw_html_length,
                'visible_text_length': r.visible_text_length,
                'detection_count': len(r.detections),
                'hidden_block_count': len(r.hidden_blocks),
                'prompt_injection_count': len(r.prompt_injection_hits),
                'suspicious_comment_count': len(r.suspicious_comments),
                'metadata_issue_count': len(r.metadata_issues),
                'detections': [
                    {
                        'type': d.detection_type,
                        'risk_level': d.risk_level,
                        'description': d.description,
                        'evidence': d.evidence[:200],
                        'location': d.location,
                        'weight': d.weight
                    }
                    for d in r.detections
                ],
                'hidden_blocks': [
                    {
                        'method': hb.hiding_method,
                        'content_preview': hb.content[:200],
                        'location': hb.location
                    }
                    for hb in r.hidden_blocks
                ],
                'prompt_injection_hits': r.prompt_injection_hits[:10],  # Limit
                'suspicious_comments': r.suspicious_comments[:5],
                'metadata_issues': r.metadata_issues[:5]
            }
            data.append(item)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        print(f"  Detailed JSON: {output_path}")

    def _generate_csv_report(self):
        """Generate CSV for easy analysis in spreadsheets."""
        output_path = OUTPUT_DIR / "results.csv"

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'url', 'score', 'risk_level',
                'hidden_blocks', 'prompt_injections',
                'suspicious_comments', 'metadata_issues',
                'detection_count', 'html_size', 'visible_text_size'
            ])

            for r in self.results:
                writer.writerow([
                    r.url,
                    r.suspiciousness_score,
                    r.risk_level,
                    len(r.hidden_blocks),
                    len(r.prompt_injection_hits),
                    len(r.suspicious_comments),
                    len(r.metadata_issues),
                    len(r.detections),
                    r.raw_html_length,
                    r.visible_text_length
                ])

        print(f"  CSV report: {output_path}")

    def _generate_findings_report(self):
        """Generate detailed findings for manual review."""
        output_path = OUTPUT_DIR / "findings_report.md"

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Legal AI Manipulation Detection - Detailed Findings\n\n")
            f.write(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n")
            f.write("---\n\n")

            # Only include medium+ risk sites
            notable = [r for r in self.results if r.risk_level in ['medium', 'high', 'critical']]
            notable.sort(key=lambda x: x.suspiciousness_score, reverse=True)

            if not notable:
                f.write("## No Notable Findings\n\n")
                f.write("No sites with medium or higher risk level were detected.\n")
                return

            f.write(f"## Notable Findings ({len(notable)} sites)\n\n")

            for i, r in enumerate(notable):
                f.write(f"### {i+1}. {r.url}\n\n")
                f.write(f"**Risk Level:** {r.risk_level.upper()}\n")
                f.write(f"**Suspiciousness Score:** {r.suspiciousness_score}\n\n")

                if r.detections:
                    f.write("#### Detections:\n\n")
                    for d in r.detections:
                        f.write(f"- **[{d.risk_level}] {d.detection_type}**: {d.description}\n")
                        if d.evidence:
                            f.write(f"  - Evidence: `{d.evidence[:100]}...`\n")
                    f.write("\n")

                if r.hidden_blocks:
                    f.write("#### Hidden Content Blocks:\n\n")
                    for hb in r.hidden_blocks[:3]:
                        f.write(f"- **Method:** {hb.hiding_method}\n")
                        f.write(f"  - Content: `{hb.content[:150]}...`\n")
                    f.write("\n")

                if r.prompt_injection_hits:
                    f.write("#### Prompt Injection Patterns:\n\n")
                    seen_patterns = set()
                    for hit in r.prompt_injection_hits[:5]:
                        if hit['pattern'] not in seen_patterns:
                            f.write(f"- Pattern: `{hit['pattern']}`\n")
                            f.write(f"  - Match: `{hit['match']}`\n")
                            seen_patterns.add(hit['pattern'])
                    f.write("\n")

                if r.suspicious_comments:
                    f.write("#### Suspicious Comments:\n\n")
                    for sc in r.suspicious_comments[:2]:
                        f.write(f"- Content: `{sc['content'][:150]}...`\n")
                        f.write(f"  - AI targeting score: {sc['ai_score']}\n")
                    f.write("\n")

                f.write("---\n\n")

        print(f"  Findings report: {output_path}")


def get_default_url_list() -> list:
    """Get a default list of URLs to analyze."""
    return [
        # Settlement administrator sites
        "https://www.gilardi.com",
        "https://www.jndla.com",
        "https://www.simpluris.com",
        "https://www.angeiongroup.com",

        # Data breach settlements
        "https://www.equifaxbreachsettlement.com",
        "https://www.t-mobilesettlement.com",
        "https://www.capitalonesettlement.com",

        # Class action sites
        "https://www.classaction.org",
        "https://www.topclassactions.com",

        # Control (official/academic)
        "https://securities.stanford.edu",
    ]


def main():
    """Run the pipeline with default settings."""
    import argparse

    parser = argparse.ArgumentParser(description='Legal AI Detection Pipeline')
    parser.add_argument('--urls', nargs='+', help='URLs to analyze')
    parser.add_argument('--url-file', type=str, help='File containing URLs (one per line)')
    parser.add_argument('--no-cache', action='store_true', help='Disable caching')
    args = parser.parse_args()

    # Get URLs
    if args.urls:
        urls = args.urls
    elif args.url_file:
        with open(args.url_file) as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    else:
        urls = get_default_url_list()

    # Run pipeline
    pipeline = LegalAIDetectionPipeline()
    results = pipeline.run(urls, use_cache=not args.no_cache)

    # Print summary
    print("\n" + "=" * 70)
    print("QUICK SUMMARY")
    print("=" * 70)

    by_risk = defaultdict(int)
    for r in results:
        by_risk[r.risk_level] += 1

    print(f"Total analyzed: {len(results)}")
    print(f"Critical: {by_risk['critical']}, High: {by_risk['high']}, Medium: {by_risk['medium']}, Low: {by_risk['low']}")

    # Highlight any interesting findings
    suspicious = [r for r in results if r.suspiciousness_score > 2]
    if suspicious:
        print(f"\n⚠️  {len(suspicious)} sites with elevated suspiciousness scores:")
        for r in sorted(suspicious, key=lambda x: x.suspiciousness_score, reverse=True)[:5]:
            print(f"   - {r.url[:50]} (score: {r.suspiciousness_score})")


if __name__ == "__main__":
    main()
