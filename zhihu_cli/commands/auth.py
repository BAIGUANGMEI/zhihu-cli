"""Authentication commands: login, logout, status, whoami."""

from __future__ import annotations

import json
import sys

import click
from click.core import ParameterSource

from ..auth import (
    clear_cookies,
    cookie_str_to_dict,
    get_cookie_string,
    get_saved_cookie_string,
    qrcode_login,
    save_cookies,
)
from ..config import REQUIRED_COOKIES
from ..display import (
    console,
    format_count,
    format_stats_line,
    make_kv_table,
    print_error,
    print_hint,
    print_info,
    print_success,
    print_warning,
    strip_html,
)


def _verify_cookies(cookie_dict: dict) -> bool | None:
    """Validate cookies by fetching user info.

    Returns True/False/None for valid/invalid/unknown.
    """
    from ..client import ZhihuClient

    try:
        with ZhihuClient(cookie_dict) as client:
            info = client.get_self_info()
    except Exception:
        return None

    if not isinstance(info, dict) or not info:
        return None

    name = info.get("name", "")
    uid = info.get("id", "")
    if name and name != "知乎用户":
        return True
    if uid:
        return True
    return False


@click.command()
@click.option("--qrcode", is_flag=True, help="Use QR code to login")
@click.option("--cookie", "cookie_str", default=None, help="Provide cookie string directly")
@click.pass_context
def login(ctx: click.Context, qrcode: bool, cookie_str: str | None):
    """Authenticate with Zhihu.

    \b
    Methods:
      --qrcode   Scan QR code with Zhihu app (recommended)
      --cookie   Paste cookie string (must contain z_c0)
    """
    cookie_provided = (
        ctx.get_parameter_source("cookie_str") == ParameterSource.COMMANDLINE
    )

    if cookie_provided:
        parsed = cookie_str_to_dict(cookie_str or "")
        if not REQUIRED_COOKIES.issubset(parsed.keys()):
            print_error("Invalid cookie — must contain [bold]z_c0[/bold]")
            sys.exit(1)
        save_cookies("; ".join(f"{k}={v}" for k, v in parsed.items()))
        print_success("Cookie saved")
        return

    if not qrcode:
        cookie = get_cookie_string()
        if cookie:
            cookie_dict = cookie_str_to_dict(cookie)
            verify_result = _verify_cookies(cookie_dict)
            if verify_result is True:
                print_success("Already authenticated (saved cookie)")
                return
            elif verify_result is False:
                print_warning("Saved cookie expired or invalid")
                clear_cookies()
            else:
                print_warning("Cannot verify cookie — keeping existing session")
                return

    # QR code login
    print_info("Launching QR code login…")
    try:
        cookie = qrcode_login()
        cookie_dict = cookie_str_to_dict(cookie)
        verify_result = _verify_cookies(cookie_dict)
        if verify_result is False:
            clear_cookies()
            print_error("Login completed but session is invalid — please retry")
            sys.exit(1)
        print_success("Login successful — cookie saved")
    except Exception as e:
        print_error(f"Login failed: {e}")
        sys.exit(1)


@click.command()
def logout():
    """Clear saved credentials."""
    removed = clear_cookies()
    if removed:
        print_success(f"Logged out — removed: {', '.join(removed)}")
    else:
        print_warning("No saved credentials to clear")


@click.command()
def status():
    """Check authentication status (offline)."""
    cookie = get_saved_cookie_string()
    if not cookie:
        print_error("Not authenticated")
        print_hint("Run [bold]zhihu login --qrcode[/bold] or [bold]zhihu login --cookie[/bold]")
        sys.exit(1)

    print_success("Authenticated [dim](saved cookie)[/dim]")
    print_hint("Run [bold]zhihu whoami[/bold] to view profile")


@click.command()
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def whoami(as_json: bool):
    """Show current user profile."""
    from ..client import ZhihuClient

    cookie = get_cookie_string()
    if not cookie:
        print_error("Not authenticated — run [bold]zhihu login[/bold]")
        sys.exit(1)

    try:
        with ZhihuClient(cookie_str_to_dict(cookie)) as client:
            info = client.get_self_info()

            if as_json:
                click.echo(json.dumps(info, indent=2, ensure_ascii=False))
                return

            name = info.get("name", "Unknown")
            headline = info.get("headline", "")
            url_token = info.get("url_token", "")
            gender = info.get("gender", -1)
            description = strip_html(info.get("description", ""))

            table = make_kv_table(f"  {name}  ")

            if url_token:
                table.add_row("ID", f"@{url_token}")
            if headline:
                table.add_row("Headline", headline)
            if description:
                table.add_row("Bio", description[:80])

            gender_label = {0: "Male", 1: "Female", -1: "—"}.get(gender, str(gender))
            table.add_row("Gender", gender_label)

            table.add_row("Answers", format_count(info.get("answer_count", 0)))
            table.add_row("Articles", format_count(info.get("articles_count", 0)))
            table.add_row("Followers", format_count(info.get("follower_count", 0)))
            table.add_row("Following", format_count(info.get("following_count", 0)))
            table.add_row("Upvotes", format_count(info.get("voteup_count", 0)))
            table.add_row("Thanks", format_count(info.get("thanked_count", 0)))

            console.print()
            console.print(table)
            console.print()

    except SystemExit:
        raise
    except Exception as e:
        print_error(f"Failed to fetch profile: {e}")
        sys.exit(1)
