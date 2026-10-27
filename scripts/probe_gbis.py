"""Read-only public-source capability check. No authentication or private endpoints."""
import re
from urllib.parse import urljoin, urlparse
import httpx

base='https://m.gbis.go.kr'
with httpx.Client(timeout=25, follow_redirects=False) as client:
    page=client.get(base+'/search')
    print('PUBLIC_PAGE',page.status_code,'bytes',len(page.content))
    page.raise_for_status()
    scripts=re.findall(r'<script[^>]+src=["\']([^"\']+)',page.text)
    print('SCRIPT_COUNT',len(scripts))
    urls=[]
    for src in scripts:
        url=urljoin(base,src)
        if urlparse(url).hostname != 'm.gbis.go.kr':continue
        urls.append(url)
    texts=[]
    for url in urls[:8]:
        response=client.get(url)
        print('SCRIPT',urlparse(url).path,response.status_code,'bytes',len(response.content))
        if response.status_code==200 and len(response.content)<4000000:texts.append(response.text)
    strings=set()
    for source in texts:
        for token in re.findall(r'["\']([^"\'\n]{4,180})["\']',source):
            lower=token.lower()
            if (token.startswith('/') or token.startswith('https://m.gbis.go.kr')) and any(word in lower for word in ('route','bus','station','api/','search')):
                if not any(word in lower for word in ('key','token','secret','authorization')):strings.add(token)
    for token in sorted(strings)[:100]:print('PUBLIC_ASSET_PATH',token)
