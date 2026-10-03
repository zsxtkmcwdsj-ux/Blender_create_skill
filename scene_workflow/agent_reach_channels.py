from __future__ import annotations

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.images: list[str] = []

    def handle_data(self, data: str) -> None:
        text = re.sub(r"\s+", " ", data).strip()
        if text:
            self.parts.append(text)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "img":
            return
        values = dict(attrs)
        for key in ("src", "data-src", "data-original"):
            if values.get(key):
                self.images.append(str(values[key]))


class _BingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._in_item = False
        self._in_title = False
        self._in_snippet = False
        self._current: dict[str, str] = {}
        self._title: list[str] = []
        self._snippet: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = str(values.get("class") or "")
        if tag == "li" and "b_algo" in classes:
            self._in_item = True
            self._current = {}
            self._title = []
            self._snippet = []
        elif self._in_item and tag == "a" and not self._current.get("url"):
            href = str(values.get("href") or "")
            if href.startswith("http"):
                self._current["url"] = href
                self._in_title = True
        elif self._in_item and tag == "p":
            self._in_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._in_title = False
        elif tag == "p":
            self._in_snippet = False
        elif tag == "li" and self._in_item:
            title = re.sub(r"\s+", " ", " ".join(self._title)).strip()
            snippet = re.sub(r"\s+", " ", " ".join(self._snippet)).strip()
            if title and self._current.get("url"):
                self.results.append({"title": title, "url": self._current["url"], "snippet": snippet[:1600]})
            self._in_item = False

    def handle_data(self, data: str) -> None:
        text = re.sub(r"\s+", " ", data).strip()
        if not text:
            return
        if self._in_title:
            self._title.append(text)
        elif self._in_snippet:
            self._snippet.append(text)


def _mcporter() -> str:
    return shutil.which("mcporter") or shutil.which("mcporter.cmd") or shutil.which("mcporter.ps1") or ""


def _call_mcporter(tool: str, args: list[str], timeout: int = 90) -> dict[str, Any]:
    command = _mcporter()
    if not command:
        raise FileNotFoundError("mcporter is not installed or not on PATH")
    completed = subprocess.run(
        [command, "call", tool, *args, "--output", "json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=True,
    )
    payload = json.loads(completed.stdout)
    if payload.get("isError"):
        raise RuntimeError(json.dumps(payload, ensure_ascii=False))
    return payload


def _parse_exa(query: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for block in payload.get("content", []):
        if block.get("type") != "text":
            continue
        text = str(block.get("text") or "")
        for chunk in [item.strip() for item in text.split("\n\n---\n\n") if item.strip()]:
            url_match = re.search(r"^URL:\s*(\S+)$", chunk, re.MULTILINE)
            if not url_match:
                continue
            title_match = re.search(r"^Title:\s*(.+)$", chunk, re.MULTILINE)
            highlight_match = re.search(r"Highlights:\s*(.+)", chunk, re.DOTALL)
            results.append(
                {
                    "channel": "agent_reach_exa",
                    "query": query,
                    "title": title_match.group(1).strip() if title_match else "",
                    "url": url_match.group(1).strip(),
                    "snippet": (highlight_match.group(1).strip() if highlight_match else "")[:2400],
                }
            )
    return results


def search_exa(queries: list[str], max_results: int = 6) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    for query in queries:
        try:
            results.extend(_parse_exa(query, _call_mcporter("exa.web_search_exa", [f"query={query}", f"numResults={max_results}"])))
        except Exception as exc:
            errors.append(f"{query}: {exc}")
    unique: dict[str, dict[str, Any]] = {}
    for item in results:
        if item.get("url"):
            unique.setdefault(str(item["url"]), item)
    return {"status": "passed" if unique else "error", "results": list(unique.values()), "errors": errors}


def fetch_exa(urls: list[str], max_characters: int = 8000) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    for url in urls:
        try:
            payload = _call_mcporter("exa.web_fetch_exa", [f"urls={url}", f"maxCharacters={max_characters}"])
            text = "\n\n".join(str(item.get("text") or "") for item in payload.get("content", []) if item.get("type") == "text")
            pages.append({"channel": "agent_reach_exa_fetch", "url": url, "status": "passed", "text": text[:max_characters]})
        except Exception as exc:
            pages.append({"channel": "agent_reach_exa_fetch", "url": url, "status": "error", "error": str(exc)})
    return pages


def _xhs() -> str:
    return shutil.which("xhs") or shutil.which("xhs.cmd") or ""


def search_xhs(queries: list[str], limit: int = 6) -> dict[str, Any]:
    command = _xhs()
    if not command:
        return {"status": "skipped", "results": [], "errors": ["xhs is not installed or not on PATH"]}
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    for query in queries:
        try:
            completed = subprocess.run([command, "search", query, "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90, check=True)
            payload = json.loads(completed.stdout)
            items = ((payload.get("data") or {}).get("items") or [])[:limit]
            for item in items:
                card = item.get("note_card") or {}
                title = str(card.get("display_title") or card.get("title") or "").strip()
                note_id = str(item.get("id") or card.get("note_id") or "").strip()
                token = str(item.get("xsec_token") or "").strip()
                if not title or not note_id:
                    continue
                url = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={quote(token, safe='')}" if token else f"https://www.xiaohongshu.com/explore/{note_id}"
                results.append({"channel": "agent_reach_xiaohongshu", "query": query, "title": title, "url": url, "snippet": str(card.get("desc") or "")[:1600]})
        except Exception as exc:
            errors.append(f"{query}: {exc}")
    return {"status": "passed" if results else ("error" if errors else "empty"), "results": results, "errors": errors}


def search_bing(queries: list[str], max_results: int = 5) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    for query in queries:
        try:
            request = Request(f"https://www.bing.com/search?q={quote(query)}", headers={"User-Agent": "Mozilla/5.0 ResearchToBlender/1.0"})
            with urlopen(request, timeout=25) as response:
                raw = response.read(500_000)
            parser = _BingParser()
            parser.feed(raw.decode("utf-8", errors="replace"))
            for item in parser.results[:max_results]:
                results.append({"channel": "bing_web_search", "query": query, **item})
        except Exception as exc:
            errors.append(f"{query}: {exc}")
    unique: dict[str, dict[str, Any]] = {}
    for item in results:
        if item.get("url"):
            unique.setdefault(str(item["url"]), item)
    return {"status": "passed" if unique else "error", "results": list(unique.values()), "errors": errors}


def fetch_page(url: str, timeout: int = 25) -> dict[str, Any]:
    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 ResearchToBlender/1.0"})
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(1_000_000)
            content_type = response.headers.get("Content-Type", "")
        parser = _TextParser()
        parser.feed(raw.decode("utf-8", errors="replace"))
        return {"url": url, "status": "passed", "reader": "urllib_html", "content_type": content_type, "text": " ".join(parser.parts)[:8000], "images": parser.images[:20]}
    except Exception as exc:
        direct_error = str(exc)
    jina_error = ""
    for _ in range(2):
        try:
            request = Request(f"https://r.jina.ai/{url}", headers={"User-Agent": "Mozilla/5.0 ResearchToBlender/1.0", "Accept": "text/plain"})
            with urlopen(request, timeout=timeout) as response:
                raw = response.read(1_000_000)
                content_type = response.headers.get("Content-Type", "")
            return {"url": url, "status": "passed", "reader": "jina_reader", "content_type": content_type, "text": raw.decode("utf-8", errors="replace")[:8000], "images": []}
        except Exception as exc:
            jina_error = str(exc)
    return {"url": url, "status": "error", "error": f"direct: {direct_error}; jina: {jina_error}", "text": "", "images": []}


def _baike_terms(question: str) -> list[str]:
    cleaned = question
    for word in (
        "\u751f\u6210",
        "\u521b\u5efa",
        "\u5236\u4f5c",
        "\u4e00\u4e2a",
        "\u7684",
        "\u73b0\u5b9e\u98ce\u683c",
        "\u5199\u5b9e\u98ce\u683c",
        "\u5916\u89c2",
        "\u5ba4\u5185",
        "\u91cd\u70b9\u4f53\u73b0",
        "\u91cd\u70b9\u8868\u73b0",
        "\u91cd\u70b9\u8981\u6c42",
        "\u5efa\u7b51\u7eb9\u7406",
        "\u7eb9\u7406",
        "\u6750\u8d28",
        "\u7cbe\u7ec6\u5316",
        "\u9897\u7c92\u5ea6",
        "\u7ec6\u8282",
        "\u7b49",
        "lod",
        "LOD",
    ):
        cleaned = cleaned.replace(word, " ")
    cleaned = re.sub(r"[\s,，。；;:：、（）()]+", " ", cleaned).strip()
    suffixes = "\u57ce\u697c|\u89d2\u697c|\u535a\u7269\u9986|\u56fe\u4e66\u9986|\u4f53\u80b2\u9986|\u5927\u53a6|\u5927\u697c|\u5bab|\u6bbf|\u9601|\u5854|\u6865|\u697c|\u9986"
    terms = re.findall(rf"[\u4e00-\u9fffA-Za-z0-9]{{2,}}(?:{suffixes})", cleaned)
    compact = re.sub(r"\s+", "", cleaned)
    candidates = [*terms]
    if compact:
        candidates.extend([compact[:12], compact])
    return list(dict.fromkeys(item for item in candidates if len(item) >= 2))[:5]

def collect_agent_reach(question: str, *, max_results: int = 5) -> dict[str, Any]:
    base = re.sub(r"\s+", " ", question).strip()
    exa = search_exa([base, f"{base} official", f"{base} interior", f"{base} floor plan"], max_results=max_results)
    bing = search_bing([base, f"{base} architecture details", f"{base} roof facade materials"], max_results=max_results)
    exa_pages = fetch_exa([item["url"] for item in exa["results"][:8]])
    web_pages = [fetch_page(item["url"]) for item in bing["results"][:8]]
    xhs = search_xhs([base, f"{base} interior"], limit=max_results)
    baike_pages = [{"channel": "agent_reach_baidu_baike", "term": term, **fetch_page(f"https://baike.baidu.com/item/{quote(term)}")} for term in _baike_terms(question)]
    sources = [*exa["results"], *bing["results"], *xhs["results"]]
    pages = [*exa_pages, *web_pages, *baike_pages]
    usable_pages = [item for item in pages if item.get("status") == "passed" and item.get("text")]
    return {
        "status": "passed" if sources or usable_pages else "partial",
        "question": question,
        "channels": {"exa": exa, "bing": bing, "exa_pages": exa_pages, "web_pages": web_pages, "xiaohongshu": xhs, "baidu_baike": baike_pages},
        "sources": sources,
        "pages": pages,
    }
