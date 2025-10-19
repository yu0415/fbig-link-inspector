from bs4 import BeautifulSoup

def parse_basic_meta(html: str) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    
    def get_meta(prop: str):
        tag = soup.find('meta', attrs={'property': prop})
        return tag.get('content') if tag else None
    
    return {
        'og:title': get_meta('og:title'),
        'og:description': get_meta('og:description'),
        'og:image': get_meta('og:image'),
        'og:url': get_meta('og:url'),
        'og:site_name': get_meta('og:site_name'),
    }