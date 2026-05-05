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
        ns = {
            'ns': 'urn:schemas-microsoft-com:xml-analysis:rowset',
            'xsd': 'http://www.w3.org/2001/XMLSchema',
            'saw-sql': 'urn:saw-sql'
        }

        # Get rows
        rows = root.findall('.//ns:Row', ns)
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

def parse_print_books(rows):
    """Parse print book rows from Analytics report"""
    books = []
    for row in rows:
        try:
            title = getattr(row.find('Column1'), 'text', None) or 'Unknown Title'
            author = getattr(row.find('Column2'), 'text', None) or 'Unknown Author'
            isbn = getattr(row.find('Column3'), 'text', None)
            call_number = getattr(row.find('Column4'), 'text', None) or ''

            books.append({
                'title': title.strip(),
                'author': author.strip(),
                'isbn': isbn.strip() if isbn else None,
                'call_number': call_number.strip(),
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
            title = getattr(row.find('Column1'), 'text', None) or 'Unknown Title'
            author = getattr(row.find('Column2'), 'text', None) or 'Unknown Author'
            isbn = getattr(row.find('Column3'), 'text', None)
            platform = getattr(row.find('Column4'), 'text', None) or ''

            books.append({
                'title': title.strip(),
                'author': author.strip(),
                'isbn': isbn.strip() if isbn else None,
                'platform': platform.strip(),
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
