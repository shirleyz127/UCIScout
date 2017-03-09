import re
import sys
from urlparse import urlparse

from flask import Flask, render_template, request
from flask_paginate import Pagination

from services.es import ElasticsearchService  # TODO: Add package root path

app = Flask(__name__)

argc = len(sys.argv)
es_url = sys.argv[1] if argc > 2 else 'http://localhost:9200'
es_index = sys.argv[2] if argc > 3 else 'html_document_v2'
es_service = ElasticsearchService(es_url)


@app.template_filter('max_length')
def max_length(string, max_length, postfix='...'):
    if len(string) < max_length:
        return string

    if not re.search('\s', string[-max_length:]):
        return string[:max_length] + postfix

    trimmed = string[:max_length + 1]

    # Cut until the next whitespace
    while not trimmed[-1].isspace():
        trimmed = trimmed[:-1]

    # Cut until the next alphanumeric
    trimmed = trimmed[:-1]
    while not trimmed[-1].isalnum():
        trimmed = trimmed[:-1]

    return trimmed + postfix


@app.template_filter('ensure_scheme')
def ensure_scheme(url):
    if not urlparse(url).scheme:
        return 'http://' + url
    return url


@app.route('/', methods=['GET'])
def search_page():
    return render_template('index.html')


@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query')
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page

    num_total_results = es_service.count(es_index, query)
    results = es_service.search(es_index, query, offset=offset, limit=per_page)

    pagination = Pagination(page=page, per_page=per_page, total=num_total_results,
                            inner_window=1, css_framework='bootstrap3')

    return render_template('results.html', query=query, pagination=pagination,
                           results=results, num_total_results=num_total_results)


if __name__ == '__main__':
    app.run()
