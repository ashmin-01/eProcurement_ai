import logging
from itemadapter import ItemAdapter
from classification.classify_products import ProductClassifier

logger = logging.getLogger(__name__)

class ClassificationPipeline:
    
    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create the pipeline instance.
        return cls()

    def open_spider(self, spider):
        # initializes the heavy classifier ONCE.
        logger.info(f"Opening spider {spider.name}. Initializing classifier...")
        self.classifier = ProductClassifier()
        logger.info("Classifier initialized for spider.")

    def close_spider(self, spider):
        logger.info(f"Closing spider {spider.name}.")
        del self.classifier

    def process_item(self, item, spider):
            adapter = ItemAdapter(item)
            product_data = adapter.asdict()

            classification_result = self.classifier.classify_product(product_data, use_llm=True)

            if classification_result:
                adapter['type_id'] = classification_result.get('selected_type_id')
                adapter['classification_path'] = classification_result.get('classification_path')
            else:
                adapter['type_id'] = None
                adapter['classification_path'] = "Classification Failed"

            fields_to_keep = {'product_name', 'type_id', 'classification_path'}
            all_fields = list(adapter.keys())

            for field in all_fields:
                if field not in fields_to_keep:
                    del item[field] 

            return item