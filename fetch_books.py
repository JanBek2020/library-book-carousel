import requests
import json
import random
from datetime import datetime, timedelta
import os

# Configuration
ALMA_API_KEY = os.environ.get('ALMA_API_KEY')
ALMA_BASE_URL = 'https://api-na.hosted.exlibrisgroup.com'
GOOGLE_BOOKS_API = 'https://www.googleapis.com/books/v1/volumes'
OPEN_LIBRARY_API = 'https://covers.openlibrary.org/b/isbn'

def get_date_range():
    """Calculate date range for last 90 days"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    # Format: YYYYMMDD (Alma prefers this format)
    return start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d')

def query_alma_books():
    """Query Alma API for new books (print and ebooks) from last 90 days"""
    start_date, end_date = get_date_range()
    
    # Simplified query - try without material_type filter first
    query = f'created_date~[{start_date},{end_date}]'
    
    headers = {
        'Authorization': f'apikey {ALMA_API_KEY}',
        'Accept': 'application/json'
    }
    
    params = {
        'q': query,
        'limit': 100,
        'offset': 0
    }
    
    url = f'{ALMA_BASE_URL}/almaws/v1/bibs'
    
    print(f"Querying Alma API with date range: {start_date} to {end_date}")
    print(f"Full URL: {url}")
    print(f"Query: {query}")
    
    try:
        response = requests.get(url, headers=headers, params=params)
        print(f"Response status code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error response: {response.text}")
        
        response.raise_for_status()
        data = response.json()
        
        total_records = data.get('total_record_count', 0)
        print(f"Total records found: {total_records}")
        
        return data.get('bib', [])
    except requests.exceptions.RequestException as e:
        print(f"Error querying Alma API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response content: {e.response.text}")
        return []

def extract_isbn(bib_record):
    """Extract ISBN from bibliographic record"""
    try:
        # Try multiple fields where ISBN might be stored
        if 'isbn' in bib_record:
            isbn_list = bib_record['isbn']
            if isinstance(isbn_list, list) and len(isbn_list) > 0:
                return isbn_list[0]
            elif isinstance(isbn_list, str):
                return isbn_list
        
        # Try network_number field
        if 'network_number' in bib_record:
            for num in bib_record.get('network_number', []):
                if 'ISBN' in num.upper():
                    # Extract just the ISBN digits
                    isbn = ''.join(filter(lambda x: x.isdigit() or x.upper() == 'X', num))
                    if len(isbn) in [10, 13]:
                        return isbn
    except Exception as e:
        print(f"Error extracting ISBN: {e}")
    return None

def get_cover_from_google_books(isbn):
    """Fetch cover image URL from Google Books API"""
    if not isbn:
        return None
    
    try:
        params = {'q': f'isbn:{isbn}'}
        response = requests.get(GOOGLE_BOOKS_API, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data.get('totalItems', 0) > 0:
            volume_info = data['items'][0].get('volumeInfo', {})
            image_links = volume_info.get('imageLinks', {})
            # Prefer larger thumbnail
            return image_links.get('thumbnail') or image_links.get('smallThumbnail')
    except Exception as e:
        print(f"Google Books API error for ISBN {isbn}: {e}")
    return None

def get_cover_from_open_library(isbn):
    """Fetch cover image URL from Open Library"""
    if not isbn:
        return None
    
    # Try medium size cover
    cover_url = f'{OPEN_LIBRARY_API}/{isbn}-M.jpg'
    try:
        response = requests.head(cover_url, timeout=5)
        if response.status_code == 200:
            return cover_url
    except Exception as e:
        print(f"Open Library error for ISBN {isbn}: {e}")
    return None

def get_cover_image(isbn):
    """Try multiple sources for cover image"""
    if not isbn:
        return 'https://via.placeholder.com/128x192.png?text=No+Cover'
    
    # Try Google Books first
    cover = get_cover_from_google_books(isbn)
    if cover:
        return cover
    
    # Fallback to Open Library
    cover = get_cover_from_open_library(isbn)
    if cover:
        return cover
    
    # Return placeholder if no cover found
    return 'https://via.placeholder.com/128x192.png?text=No+Cover'

def process_books(bib_records):
    """Process bibliographic records into carousel-ready format"""
    books = []
    
    for bib in bib_records:
        try:
            title = bib.get('title', 'Unknown Title')
            author = bib.get('author', 'Unknown Author')
            mms_id = bib.get('mms_id', '')
            
            # Extract ISBN
            isbn = extract_isbn(bib)
            
            # Get cover image
            print(f"Processing: {title[:50]}... (ISBN: {isbn})")
            cover_url = get_cover_image(isbn)
            
            book_data = {
                'title': title,
                'author': author,
                'mms_id': mms_id,
                'isbn': isbn,
                'cover_url': cover_url
            }
            
            books.append(book_data)
            
        except Exception as e:
            print(f"Error processing book: {e}")
            continue
    
    return books

def main():
    """Main execution function"""
    print("=" * 60)
    print("Starting Book Carousel Update")
    print("=" * 60)
    
    print("\nFetching new books from Alma...")
    bib_records = query_alma_books()
    
    if not bib_records:
        print("\n⚠️  No books found or API error occurred")
        print("Creating empty books.json to prevent workflow failure")
        # Create empty file so Git commit doesn't fail
        with open('books.json', 'w', encoding='utf-8') as f:
            json.dump([], f)
        return
    
    print(f"\n✓ Found {len(bib_records)} books")
    
    print("\nProcessing book data and fetching covers...")
    books = process_books(bib_records)
    
    print(f"\n✓ Successfully processed {len(books)} books")
    
    # Randomly select up to 50 books
    if len(books) > 50:
        books = random.sample(books, 50)
        print(f"✓ Randomly selected 50 books from {len(books)} available")
    
    # Save to JSON file
    output_file = 'books.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(books, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Successfully saved {len(books)} books to {output_file}")
    print("=" * 60)
    print("Book Carousel Update Complete!")
    print("=" * 60)

if __name__ == '__main__':
    main()
