#!/usr/bin/env python3
"""PressAI Video SEO Engine — Unified CLI entry point.

Usage:
  python -m cli.main fetch --video <URL>         # Fetch YouTube data
  python -m cli.main fetch --channel <ID>        # List channel videos
  python -m cli.main match                       # Match WP posts to YouTube IDs
  python -m cli.main sitemap --matches <JSON>    # Generate video sitemap
  python -m cli.main generate --video <ID>       # Generate SEO schema [Phase 2]
  python -m cli.main inject --post-id <ID>       # Inject schema to WordPress [Phase 2]

For full options on any subcommand:
  python -m cli.main <command> --help
"""
import argparse
import sys


def cmd_fetch(args):
    """Fetch YouTube transcript + metadata."""
    from core.fetcher import main as fetcher_main
    sys.argv = [sys.argv[0]] + args.rest
    fetcher_main()


def cmd_match(args):
    """Match WordPress posts to YouTube IDs."""
    from core.matcher import main as matcher_main
    matcher_main()


def cmd_sitemap(args):
    """Generate video sitemap XML."""
    from core.sitemap import main as sitemap_main
    sys.argv = [sys.argv[0]] + args.rest
    sitemap_main()


def cmd_generate(args):
    """Generate SEO schema via Gemini AI (Phase 2)."""
    print("ERROR: generator not yet implemented. See DISPATCH-VSE-MIGRATE-GENERATOR.")
    sys.exit(1)


def cmd_inject(args):
    """Inject schema to WordPress post (Phase 2)."""
    print("ERROR: injector not yet implemented. See DISPATCH-VSE-MIGRATE-INJECTOR.")
    sys.exit(1)


def main():
    """Main CLI dispatcher."""
    parser = argparse.ArgumentParser(
        prog="vse",
        description="PressAI Video SEO Engine — automated video content optimization",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # fetch
    fetch_p = subparsers.add_parser("fetch", help="Fetch YouTube data")
    fetch_p.add_argument("rest", nargs=argparse.REMAINDER)
    fetch_p.set_defaults(func=cmd_fetch)

    # match
    match_p = subparsers.add_parser("match", help="Match WP posts to YouTube IDs")
    match_p.set_defaults(func=cmd_match)

    # sitemap
    sitemap_p = subparsers.add_parser("sitemap", help="Generate video sitemap")
    sitemap_p.add_argument("rest", nargs=argparse.REMAINDER)
    sitemap_p.set_defaults(func=cmd_sitemap)

    # generate
    gen_p = subparsers.add_parser("generate", help="Generate SEO schema [Phase 2]")
    gen_p.set_defaults(func=cmd_generate)

    # inject
    inj_p = subparsers.add_parser("inject", help="Inject schema to WordPress [Phase 2]")
    inj_p.set_defaults(func=cmd_inject)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
