import scrapy
import re
import json
from urllib.parse import urljoin, urlparse
from ..items import ProductItem 
from w3lib.html import remove_tags

class SikaCrawlerSpider(scrapy.Spider):
    name = 'sika_crawler'
    allowed_domains = ['gcc.sika.com']

    start_urls = [
        'https://gcc.sika.com/en/construction.html', # Main entry point
        'https://gcc.sika.com/en/construction/refurbishment.html', 
        'https://gcc.sika.com/en/construction/concrete.html',
        'https://gcc.sika.com/en/construction/waterproofing.html',
        'https://gcc.sika.com/en/construction/roofing.html',
        'https://gcc.sika.com/en/construction/flooring-and-coating.html',
        'https://gcc.sika.com/en/construction/sealing-bonding/sealing-bonding-solutions.html',
        'https://gcc.sika.com/en/construction/refurbishment/wall-facade-system.html',
        'https://gcc.sika.com/en/construction/building-finishing/tiling-system.html',
    ]

    # Stores the core path of each starting URL for constrained recursion
    start_path_roots = set() 
    
    visited_urls = set()
    processed_products = set()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-process start_urls to build the set of required paths
        for url in self.start_urls:
            path_segment = urlparse(url).path
            self.start_path_roots.add(path_segment.replace('.html', '').strip('/'))

    # --- 1. INITIAL REQUEST (USES PLAYWRIGHT) ---
    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse_category_page,
                #meta={
                #    "playwright": True, 
                #    "playwright_wait_until": "commit",
                    #"playwright_page_goto_kwargs": {"timeout": 15000}
                #}
            )

    # --- 2. LINK DISCOVERY  ---
    # TODO: Improve filtering to catch more product links while avoiding categories.
    def parse_category_page(self, response):
        current_url = response.url.strip()
        if current_url in self.visited_urls:
            return

        self.visited_urls.add(current_url)
        self.logger.info(f"🔍 Scanning {response.url}")

        all_link_elements = response.css('a::attr(href)').getall()
        
        for link in all_link_elements:
            if not link or link.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                continue
            
            full_url = urljoin(response.url, link.strip())
            
            # 1. Domain and Basic URL Validation
            if not self.is_valid_domain(full_url) or self.is_utility_url(full_url):
                continue    
            # 2. Check if it's a likely product page 
            if self.is_probable_product_link(full_url):
                if full_url not in self.processed_products:
                    self.processed_products.add(full_url)
                    self.logger.info(f"📦 Discovered product: {full_url}")  
                    #yield ProductLinkItem(product_url=full_url)

                    yield scrapy.Request(
                        full_url, 
                        callback=self.parse_product_page
                    )
                continue # IMPORTANT: If it's a product, skip to the next link.
            
            # 3. Constrained Category Recursion
            # Only follow unvisited, HTML pages that are within the allowed scope (one of the start roots or a sub-path)
            if (
                full_url.endswith(".html")
                and full_url not in self.visited_urls
                and self.is_within_scope(full_url)
            ):
                self.logger.debug(f"➡️ Following category: {full_url}") 
                yield scrapy.Request(
                    full_url,
                    callback=self.parse_category_page,
                    #meta={
                    #    "playwright": True,
                    #    "playwright_wait_until": "commit"
                    #}
                )

    # --- 3. HELPER FUNCTIONS FOR LINK FILTERING ---
    def is_valid_domain(self, url):
        parsed = urlparse(url)
        # Check domain and ensure it starts with the /en/construction/ path
        return (
            parsed.netloc == "gcc.sika.com"
            and parsed.path.startswith("/en/construction/")
        )
    
    def is_within_scope(self, url):
        """Checks if the URL is a path that starts with one of our defined roots."""
        path = urlparse(url).path.replace(".html", "").strip("/")
        return any(path.startswith(root) for root in self.start_path_roots)

    def is_utility_url(self, url):
        """Checks for common, non-product utility pages."""
        url_lower = url.lower()
        non_product_keywords = [
            'about-', 'contact-', 'news', 'career', 'privacy', 'cookie', 
            'legal', 'search', 'sitemap', 'download', '.pdf', '.jpg'
        ]
        return any(k in url_lower for k in non_product_keywords)
    
    def is_probable_product_link(self, link):
        """
        IMPROVED: Catches product links that have 'sika' OR a digit, 
        and enforces a minimum depth to filter high-level categories.
        """
        link = link.lower().strip()
        
        if not link.endswith(".html"):
            return False

        parsed = urlparse(link)
        path_parts = parsed.path.strip("/").split("/")

        # Minimum path depth (e.g., /en/construction/refurbishment/grouting/cementitious-grouts.html is 6 parts)
        if len(path_parts) < 6:
            return False 

        last_segment = path_parts[-1]

        # Product Signature: Must contain 'sika' OR a digit. 
        # This catches 'sikagrout-cable-pt.html' (sika) AND 'sikaceram-255-starflexldae.html' (sika, digit).
        is_product_signature = ("sika" in last_segment) or re.search(r"\d", last_segment)
        
        if not is_product_signature:
            return False

        # Optional: Block high-level category pages that might slip through, but only at the 6-segment depth
        blocked_keywords = {"tile-grout", "tile-adhesive", "anchoring", "grouting", "waterproofing", "roofing"}
        
        if len(path_parts) == 6 and any(bk in last_segment for bk in blocked_keywords):
             return False 

        return True

    # --- 4. DATA EXTRACTION ---    
    def parse_product_page(self, response):
        """
        Extracts cleaned product data and technical specs.
        Unicode is handled via settings, and HTML tags are stripped via w3lib.
        """
        if not self.is_valid_product_page(response):
            return

        item = ProductItem()
        tech_specs = {}

        # Target the accordion sections
        sections = response.css('.cmp-accordion__item')
        allowed_sections = ["Product Information", "Technical Information"]

        for section in sections:
            section_name = section.css('.cmp-accordion__title::text').get()
            if not section_name:
                continue
            
            section_name = section_name.strip()

            if section_name in allowed_sections:
                for block in section.css('.productcontent'):
                    key = block.css('h3::text').get()

                    if key:
                        key = key.strip()

                        # If it's a table, we strip all tags to get clean plain text.
                        # If it's standard text, we join all nested text parts.
                        if block.css('table'):
                            raw_html = block.css('table').get()
                            # remove_tags cleans the HTML, then we collapse whitespace
                            clean_value = remove_tags(raw_html)
                            value = ' '.join(clean_value.split())
                        else:
                            # Grab all text from spans/paragraphs, stripping extra whitespace
                            value_parts = block.css('.cmp-product span *::text').getall()
                            value = ' '.join([p.strip() for p in value_parts if p.strip()]).strip()

                        tech_specs[f"{section_name}: {key}"] = value

        # --- Main Data Extraction ---
        datasheet_url = response.css('a.cmp-button:contains("Product Data Sheet")::attr(href)').get()

        item['brand'] = 'Sika'
        item['product_name'] = self.simple_clean(response.css('h1[itemprop="name"]::text').get() or response.css('h1::text').get())
        item['model_article_number'] = response.css('meta[itemprop="code"]::attr(content)').get()
        item['short_description'] = self.simple_clean(response.css('div.cmp-product__description--short::text').get())

        # Clean the long description text by joining all nested parts
        long_desc_parts = response.css('p[itemprop="description"] *::text').getall()
        item['long_description'] = self.simple_clean(' '.join(long_desc_parts))

        item['product_image_url'] = response.css('meta[property="og:image"]::attr(content)').get()
        item['datasheet_url'] = response.urljoin(datasheet_url) if datasheet_url else None
        item['technical_specifications'] = tech_specs
        item['product_url'] = response.url
        item['type_id'] = ''
        item['classification_path'] = ''


        yield item
      

    # --- 5. CONTENT VALIDATION AND CLEANING FUNCTIONS ---
    
    def is_valid_product_page(self, response):
        """Checks if the content on the page looks like a real product page."""
        strong_indicators = ['Product Details', 'Technical Data', 'Technical Information']
        page_text = ' '.join(response.css('body ::text').getall()).lower()
        if any(term.lower() in page_text for term in strong_indicators):
            return True
        if any('pds' in link.lower() or 'data-sheet' in link.lower() for link in response.css('a[href*=".pdf"]::attr(href)').getall()):
             return True
        return False
        
    def simple_clean(self, text):
        if not text:
            return ''
        text = str(text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()