from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import ipaddress
import socket
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.parse import urlencode

import httpx

from pyapi.config import ToolConfig

from .args import int_arg, string_arg

MAX_REDIRECTS = 5
USER_AGENT = "CareerPilotBot/0.1"


def run_fetch_url(config: ToolConfig, arguments: dict[str, Any]) -> str:
    require_internet_tools(config)
    url = normalize_public_url(string_arg(arguments, "url", ""))
    page = fetch_page(config, url)
    return format_page_text(page.url, page.status_code, page.text)


def run_web_search(config: ToolConfig, arguments: dict[str, Any]) -> str:
    require_internet_tools(config)
    query = string_arg(arguments, "query", "").strip()
    if not query:
        raise ValueError("web_search requires a query")
    max_results = int_arg(arguments, "max_results", 5, minimum=1, maximum=10)
    url = f"https://duckduckgo.com/html/?{urlencode({'q': query})}"
    page = fetch_page(config, url)
    results = extract_duckduckgo_results(page.text, max_results)
    if not results:
        results = [(link, link) for link in unique_external_links(page.links, max_results)]
    if not results:
        return format_page_text(page.url, page.status_code, page.text)
    return "\n".join(f"{index}. {title}\n   {url}" for index, (title, url) in enumerate(results, start=1))


def run_read_llms_txt(config: ToolConfig, arguments: dict[str, Any]) -> str:
    require_internet_tools(config)
    base_url = normalize_public_url(string_arg(arguments, "url", ""))
    origin = origin_for_url(base_url)
    results: list[str] = []

    for path in ["/llms.txt", "/llms-full.txt"]:
        url = f"{origin}{path}"
        try:
            page = fetch_page(config, url)
        except Exception as error:
            results.append(f"{url}\nerror: {error}")
            continue
        results.append(format_page_text(page.url, page.status_code, page.text))

    return "\n\n---\n\n".join(results)


def run_crawl_site(config: ToolConfig, arguments: dict[str, Any]) -> str:
    require_internet_tools(config)
    start_url = normalize_public_url(string_arg(arguments, "url", ""))
    max_pages = int_arg(arguments, "max_pages", config.crawl_max_pages, minimum=1, maximum=config.crawl_max_pages)
    origin = origin_for_url(start_url)
    queue = [start_url]
    seen: set[str] = set()
    pages: list[str] = []

    while queue and len(pages) < max_pages:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)

        try:
            page = fetch_page(config, url)
        except Exception as error:
            pages.append(f"{url}\nerror: {error}")
            continue

        pages.append(format_page_text(page.url, page.status_code, page.text))
        for link in page.links:
            if link.startswith(origin) and link not in seen and link not in queue:
                queue.append(link)

    return "\n\n---\n\n".join(pages)


def run_curl(config: ToolConfig, arguments: dict[str, Any]) -> str:
    return run_fetch_url(config, arguments)


def run_wget(config: ToolConfig, arguments: dict[str, Any]) -> str:
    return run_fetch_url(config, arguments)


@dataclass(frozen=True)
class FetchedPage:
    url: str
    status_code: int
    text: str
    links: list[str]


def fetch_page(config: ToolConfig, url: str) -> FetchedPage:
    current_url = normalize_public_url(url)
    response: httpx.Response | None = None
    with httpx.Client(timeout=config.network_timeout_seconds, headers={"User-Agent": USER_AGENT}) as client:
        for _redirect in range(MAX_REDIRECTS + 1):
            response = client.get(current_url, follow_redirects=False)
            if response.status_code not in {301, 302, 303, 307, 308}:
                break

            location = response.headers.get("location")
            if not location:
                break
            current_url = normalize_public_url(urljoin(current_url, location))
        else:
            raise ValueError("too many redirects")

    assert response is not None
    final_url = normalize_public_url(str(response.url))
    raw = response.content[: config.max_network_bytes]
    content_type = response.headers.get("content-type", "")
    decoded = raw.decode(response.encoding or "utf-8", errors="replace")
    if "html" in content_type.lower() or looks_like_html(decoded):
        parser = HtmlTextParser(final_url)
        parser.feed(decoded)
        text = parser.text()
        links = parser.links
    else:
        text = decoded
        links = []

    return FetchedPage(final_url, response.status_code, text, links)


def require_internet_tools(config: ToolConfig) -> None:
    if not config.internet_enabled:
        raise ValueError("internet tools are disabled")


def normalize_public_url(raw_url: str) -> str:
    value = raw_url.strip()
    if not value:
        raise ValueError("url is required")
    if "://" not in value:
        value = f"https://{value}"

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("only http and https URLs are supported")
    if not parsed.hostname:
        raise ValueError("url must include a hostname")
    if parsed.username or parsed.password:
        raise ValueError("URLs with credentials are not allowed")

    assert_public_hostname(parsed.hostname)
    clean = parsed._replace(fragment="")
    return urlunparse(clean)


def assert_public_hostname(hostname: str) -> None:
    try:
        addresses = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as error:
        raise ValueError(f"could not resolve host: {hostname}") from error

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError("private, local, or reserved network addresses are not allowed")


def origin_for_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


def looks_like_html(value: str) -> bool:
    lowered = value[:500].lower()
    return "<html" in lowered or "<!doctype html" in lowered or "<body" in lowered


def format_page_text(url: str, status_code: int, text: str) -> str:
    return f"URL: {url}\nStatus: {status_code}\n\n{text.strip() or '(no readable text)'}"


def extract_duckduckgo_results(text: str, max_results: int) -> list[tuple[str, str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    results: list[tuple[str, str]] = []
    for index, line in enumerate(lines):
        if line.startswith("http://") or line.startswith("https://"):
            title = lines[index - 1] if index > 0 else line
            if "duckduckgo.com" in line:
                continue
            results.append((title, line))
            if len(results) >= max_results:
                break
    return results


def unique_external_links(links: list[str], max_results: int) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for link in links:
        if "duckduckgo.com" in link or link in seen:
            continue
        seen.add(link)
        results.append(link)
        if len(results) >= max_results:
            break
    return results


class HtmlTextParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.parts: list[str] = []
        self.links: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                try:
                    self.links.append(normalize_public_url(urljoin(self.base_url, href)))
                except ValueError:
                    pass
        if tag in {"p", "br", "div", "section", "article", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.skip_depth > 0:
            self.skip_depth -= 1
        if tag in {"p", "div", "section", "article", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        text = " ".join(data.split())
        if text:
            self.parts.append(text)

    def text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self.parts).splitlines()]
        return "\n".join(line for line in lines if line)
