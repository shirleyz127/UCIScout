import argparse
from datetime import datetime
from elasticsearch import Elasticsearch
import logging
from lxml import html, etree
from lxml.html.clean import Cleaner
import json
import os
import requests
from urlparse import urljoin


def get_raw_data_path(raw_data_dir, level_1, level_2):
    """Returns the full path to the raw data file."""

    return os.path.join(raw_data_dir, level_1, level_2)


def get_record_generator(book_keeping_file_path, skip_num_lines=None):
    """Yields entries in the book keeping file."""

    with open(book_keeping_file_path) as f:
        if skip_num_lines:
            for _ in xrange(skip_num_lines):
                next(f)

        for line in f:
            level, url = line.strip().split(None, 1)
            level_1, level_2 = level.split('/')

            yield level_1, level_2, url


def index_page(es, index, metadata):
    """Posts the metadata to the provided index on elasticsearch."""

    es.index(index=index, doc_type='html_document', body=metadata)


def parse_raw_html(raw_data_path):
    """Parses raw html and returns metadata.

    Fields in the metadata are:
        title: The title of the page.
        ....
    """

    try:
        with open(raw_data_path) as f:
            document = html.document_fromstring(f.read())
    except (etree.ParserError, IOError):
        return None

    try:
        cleaner = Cleaner(scripts=True, javascript=True, comments=True, style=True,
                          links=True, meta=True, processing_instructions=True)
        body_el = cleaner.clean_html(document.find('.//body'))
        body = ' '.join(body_el.text_content().split())
    except AttributeError:
        return None

    title = get_el_text_content(document, 'title') or body[:60]
    description = get_el_attribute(document, 'meta[@name="description"]', 'content') or body[:150]

    h1s = get_els_text_content(document, 'h1')
    h2s = get_els_text_content(document, 'h2')
    h3s = get_els_text_content(document, 'h3')
    strongs = get_els_text_content(document, 'strong')
    bolds = get_els_text_content(document, 'b')

    return {
        'title': title,
        'description': description,
        'headings': {
            'h1': list(set(h1s)),
            'h2': list(set(h2s)),
            'h3': list(set(h3s)),
        },
        'bold': list(set(strongs).union(bolds)),
        'body': body
    }


def get_el_text_content(document, tag):
    text = document.findtext('.//' + tag)
    return text.strip() if text else ''


def get_el_attribute(document, tag, attribute):
    el = document.find('.//' + tag)
    return el.get(attribute) if el is not None else ''


def get_els_text_content(document, tag):
    els = document.findall('.//' + tag)
    return (el.text.strip() for el in els if el.text and el.text.strip())


def run(es, raw_data_dir, book_keeping_file_path, index, start=0):
    """Reads, parse, and index each entry in the book keeping file."""

    i = 0
    is_finished = False
    err = None
    try:
        for i, record in enumerate(get_record_generator(book_keeping_file_path, start)):
            raw_data_path = get_raw_data_path(raw_data_dir, record[0], record[1])
            metadata = parse_raw_html(raw_data_path)
            if not metadata:
                continue

            metadata['url'] = record[2]
            index_page(es, index, metadata)

        is_finished = True
    except Exception as e:
        err = e
    finally:
        return i, is_finished, err


def initialize_index(es, index):
    data = {
        'settings': {
            'analysis': {
                'analyzer': {
                    'url_analyzer': {
                        'tokenizer': 'uax_url_email'
                    }
                }
            }
        },
        'mappings': {
            'html_document': {
                'properties': {
                    'title': {
                        'type': 'text',
                        'analyzer': 'english'
                    },
                    'description': {
                        'type': 'text',
                        'analyzer': 'english'
                    },
                    'headings': {
                        'properties': {
                            'h1': {
                                'type': 'text',
                                'analyzer': 'english'
                            },
                            'h2': {
                                'type': 'text',
                                'analyzer': 'english'
                            },
                            'h3': {
                                'type': 'text',
                                'analyzer': 'english'
                            }
                        }
                    },
                    'bold': {
                        'type': 'text',
                        'analyzer': 'english'
                    },
                    'body': {
                        'type': 'text',
                        'analyzer': 'english'
                    },
                    'url': {
                        'type': 'text',
                        'analyzer': 'url_analyzer'
                    }
                }
            }
        }
    }

    es.indices.create(index=index, body=data)


def load_progress(file_path):
    with open(file_path) as f:
        progress = json.loads(f.read())
        return progress


def save_progress(progress, file_path, end, is_finished):
    with open(file_path, 'w') as f:
        progress.append(dict(run_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                             end_line_num=end, is_finished=is_finished))
        f.write(json.dumps(progress, sort_keys=True, indent=4, separators=(',', ': ')))


def get_parser():
    parser = argparse.ArgumentParser('Indexes all the webpages in a given directory.')
    parser.add_argument('raw_data_dir', help='Directory containing all the HTML files.')
    parser.add_argument('book_keeping_file_path',
                        help='File containing the url of a HTML file and where it is '
                             'located in the raw_data_dir.')
    parser.add_argument('--elasticsearch-host', default='localhost',
                        help='Elastic Search Host (Default: localhost).')
    parser.add_argument('--elasticsearch-port', default='9200', type=int,
                        help='Elastic Search Port (Default: 9200).')
    parser.add_argument('--log-level', '-l', default='INFO', help='Log level (Default: INFO).')
    parser.add_argument('--no-load-progress', action='store_true', help='Skip loading progress (Default: False).')
    parser.add_argument('--initialize-index', action='store_true', help='Initialize index (Default: False).')
    return parser


def get_logger(log_level):
    logging.basicConfig(level=logging.getLevelName(log_level))
    logger = logging.getLogger(__name__)
    return logger


def get_elasticsearch_connection(host, port):
    es = Elasticsearch([{'host': host, 'port': port}])
    return es


def main():
    parser = get_parser()
    args = parser.parse_args()
    index = 'html_document_v2'

    global logger
    logger = get_logger(args.log_level)

    es = get_elasticsearch_connection(args.elasticsearch_host, args.elasticsearch_port)

    if args.initialize_index:
        logger.info('Initializing index "{}"...'.format(index))
        initialize_index(es, index)

    workspace = os.path.dirname(args.book_keeping_file_path)
    progress_file = os.path.join(workspace, 'progress.json')

    start = 0
    progress = []
    if os.path.exists(progress_file) and not args.no_load_progress:
        progress = load_progress(progress_file)
        prev_run = progress[-1]
        if prev_run['is_finished']:
            logger.info('Previous run marked indexer as finished. Exiting.')
            return

        start = prev_run['end_line_num']
        logger.warn('Previous progress found, resuming from line {} in {}.'.format(start, args.book_keeping_file_path))

    end, is_finished, err = run(es, args.raw_data_dir, args.book_keeping_file_path, index, start)

    logger.info('Run ending... Saving progress at {}...'.format(progress_file))
    save_progress(progress, progress_file, end, is_finished)

    if err:
        raise err

    logger.info('Done!')


if __name__ == '__main__':
    main()