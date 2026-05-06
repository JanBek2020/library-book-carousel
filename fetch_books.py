import requests
import json
import random
import os
import xml.etree.ElementTree as ET

# Configuration
ANALYTICS_API_KEY = os.environ.get('ALMA_ANALYTICS_KEY')
ALMA_BASE_URL = 'https://api-na.hosted.exlibrisgroup.com'
GOOGLE_BOOKS_API = 'https://www.googleapis.com/books/v1/volumes'
OPEN_LIBRARY_COVER = 'https://covers.openlibrary.org/b/isbn'

EBOOK_REPORT_PATH = '/shared/Hobart/Reports/Alma Analytics API/New Ebooks'
PRINT_REPORT_PATH = '/shared/Hobart/Reports/Alma Analytics API/New Print Books'

NS = {
    'ns': 'urn:schemas-microsoft-com:xml-analysis:rowset',
    'xsd': 'http://www.w3.org/2001/XMLSchema',
    'saw-sql': 'urn:saw-sql'
}

def fetch_analytics_report(report_path):
    """Fetch results from an Alma Analytics report"""
    headers = {
        'Authorization': f'apikey {ANALYTICS_API_KEY}',
        'Accept': 'application/xml'
    }

    params = {
        'path': report_path,
        'limit': 1000
    }

    url = f'{ALMA_BASE_URL}/almaws/v1/analytics/reports'

    all_rows = []
    is_finished = False
    token = None
    first_batch = True

    while not is_finished:
        if token:
            params['token'] = token

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching Analytics report: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Status code: {e.response.status_code}")
                print(f"Full error response: {e.response.text}")
            break

        root = ET.fromstring(response.content)

        # Get rows
        rows = root.findall('.//ns:Row', NS)

        # DEBUG: Print column tags from first row of first batch
        if first_batch and rows:
            print("DEBUG - Column tags in first row:")
            for child in rows[0]:
                print(f"  Tag: {child.tag!r}, Text: {child.text!r}")
            first_batch = False

        all_rows.extend(rows)

        # Check if finished
        is_finished_el = root.find('.//IsFinished')
        is_finished = is_finished_el is not None and is_finished_el.text.lower() == 'true'

        # Get resumption token if not finished
        if not is_finished:
            token_el = root.find('.//ResumptionToken')
            if token_el is not None:
                token = token_el.text
            else:
                is_finished = True

    print(f"Fetched {len(all_rows)} rows from {report_path}")
    return all_rows


def get_cell_text(row, *tag_names):
    """Try multiple tag name variations to find a cell value"""
    for tag in tag_names:
        # Try with namespace
        el = row.find(f'ns:{tag}', NS)
        if el is not None and el.text:
            return el.text.strip()
        # Try without namespace
        el = row.find(tag)
        if el is not None and el.text:
            return el.text.strip()
    return None


def extract_best_isbn(isbn_field):
    """Extract best ISBN from semicolon-separated list, preferring ISBN-13"""
    if not isbn_field:
        return None

    # Split on semicolon (with or without trailing space)
    isbns = [i.strip() for i in isbn_field.split(';') if i.strip()]

    # Prefer ISBN-13 (starts with 978 or 979, 13 digits)
    for isbn in isbns:
        cleaned = isbn.replace('-', '').replace(' ', '')
        if len(cleaned) == 13 and cleaned[:3] in ['978', '979'] and cleaned.isdigit():
            return cleaned

    # Fall back to first valid ISBN-10 (may end in X)
    for isbn in isbns:
        cleaned = isbn.replace('-', '').replace(' ', '')
        if len(cleaned) == 10:
            return cleaned

    return isbns[0] if isbns else None


def parse_print_books(rows):
    """Parse print book rows from Analytics report"""
    books = []
    for row in rows:
        try:
            title = get_cell_text(row, 'Column3', 'Title') or ''
            author = get_cell_text(row, 'Column1', 'Author') or ''
            isbn_raw = get_cell_text(row, 'Column2', 'ISBN') or ''
            call_number = get_cell_text(row, 'Column4', 'PermanentCallNumber', 'Permanent Call Number') or ''

            if not title:
                continue

            books.append({
                'title': title,
                'author': author,
                'isbn': extract_best_isbn(isbn_raw),
                'call_number': call_number,
                'type': 'print'
            })
        except Exception as e:
            print(f"Error parsing print row: {e}")
            continue
    return books


def parse_ebooks(rows):
    """Parse ebook rows from Analytics report"""
    books = []
    for row in rows:
        try:
            title = get_cell_text(row, 'Column3', 'Title') or ''
            author = get_cell_text(row, 'Column1', 'Author') or ''
            isbn_raw = get_cell_text(row, 'Column2', 'ISBN') or ''
            platform = get_cell_text(row, 'Column4', 'ElectronicCollectionInterfaceName', 'Electronic Collection Interface Name') or ''

            if not title:
                continue

            books.append({
                'title': title,
                'author': author,
                'isbn': extract_best_isbn(isbn_raw),
                'platform': platform,
                'type': 'ebook'
            })
        except Exception as e:
            print(f"Error parsing ebook row: {e}")
            continue
    return books


def get_cover_from_google(isbn):
    """Fetch cover image URL from Google Books API"""
    if not isbn:
        return None
    try:
        params = {'q': f'isbn:{isbn}'}
        response = requests.get(GOOGLE_BOOKS_API, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data.get('totalItems', 0) > 0:
            image_links = data['items'][0].get('volumeInfo', {}).get('imageLinks', {})
            return image_links.get('thumbnail') or image_links.get('smallThumbnail')
    except:
        pass
    return None


def get_cover_from_open_library(isbn):
    """Fetch cover image URL from Open Library"""
    if not isbn:
        return None
    try:
        cover_url = f'{OPEN_LIBRARY_COVER}/{isbn}-M.jpg'
        response = requests.head(cover_url, timeout=5)
        if response.status_code == 200:
            return cover_url
    except:
        pass
    return None


def get_cover(isbn):
    """Try Google Books first, then Open Library, then placeholder"""
    cover = get_cover_from_google(isbn)
    if cover:
        return cover
    cover = get_cover_from_open_library(isbn)
    if cover:
        return cover
    return 'https://via.placeholder.com/128x192.png?text=No+Cover'


def main():
    print("Fetching print books from Alma Analytics...")
    print_rows = fetch_analytics_report(PRINT_REPORT_PATH)
    print_books = parse_print_books(print_rows)
    print(f"Parsed {len(print_books)} print books")

    print("Fetching ebooks from Alma Analytics...")
    ebook_rows = fetch_analytics_report(EBOOK_REPORT_PATH)
    ebooks = parse_ebooks(ebook_rows)
    print(f"Parsed {len(ebooks)} ebooks")

    # Combine and shuffle
    all_books = print_books + ebooks
    random.shuffle(all_books)

    # Select up to 50
    selected = all_books[:50]
    print(f"Selected {len(selected)} books for carousel")

    # Fetch covers
    print("Fetching cover images...")
    for book in selected:
        book['cover_url'] = get_cover(book.get('isbn'))
        print(f"  ✓ {book['title'][:50]}")

    # Save to JSON
    with open('books.json', 'w', encoding='utf-8') as f:
        json.dump(selected, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Successfully saved {len(selected)} books to books.json")


if __name__ == '__main__':
    main()
