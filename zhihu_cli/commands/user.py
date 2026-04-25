"""User profile commands: user, user-answers, user-articles, followers, following."""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager

import click

from ..auth import cookie_str_to_dict, get_cookie_string
from ..display import (
    console,
    format_count,
    format_stats_line,
    make_kv_table,
    make_table,
    print_error,
    print_info,
    strip_html,
)


@contextmanager
def _get_client():
    from ..client import ZhihuClient

    cookie = get_cookie_string()
    if not cookie:
        print_error("Not authenticated — run [bold]zhihu login[/bold]")
        sys.exit(1)
    with ZhihuClient(cookie_str_to_dict(cookie)) as client:
        yield client


@click.command()
@click.argument("url_token")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def user(url_token: str, as_json: bool):
    """View a user's profile by url_token."""
    with _get_client() as client:
        try:
            info = client.get_user_profile(url_token)
        except Exception as e:
            print_error(f"Failed to fetch user: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(info, indent=2, ensure_ascii=False))
            return

        name = info.get("name", "Unknown")
        headline = info.get("headline", "")
        desc = strip_html(info.get("description", ""))

        table = make_kv_table(f"  @{url_token}  ")
        table.add_row("Name", name)
        if headline:
            table.add_row("Headline", headline)
        if desc:
            table.add_row("Bio", desc)

        table.add_row("Answers", format_count(info.get("answer_count", 0)))
        table.add_row("Articles", format_count(info.get("articles_count", 0)))
        table.add_row("Followers", format_count(info.get("follower_count", 0)))
        table.add_row("Following", format_count(info.get("following_count", 0)))
        table.add_row("Upvotes", format_count(info.get("voteup_count", 0)))

        console.print()
        console.print(table)
        console.print()


@click.command("user-answers")
@click.argument("url_token")
@click.option("-l", "--limit", default=10, help="Max results", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def user_answers(url_token: str, limit: int, as_json: bool):
    """List answers by a user."""
    with _get_client() as client:
        try:
            results = client.get_user_answers(url_token, limit=limit)
            data = results.get("data", [])
        except Exception as e:
            print_error(f"Failed to fetch answers: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
            return

        if not data:
            print_info("No answers found")
            return

        table = make_table(f" Answers by @{url_token} ")
        table.add_column("#", style="dim", width=4)
        table.add_column("Question", ratio=1)
        table.add_column("Upvotes", width=10, justify="right")

        for i, ans in enumerate(data, 1):
            q_title = strip_html(ans.get("question", {}).get("title", "—"))
            upvotes = format_count(ans.get("voteup_count", 0))
            table.add_row(str(i), q_title, f"[bold]{upvotes}[/bold]")

        console.print()
        console.print(table)
        console.print()


@click.command("user-articles")
@click.argument("url_token")
@click.option("-l", "--limit", default=10, help="Max results", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def user_articles(url_token: str, limit: int, as_json: bool):
    """List articles by a user."""
    with _get_client() as client:
        try:
            results = client.get_user_articles(url_token, limit=limit)
            data = results.get("data", [])
        except Exception as e:
            print_error(f"Failed to fetch articles: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
            return

        if not data:
            print_info("No articles found")
            return

        table = make_table(f" Articles by @{url_token} ")
        table.add_column("#", style="dim", width=4)
        table.add_column("Title", ratio=1)
        table.add_column("Upvotes", width=10, justify="right")

        for i, art in enumerate(data, 1):
            title = strip_html(art.get("title", "—"))
            upvotes = format_count(art.get("voteup_count", 0))
            table.add_row(str(i), title, f"[bold]{upvotes}[/bold]")

        console.print()
        console.print(table)
        console.print()


@click.command()
@click.argument("url_token")
@click.option("-l", "--limit", default=10, help="Max results", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def followers(url_token: str, limit: int, as_json: bool):
    """List a user's followers."""
    with _get_client() as client:
        try:
            results = client.get_followers(url_token, limit=limit)
            data = results.get("data", [])
        except Exception as e:
            print_error(f"Failed to fetch followers: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
            return

        if not data:
            print_info("No followers found")
            return

        table = make_table(f" Followers of @{url_token} ")
        table.add_column("#", style="dim", width=4)
        table.add_column("Name", width=16)
        table.add_column("Headline", ratio=1)
        table.add_column("Followers", width=10, justify="right")

        for i, u in enumerate(data, 1):
            name = u.get("name", "—")
            headline = u.get("headline", "")
            cnt = format_count(u.get("follower_count", 0))
            table.add_row(str(i), name, headline, cnt)

        console.print()
        console.print(table)
        console.print()


@click.command()
@click.argument("url_token")
@click.option("-l", "--limit", default=10, help="Max results", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def following(url_token: str, limit: int, as_json: bool):
    """List who a user follows."""
    with _get_client() as client:
        try:
            results = client.get_following(url_token, limit=limit)
            data = results.get("data", [])
        except Exception as e:
            print_error(f"Failed to fetch following: {e}")
            sys.exit(1)

        if as_json:
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
            return

        if not data:
            print_info("No following found")
            return

        table = make_table(f" @{url_token} Follows ")
        table.add_column("#", style="dim", width=4)
        table.add_column("Name", width=16)
        table.add_column("Headline", ratio=1)
        table.add_column("Followers", width=10, justify="right")

        for i, u in enumerate(data, 1):
            name = u.get("name", "—")
            headline = u.get("headline", "")
            cnt = format_count(u.get("follower_count", 0))
            table.add_row(str(i), name, headline, cnt)

        console.print()
        console.print(table)
        console.print()
