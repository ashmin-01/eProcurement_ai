import scrapy

class ProductItem(scrapy.Item):
    brand = scrapy.Field()
    product_name = scrapy.Field()
    model_article_number = scrapy.Field()
    short_description = scrapy.Field()
    long_description = scrapy.Field()
    product_image_url = scrapy.Field()
    datasheet_url = scrapy.Field()
    technical_specifications = scrapy.Field()
    product_url = scrapy.Field()
    type_id = scrapy.Field()
    classification_path = scrapy.Field()
