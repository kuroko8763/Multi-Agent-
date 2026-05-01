"""
Multi-Agent Architecture Review System - CLI Entry Point

Usage:
    # Run demo
    python main.py demo

    # Run on a PR (from JSON file)
    python main.py run --pr-data pr.json --code-dir ./src

    # Run with GitHub integration
    python main.py run --github --pr-number 1234

    # Generate CI configuration
    python main.py generate-ci --output .github/workflows/review.yml

    # Run tests
    python main.py test
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

from pipeline import ArchitectureReviewPipeline, create_sample_pr_data


def cmd_demo(args):
    """Run demo with sample PR data."""
    print("\n🚀 Running Multi-Agent Architecture Review Demo...")
    
    pr_data = create_sample_pr_data()
    pipeline = ArchitectureReviewPipeline()
    result = pipeline.run(pr_data, {})
    
    print("\n" + "=" * 70)
    print("📊 REVIEW SUMMARY")
    print("=" * 70)
    
    review = result.review_summary
    print(f"\nStatus: {review['approval_status'].upper()}")
    print(f"Score: {review['overall_score']}/100")
    print(f"\n{review['summary']}")
    
    if review['must_fix']:
        print("\n🚨 Must Fix:")
        for item in review['must_fix']:
            print(f"  - {item}")
    
    if review['should_fix']:
        print("\n⚠️ Should Fix:")
        for item in review['should_fix']:
            print(f"  - {item}")
    
    print("\n" + "=" * 70)
    print("📄 FULL REPORT")
    print("=" * 70)
    print(pipeline.generate_full_report(result))
    
    # Save outputs
    output_dir = Path('reports')
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    pipeline.export_json(result, f'reports/demo_{timestamp}.json')
    pipeline.export_report(result, f'reports/demo_{timestamp}.md')
    
    print(f"\n✅ Reports saved to reports/demo_{timestamp}.*")


def cmd_run(args):
    """Run pipeline on a specific PR."""
    pr_data_path = Path(args.pr_data)
    
    if not pr_data_path.exists():
        print(f"❌ PR data file not found: {pr_data_path}")
        sys.exit(1)
    
    with open(pr_data_path, 'r', encoding='utf-8') as f:
        pr_data = json.load(f)
    
    # Load code contents if directory specified
    code_contents = {}
    if args.code_dir:
        code_dir = Path(args.code_dir)
        if code_dir.exists():
            for file_change in pr_data.get('files', []):
                file_path = file_change.get('path', '')
                full_path = code_dir / file_path
                if full_path.exists():
                    try:
                        code_contents[file_path] = full_path.read_text(encoding='utf-8')
                    except Exception:
                        pass
    
    pipeline = ArchitectureReviewPipeline()
    result = pipeline.run(pr_data, code_contents)
    
    # Output format
    if args.json:
        pipeline.export_json(result, args.output or 'review_output.json')
        print(f"✅ JSON output saved to {args.output or 'review_output.json'}")
    else:
        print(pipeline.generate_full_report(result))
        
        if args.output:
            pipeline.export_report(result, args.output)
            print(f"✅ Markdown report saved to {args.output}")


def cmd_generate_ci(args):
    """Generate CI configuration for regression tests."""
    from agents.regression_planner import RegressionAdviceAgent
    
    # Create a minimal test plan for CI template
    agent = RegressionAdviceAgent()
    ci_config = """# Generated CI configuration for Architecture Review
name: Architecture Review Pipeline

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Architecture Review
        uses: ./.github/actions/arch-review
        with:
          pr-data: ${{ github.event.pull_request.number }}

  report:
    needs: review
    runs-on: ubuntu-latest
    steps:
      - name: Post Review Comment
        uses: ./.github/actions/post-review-comment
"""
    
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(ci_config, encoding='utf-8')
    
    print(f"✅ CI configuration saved to {args.output}")


def cmd_test(args):
    """Run unit tests."""
    import unittest
    loader = unittest.TestLoader()
    start_dir = 'tests'
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    print("🧪 Running tests...")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    sys.exit(0 if result.wasSuccessful() else 1)


def main():
    parser = argparse.ArgumentParser(
        description='Multi-Agent Architecture Review System',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Demo command
    demo_parser = subparsers.add_parser('demo', help='Run demo with sample data')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run review on a PR')
    run_parser.add_argument('--pr-data', '-p', required=True, help='Path to PR JSON file')
    run_parser.add_argument('--code-dir', '-c', help='Directory containing source code')
    run_parser.add_argument('--output', '-o', help='Output file path')
    run_parser.add_argument('--json', action='store_true', help='Output JSON format')
    
    # Generate CI command
    ci_parser = subparsers.add_parser('generate-ci', help='Generate CI configuration')
    ci_parser.add_argument('--output', '-o', default='.github/workflows/arch-review.yml', help='Output path')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Run unit tests')
    
    args = parser.parse_args()
    
    if args.command == 'demo':
        cmd_demo(args)
    elif args.command == 'run':
        cmd_run(args)
    elif args.command == 'generate-ci':
        cmd_generate_ci(args)
    elif args.command == 'test':
        cmd_test(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()