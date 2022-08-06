import time
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
import json
from bs4 import BeautifulSoup
import os
import pickle
import re


# this script does create some files under this directory
BASEDIR = os.path.expanduser('~/Documents/MAM_search_calibre')
if not os.path.isdir(BASEDIR):
    os.makedirs(BASEDIR)
sess_filepath = os.path.join(BASEDIR, 'session.pkl')

# these are the defaults
CALIBRE_IP = 'localhost'
CALIBRE_PORT = '8080'

def get_mam_requests():
    keepGoing = True
    start_idx = 0
    req_books = []

    # fetch list of requests to search for
    while keepGoing:
        time.sleep(1)
        url = 'https://www.myanonamouse.net/tor/json/loadRequests.php'
        # get populate headers from developer tools > network activity
        # or by creating a new MAM session to use the MAM requests API
        headers = {
            'cookie': '',
            'user-agent': ''
        }

        params = {
            'tor[text]': '',
            'tor[srchIn][title]': 'true',
            'tor[viewType]': 'unful',
            'tor[cat][]': 'm14',  # search ebooks category
            'tor[startDate]': '',
            'tor[endDate]': '',
            'tor[startNumber]': f'{start_idx}',
            'tor[sortType]': 'dateD'
        }
        data = MultipartEncoder(fields=params)
        headers['Content-type'] = data.content_type
        r = sess.post(url, headers=headers, data=data)
        req_books += r.json()['data']
        total_items = r.json()['found']
        start_idx += 100
        keepGoing = total_items > start_idx
    with open(sess_filepath, 'wb') as f:
        pickle.dump(sess, f)

    with open(mam_blacklist_filepath, 'a') as f:
        for book in req_books:
            f.write(str(book['id']) + '\n')
    return req_books


def reduce_author_str(author):
    return ' '.join([x for x in author.split(' ') if len(x) > 1])


def search_calibre(title, authors):
    queries = [f'{title_varient} {reduce_author_str(author)}'
               for title_varient in get_title_varients(title)
               for author in authors]
    for query in queries:
        params = {
            'library_id': 'Calibre_Library',  # code assumes library_id == Calibre_Library in several places
            'search': query
        }
        r = sess.get(calibre_search_url, params=params, timeout=10)
        r_json = r.json()
        if r_json['metadata']:
            return r_json['metadata']


def get_calibre_book_details_url(calibre_book_id):
    calibre_url = f'http://{CALIBRE_IP}:{CALIBRE_PORT}/#book_id={calibre_book_id}?library_id=Calibre_Library&panel=book_details'
    return calibre_url


mam_blacklist_filepath = os.path.join(BASEDIR, 'blacklisted_ids.txt')
if os.path.exists(mam_blacklist_filepath):
    with open(mam_blacklist_filepath, 'r') as f:
        blacklist = set([int(x.strip()) for x in f.readlines()])
else:
    blacklist = set()


if os.path.exists(sess_filepath):
    sess = pickle.load(open(sess_filepath, 'rb'))
else:
    sess = requests.Session()

get_title_varients = lambda x: {re.sub(' *(?:[\-:].*|\(.*\))* *$', '', x), re.sub(' *(?:\(.*\))* *$', '', x), x}

calibre_search_url = f'http://{CALIBRE_IP}:{CALIBRE_PORT}/interface-data/books-init'


if __name__ == '__main__':
    req_books = get_mam_requests()
    req_books_reduced = [x for x in req_books if
                         x['cat_name'].startswith('Ebooks') and x['filled'] == 0 and x['torsatch'] == 0]

    for book in req_books_reduced:
        book['url'] = 'https://www.myanonamouse.net/tor/viewRequest.php/' + str(book['id'])[:-5] + '.' + str(book['id'])[-5:]
        title = BeautifulSoup(book["title"], features="lxml").text
        authors = [author for k, author in json.loads(book['authors']).items()]
        search_results = search_calibre(title, authors)
        if search_results:
            search_results = {k:v for k,v in search_results.items() if get_title_varients(v['title'].lower()).intersection(get_title_varients(title.lower()))}
        if search_results:
            print(title)
            print(book['url'], f'got {len(search_results)} hits')
            if len(search_results) > 5:
                print(f'showing first 5 results')
            for x in list(search_results.keys())[:5]:
                print(get_calibre_book_details_url(x))
            print()

