from elasticsearch import Elasticsearch

class ElasticsearchService():
    def __init__(self, es_url):
        self.es = Elasticsearch([es_url])

    def search(self, index, query, offset, limit):
        body = {
            'from': offset,
            'size': limit,
            'query': {
                'multi_match': {
                    'query': query,
                    'fields': [
                        '_all',
                        'title^5',
                        'headings.h1^4',
                        'headings.h2^3',
                        'headings.h3^2',
                        'bold^2'
                    ],
                    'operator': 'and'
                }
            }
        }

        res = self.es.search(index=index, body=body)
        results = []

        for hit in res['hits']['hits']:
            source = hit['_source']
            results.append({
                'title': source['title'],
                'url': source['url'],
                'description': source['description']
            })

        return results


    def count(self, index, query):
        body = {
            'query': {
                'multi_match': {
                    'query': query,
                    'fields': [
                        '_all',
                        'title^5',
                        'headings.h1^4',
                        'headings.h2^3',
                        'headings.h3^2',
                        'bold^2'
                    ],
                    'operator': 'and'
                }
            }
        }

        count = self.es.count(index=index, body=body)['count']
        return count
