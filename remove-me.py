#!/usr/bin/env python
import json
import requests
from requests.exceptions import HTTPError

# ==== CONFIG ====
BASE_URL = "https://api.figshare.com/v2/{endpoint}"
TOKEN = "YOUR_TOKEN_HERE"  # <-- paste your token or import from your existing script
TARGET_NAME = "jonathan candelaria"  # case-insensitive match
PAGE_SIZE = 100                      # how many articles per page
DRY_RUN = True                       # set to False to actually apply changes
# =================


def raw_issue_request(method, url, data=None, binary=False):
    headers = {"Authorization": "token " + TOKEN}

    if data is not None and not binary:
        headers["Content-Type"] = "application/json"
        data = json.dumps(data)

    resp = requests.request(method, url, headers=headers, data=data)
    try:
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            return resp.content
    except HTTPError as e:
        print(f"HTTPError: {e}")
        print("Response body:", resp.text)
        raise


def issue_request(method, endpoint, *args, **kwargs):
    url = BASE_URL.format(endpoint=endpoint)
    return raw_issue_request(method, url, *args, **kwargs)


def normalize_author_name(author_obj):
    """
    Figshare article authors API returns entries like:
      {"id": 12345, "name": "Firstname Lastname", ...}

    We only care about 'name' here.
    """
    name = author_obj.get("name", "")
    return name.strip().lower()


def fetch_all_articles():
    """
    Iterate through /account/articles pages and yield article dicts.
    """
    page = 1
    while True:
        endpoint = f"account/articles?page={page}&page_size={PAGE_SIZE}"
        articles = issue_request("GET", endpoint)

        if not articles:
            break

        for a in articles:
            yield a

        page += 1


def fetch_article_authors(article_id):
    """
    GET /v2/account/articles/{id}/authors
    """
    endpoint = f"account/articles/{article_id}/authors"
    return issue_request("GET", endpoint)


def update_article_authors(article_id, new_authors):
    """
    PUT /v2/account/articles/{id}/authors
    body: {"authors": [ { "id": ... } or { "name": "..." }, ... ]}
    """
    endpoint = f"account/articles/{article_id}/authors"
    data = {"authors": new_authors}

    if DRY_RUN:
        print(f"[DRY RUN] Would update article {article_id} with authors:")
        for a in new_authors:
            print("    ", a)
        return

    print(f"Updating authors for article {article_id}...")
    issue_request("PUT", endpoint, data=data)
    print(f"Done updating article {article_id}.")


def main():
    print("Fetching all articles for this account...")
    articles_processed = 0
    articles_modified = 0
    authors_removed_total = 0

    for article in fetch_all_articles():
        article_id = article["id"]
        article_title = article.get("title", f"(id={article_id})")

        authors = fetch_article_authors(article_id)

        if not authors:
            # no authors on this article
            articles_processed += 1
            continue

        # Filter out "Jonathan Candelaria"
        kept_authors = []
        removed_authors = []

        for a in authors:
            norm = normalize_author_name(a)

            if norm == TARGET_NAME:
                removed_authors.append(a)
            else:
                # Keep the full author object as returned (id, name, etc.)
                kept_authors.append(a)

        if removed_authors:
            print(f"\nArticle {article_id}: {article_title}")
            print(f"  Removing {len(removed_authors)} instance(s) of '{TARGET_NAME}'")
            for ra in removed_authors:
                print("    Removed:", ra.get("name"), "(id:", ra.get("id"), ")")

            # Apply update (or just print if DRY_RUN)
            update_article_authors(article_id, kept_authors)

            articles_modified += 1
            authors_removed_total += len(removed_authors)

        articles_processed += 1

    print("\n=== Summary ===")
    print("Articles processed:", articles_processed)
    print("Articles modified:", articles_modified)
    print("Total 'Jonathan Candelaria' authors removed:", authors_removed_total)
    if DRY_RUN:
        print("\nNOTE: DRY_RUN is True, no actual changes were made.")
        print("      Set DRY_RUN = False to apply updates for real.")


if __name__ == "__main__":
    main()
