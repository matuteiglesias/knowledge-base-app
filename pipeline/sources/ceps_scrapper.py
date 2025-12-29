# requires: pip install requests lxml beautifulsoup4
import time
import requests
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
from lxml import etree

HEADERS = {"User-Agent": "paper-kb-bot/1.0 (+your-email@example.com)"}

def fetch_sitemap_locs(sitemap_url):
    r = requests.get(sitemap_url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    root = etree.fromstring(r.content)
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [el.text for el in root.xpath("//s:loc", namespaces=ns)]
    return locs

def extract_pdf_link_from_page(page_url, session=None):
    s = session or requests.Session()
    r = s.get(page_url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # Try id-based selector used on CEPS pages
    a = soup.find("a", id="ut-download-publication")
    if a and a.get("href"):
        return urljoin(page_url, a["href"])

    # fallback: any anchor with /download/publication/ or pdf= in href
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/download/publication" in href or "pdf=" in href:
            return urljoin(page_url, href)

    # fallback: look for direct .pdf link
    for a in soup.find_all("a", href=True):
        if a["href"].lower().endswith(".pdf"):
            return urljoin(page_url, a["href"])

    return None

def confirm_and_get_filename(pdf_url, page_url=None, session=None):
    s = session or requests.Session()
    # Use HEAD to confirm; some servers don't like HEAD so fallback to GET
    try:
        head = s.head(pdf_url, headers={**HEADERS, "Referer": page_url or ""}, allow_redirects=True, timeout=15)
        head.raise_for_status()
        ctype = head.headers.get("Content-Type","")
        if "pdf" not in ctype.lower():
            # could still be a redirect to PDF; do a GET small
            raise ValueError("not-pdf")
        # try to read filename
        cd = head.headers.get("Content-Disposition")
        if cd and "filename=" in cd:
            # rough parse
            fname = cd.split("filename=")[-1].strip().strip('"\' ')
            return fname
        # fallback: extract from query or path
        parsed = urlparse(head.url)
        q = parse_qs(parsed.query)
        if "pdf" in q:
            return q["pdf"][-1]
        return parsed.path.split("/")[-1] or "download.pdf"
    except Exception:
        # fallback: GET tiny chunk and inspect final URL / headers
        r = s.get(pdf_url, headers={**HEADERS, "Referer": page_url or ""}, stream=True, timeout=30)
        r.raise_for_status()
        ctype = r.headers.get("Content-Type","")
        if "pdf" not in ctype.lower():
            raise RuntimeError(f"URL doesn't look like a PDF (Content-Type: {ctype})")
        cd = r.headers.get("Content-Disposition")
        if cd and "filename=" in cd:
            fname = cd.split("filename=")[-1].strip().strip('"\' ')
        else:
            fname = urlparse(r.url).path.split("/")[-1] or "download.pdf"
        r.close()
        return fname

def download_pdf(pdf_url, out_path, page_url=None, session=None):
    s = session or requests.Session()
    with s.get(pdf_url, headers={**HEADERS, "Referer": page_url or ""}, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(out_path, "wb") as fh:
            for chunk in r.iter_content(1024*32):
                if chunk:
                    fh.write(chunk)


# example: walk a publications sitemap
if __name__ == "__main__":
    SITEMAP = "https://www.ceps.eu/sitemap-post-type-publications.xml"  # adjust if split across chunks
    session = requests.Session()
    pages = []
    try:
        pages = fetch_sitemap_locs(SITEMAP)
    except Exception as e:
        print("Failed to fetch sitemap:", e)

    for i, page in enumerate(pages):
        try:
            print(f"[{i+1}/{len(pages)}] checking {page}")
            pdf_link = extract_pdf_link_from_page(page, session=session)
            if not pdf_link:
                print("  → no pdf link found.")
                continue
            print("  → found candidate:", pdf_link)
            fname = confirm_and_get_filename(pdf_link, page_url=page, session=session)
            print("  → filename:", fname)
            out = "./downloads/" + fname
            download_pdf(pdf_link, out, page_url=page, session=session)
            print("  → saved to", out)
            time.sleep(0.8)  # be polite
        except Exception as e:
            print("  ! error:", e)
            time.sleep(2)
