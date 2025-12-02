#!/usr/bin/env python
import ast
import hashlib
import json
import os
import csv

import requests
from requests.exceptions import HTTPError

SOURCE_CSV = 'firstfivetest.csv'

BASE_URL = 'https://api.figshare.com/v2/{endpoint}'
TOKEN = ''
CHUNK_SIZE = 1048576

# FILE_PATH = '1.pdf'
# TITLE = 'A Test'


def raw_issue_request(method, url, data=None, binary=False):
    headers = {'Authorization': 'token ' + TOKEN}

    if data is not None and not binary:
        data = json.dumps(data)

    response = requests.request(method, url, headers=headers, data=data)

    try:
        response.raise_for_status()
        try:
            data = json.loads(response.content)
        except ValueError:
            data = response.content

        return data

    except HTTPError as error:
        print(f"HTTPError: {error}")
        print("Response body:", response.text)
        raise


def issue_request(method, endpoint, *args, **kwargs):
    return raw_issue_request(method, BASE_URL.format(endpoint=endpoint), *args, **kwargs)


def list_articles():
    result = issue_request('GET', 'account/articles')
    print('Listing current articles:')
    if result:
        for item in result:
            print(u'  {url} - {title}'.format(**item))
    else:
        print('  No articles.')


def create_article(PUBLICATION_DATE, FIRST_ONLINE_DATE, TITLE, LICENSE, AUTHORS, DESCRIPTION, KEYWORDS):
    data = {
        'title': TITLE,  # You may add any other information about the article here as you wish.
        'authors': [],
        'keyboards': KEYWORDS,
        'description': DESCRIPTION,
        'timeline': {
                "firstOnline": FIRST_ONLINE_DATE,
                "publisherPublication": PUBLICATION_DATE,
                "publisherAcceptance": PUBLICATION_DATE
        },
        'license': LICENSE
    }
    data['authors'].extend(AUTHORS)
    result = issue_request('POST', 'account/articles', data=data)
    print('Created article:', result['location'], '\n')

    result = raw_issue_request('GET', result['location'])

    return result['id']


def list_files_of_article(article_id):
    result = issue_request('GET', 'account/articles/{}/files'.format(article_id))
    print('Listing files for article {}:'.format(article_id))
    if result:
        for item in result:
            print('  {id} - {name}'.format(**item))
    else:
        print('  No files.')


def get_file_check_data(file_name):
    with open(file_name, 'rb') as fin:
        md5 = hashlib.md5()
        size = 0
        data = fin.read(CHUNK_SIZE)
        while data:
            size += len(data)
            md5.update(data)
            data = fin.read(CHUNK_SIZE)
        return md5.hexdigest(), size


def initiate_new_upload(article_id, file_name):
    endpoint = 'account/articles/{}/files'
    endpoint = endpoint.format(article_id)

    md5, size = get_file_check_data(file_name)
    data = {'name': os.path.basename(file_name),
            'md5': md5,
            'size': size}

    result = issue_request('POST', endpoint, data=data)
    print('Initiated file upload:', result['location'], '\n')

    result = raw_issue_request('GET', result['location'])

    return result


def complete_upload(article_id, file_id):
    issue_request('POST', 'account/articles/{}/files/{}'.format(article_id, file_id))


def upload_parts(file_info, file_path):
    url = '{upload_url}'.format(**file_info)
    result = raw_issue_request('GET', url)

    print('Uploading parts:')
    with open(file_path, 'rb') as fin:
        for part in result['parts']:
            upload_part(file_info, fin, part)


def clean_name(name):
    if not name:
        return None

    # Remove whitespace
    name = name.strip()

    # Remove trailing commas
    name = name.rstrip(",")

    # Replace invalid unicode chars
    name = name.replace("\ufffd", "")  # replacement char

    # Collapse double spaces
    name = " ".join(name.split())

    # Must contain at least 2 words
    if len(name.split()) < 2:
        return None

    return name


def upload_part(file_info, stream, part):
    udata = file_info.copy()
    udata.update(part)
    url = '{upload_url}/{partNo}'.format(**udata)

    stream.seek(part['startOffset'])
    data = stream.read(part['endOffset'] - part['startOffset'] + 1)

    raw_issue_request('PUT', url, data=data, binary=True)
    print('  Uploaded part {partNo} from {startOffset} to {endOffset}'.format(**part))


def main():
    # Open the CSV
    with open(SOURCE_CSV, mode='r', encoding='latin1') as csv_file:
        datareader = csv.reader(csv_file)
        next(datareader)  # skip header

        for lines in datareader:
            PUBLICATION_DATE = lines[4]
            FIRST_ONLINE_DATE = lines[6]
            TITLE = lines[7]
            FILE_NAME = lines[1]
            LICENSE_MAP = {
                "https://rightsstatements.org/page/CNE/1.0/?language=en": 1,
                "https://creativecommons.org/licenses/by/4.0/": 2,
                "https://creativecommons.org/publicdomain/zero/1.0/": 1,
                # Add all values appearing in column 8 of your CSV
            }

            raw_license = lines[8]
            LICENSE = LICENSE_MAP.get(raw_license, 1)  # default to CC0
            authors_raw = lines[15]
            DESCRIPTION = lines[16]
            KEYWORDS = ast.literal_eval(lines[17]) # This needs to be parsed out into an array

            # Convert the JSON string to a Python list of dicts
            authors_list = json.loads(authors_raw)

            # Convert each item to "First Last"
            AUTHORS = []
            for a in authors_list:
                raw_name = f"{a.get('first_name', '')} {a.get('last_name', '')}"
                cleaned = clean_name(raw_name)

                if cleaned:
                    AUTHORS.append({"name": cleaned})

            # We first create the article
            # Create the record. Get the ID. Then use the ID. For the File. Do this for all files.
            list_articles()

            article_id = create_article(PUBLICATION_DATE, FIRST_ONLINE_DATE, TITLE, LICENSE, AUTHORS,
                                        DESCRIPTION,
                                        KEYWORDS)
            # 6, 8, 9. 1, 10, 17, 18, 19
            # list_articles()
            # list_files_of_article(article_id)

            # Then we upload the file.
            file_info = initiate_new_upload(article_id, FILE_NAME)
            # Until here we used the figshare API; following lines use the figshare upload service API.
            upload_parts(file_info, FILE_NAME)
            # We return to the figshare API to complete the file upload process.
            complete_upload(article_id, file_info['id'])
            list_files_of_article(article_id)


if __name__ == '__main__':
    main()
