"""Web tools for the smol agent: search and scrape."""
from smolagents import Tool, DuckDuckGoSearchTool
from bs4 import BeautifulSoup
import requests
from io import BytesIO

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


class WebSearchTool(Tool):
    """Generic web search. Use to find URLs to scrape."""
    name = "web_search"
    description = "Search the web. Returns snippets and URLs. Use this to find relevant pages, then use scrape_page on URLs you need to read."
    inputs = {
        "query": {
            "type": "string",
            "description": "Search query",
        }
    }
    output_type = "string"

    def __init__(self):
        super().__init__()
        self._ddgs = DuckDuckGoSearchTool()

    def forward(self, query: str) -> str:
        try:
            return self._ddgs(query)
        except Exception as e:
            return f"Search failed: {e}"


class ScrapePageTool(Tool):
    """Fetch and extract text from a web page URL."""
    name = "scrape_page"
    description = "Fetch and extract text content from a web page URL. Returns the page title and main text (up to 2000 characters). Use after finding URLs from search."
    inputs = {
        "url": {
            "type": "string",
            "description": "Full HTTP/HTTPS URL of the page to scrape",
        }
    }
    output_type = "string"

    def forward(self, url: str) -> str:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
            resp = requests.get(url, timeout=15, headers=headers)
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            return f"Error: Request timed out for {url}"
        except requests.exceptions.RequestException as e:
            return f"Error fetching page: {e}"
        except Exception as e:
            return f"Unexpected error: {e}"

        content_type = resp.headers.get("Content-Type", "").lower()

        if ("application/pdf" in content_type) or url.lower().endswith(".pdf"):
            if PdfReader is None:
                return "Detected a PDF but pypdf is not installed. Add pypdf to use PDF extraction."
            try:
                reader = PdfReader(BytesIO(resp.content))
                text_chunks = []
                for page in reader.pages:
                    page_text = page.extract_text() or ""
                    if page_text:
                        text_chunks.append(page_text)
                    if sum(len(t) for t in text_chunks) > 6000:
                        break
                text = " ".join(" ".join(text_chunks).split())
                snippet = text[:2000] + ("…" if len(text) > 2000 else "")
                title = "PDF document"
                if reader.metadata and getattr(reader.metadata, "title", None):
                    title = str(reader.metadata.title)
                return f"Title: {title}\n\nURL: {url}\n\nContent:\n{snippet}"
            except Exception as e:
                return f"Error parsing PDF: {e}"

        try:
            soup = BeautifulSoup(resp.text, "html.parser")
            title = "No title"
            if soup.title and soup.title.string:
                title = soup.title.string.strip()
            for tag in soup(["script", "style", "noscript", "iframe", "nav", "footer", "header"]):
                tag.decompose()
            content_tags = soup.find_all(["p", "li", "h1", "h2", "h3", "h4", "article", "section"])
            text = " ".join(tag.get_text(" ", strip=True) for tag in content_tags)
            text = " ".join(text.split())
            snippet = text[:2000] + ("…" if len(text) > 2000 else "")
            return f"Title: {title}\n\nURL: {url}\n\nContent:\n{snippet}"
        except Exception as e:
            return f"Error parsing page: {e}"
