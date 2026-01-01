import json
import os
import sys
import time
from pathlib import Path

import click
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

URL = "https://www.pastpuzzle.de/#/login"


def _extract_access_token(page) -> str | None:
    script = """
    () => {
      const keys = Object.keys(localStorage).concat(Object.keys(sessionStorage));
      for (const key of keys) {
        if (!key.includes("auth-token")) continue;
        const raw = localStorage.getItem(key) || sessionStorage.getItem(key);
        if (!raw) continue;
        try {
          const parsed = JSON.parse(raw);
          if (parsed && parsed.access_token) return parsed.access_token;
        } catch (err) {}
      }
      return null;
    }
    """
    return page.evaluate(script)


def _extract_token_from_requests(page) -> str | None:
    try:
        requests = page.context.request._request_storage._requests  # type: ignore[attr-defined]
    except Exception:
        return None
    for request in reversed(requests):
        headers = request.get("headers", {})
        auth = headers.get("authorization") or headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            return auth.split(" ", 1)[1]
    return None


def _extract_token_from_storage_dump(page) -> str | None:
    try:
        storage = page.context.storage_state()
    except Exception:
        return None
    for origin in storage.get("origins", []):
        for item in origin.get("localStorage", []):
            if "auth-token" in item.get("name", ""):
                try:
                    parsed = json.loads(item.get("value", ""))
                    if parsed and parsed.get("access_token"):
                        return parsed["access_token"]
                except Exception:
                    continue
    return None


@click.command()
@click.option(
    "--write-env",
    "write_env",
    is_flag=True,
    help="Persist the access token into .env as PASTPUZZLE_AUTHORIZATION.",
)
def main(write_env: bool = False) -> None:
    load_dotenv()
    username = os.environ["PASTPUZZLE_USER"]
    password = os.environ["PASTPUZZLE_PASS"]

    deadline = time.time() + 150
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(URL, wait_until="domcontentloaded")
        _dismiss_cookie_banner(page, deadline)

        username_selectors = [
            'input[name="username"]',
            'input[name="email"]',
            'input[type="email"]',
            'input[aria-label="E-Mail"]',
            'input[aria-label="Email"]',
            'input[autocomplete="username"]',
            'input[autocomplete="email"]',
            'input.q-field__native[aria-label="E-Mail"]',
        ]
        password_selectors = [
            'input[name="password"]',
            'input[type="password"]',
            'input[aria-label="Passwort"]',
            'input[aria-label="Password"]',
            'input[autocomplete="current-password"]',
            'input.q-field__native[aria-label="Password"]',
        ]

        try:
            _wait_for_login_form(page, deadline)
        except TimeoutError:
            _dump_login_debug(page)
            _dump_selector_debug(page, username_selectors + password_selectors)
            raise

        _ensure_deadline(deadline)
        username_locator = _find_locator(page, username_selectors, deadline)
        password_locator = _find_locator(page, password_selectors, deadline)
        if not username_locator or not password_locator:
            fallback = _find_form_locators(page)
            if fallback:
                username_locator, password_locator = fallback
        if not username_locator or not password_locator:
            _dump_login_debug(page)
            _dump_selector_debug(page, username_selectors + password_selectors)
            print("Unable to locate login form fields.", file=sys.stderr)
            sys.exit(1)

        username_locator.fill(username)
        password_locator.fill(password)
        _ensure_deadline(deadline)
        page.click('button[type="submit"]')

        # Wait for post-login navigation/app state
        _ensure_deadline(deadline)
        page.wait_for_load_state("networkidle", timeout=_remaining_timeout_ms(deadline))
        _ensure_deadline(deadline)
        page.wait_for_timeout(3000)

        _ensure_deadline(deadline)
        access_token = _extract_access_token(page)
        if not access_token:
            access_token = _extract_token_from_requests(page)
        if not access_token:
            access_token = _extract_token_from_storage_dump(page)
        if not access_token:
            _dump_login_debug(page)
            print("Unable to locate access_token in storage.", file=sys.stderr)
            sys.exit(1)
        if write_env:
            _persist_token_to_env(access_token)
        print(access_token)

        # Persist session for later tests
        context.storage_state(path="pastpuzzle.storage_state.json")

        browser.close()


def _find_locator(page, selectors: list[str], deadline: float):
    for selector in selectors:
        for frame in _iter_frames(page):
            try:
                _ensure_deadline(deadline)
                locator = frame.locator(selector).first
                locator.wait_for(
                    state="attached", timeout=min(5000, _remaining_timeout_ms(deadline))
                )
                return locator
            except Exception:
                continue
    return None


def _persist_token_to_env(token: str) -> None:
    env_path = Path(".env")
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    updated = False
    for index, line in enumerate(lines):
        if line.startswith("PASTPUZZLE_AUTHORIZATION="):
            lines[index] = f"PASTPUZZLE_AUTHORIZATION={token}"
            updated = True
            break
    if not updated:
        lines.append(f"PASTPUZZLE_AUTHORIZATION={token}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _iter_frames(page) -> list[object]:
    frames = [page]
    try:
        frames.extend(page.frames)
    except Exception:
        pass
    return frames


def _dump_login_debug(page) -> None:
    debug_enabled = os.getenv("PASTPUZZLE_LOGIN_DEBUG", "").lower() in {"1", "true", "yes"}
    if not debug_enabled:
        return
    os.makedirs("data", exist_ok=True)
    try:
        page.screenshot(path="data/login.png", full_page=True)
    except Exception:
        pass
    try:
        html = page.content()
        with open("data/login.html", "w", encoding="utf-8") as handle:
            handle.write(html)
    except Exception:
        pass
    try:
        with open("data/login_frames.txt", "w", encoding="utf-8") as handle:
            for frame in _iter_frames(page):
                try:
                    handle.write(f"{frame.url}\n")
                except Exception:
                    handle.write("<unknown>\n")
    except Exception:
        pass


def _dump_selector_debug(page, selectors: list[str]) -> None:
    debug_enabled = os.getenv("PASTPUZZLE_LOGIN_DEBUG", "").lower() in {"1", "true", "yes"}
    if not debug_enabled:
        return
    os.makedirs("data", exist_ok=True)
    try:
        with open("data/login_selectors.txt", "w", encoding="utf-8") as handle:
            for selector in selectors:
                counts = []
                for frame in _iter_frames(page):
                    try:
                        counts.append(frame.locator(selector).count())
                    except Exception:
                        counts.append(-1)
                handle.write(f"{selector} -> {counts}\n")
    except Exception:
        pass


def _find_form_locators(page) -> tuple[object, object] | None:
    for frame in _iter_frames(page):
        try:
            password_locator = frame.locator("form input[type='password']").first
            if password_locator.count() == 0:
                continue
            username_locator = frame.locator("form input[type='email']").first
            if username_locator.count() == 0:
                username_locator = frame.locator("form input[type='text']").first
            if username_locator.count() == 0:
                continue
            return username_locator, password_locator
        except Exception:
            continue
    return None


def _wait_for_login_form(page, deadline: float) -> None:
    selectors = [
        'form input[aria-label="E-Mail"]',
        'form input[aria-label="Password"]',
        "form input[type='password']",
        'input[aria-label="E-Mail"]',
        'input[aria-label="Password"]',
    ]
    for selector in selectors:
        try:
            _ensure_deadline(deadline)
            page.wait_for_selector(
                selector,
                timeout=min(10000, _remaining_timeout_ms(deadline)),
                state="attached",
            )
            return
        except Exception:
            continue
    raise TimeoutError("Login form did not appear before timeout.")


def _dismiss_cookie_banner(page, deadline: float) -> None:
    buttons = [
        'button:has-text("Accept all")',
        'button:has-text("Decline optional cookies")',
        'button:has-text("Alle akzeptieren")',
        'button:has-text("Nur essenzielle Cookies")',
        'button:has-text("Ablehnen")',
    ]
    for selector in buttons:
        try:
            _ensure_deadline(deadline)
            page.click(selector, timeout=min(3000, _remaining_timeout_ms(deadline)))
            return
        except Exception:
            continue


def _ensure_deadline(deadline: float) -> None:
    if time.time() > deadline:
        raise TimeoutError("Login flow exceeded the 2.5 minute timeout.")


def _remaining_timeout_ms(deadline: float) -> int:
    remaining = int((deadline - time.time()) * 1000)
    return max(1000, remaining)

if __name__ == "__main__":
    main()
