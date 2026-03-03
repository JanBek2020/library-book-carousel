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
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

def query_alma_books():
    """Query Alma API for new books (print and ebooks) from last 90 days"""
    start_date, end_date = get_date_range()
    
    # Query for books (material_type~BK includes both print and ebooks)
    query = f'created_date~[{start_date},{end_date}] AND material_type~BK'
    
    headers = {
        'Authorization': f'apikey {ALMA_API_KEY}',
        'Accept': 'application/json'
    }
    
    params = {
        'q': query,
        'limit': 100,  # Fetch more than 50 to allow for randomization
        'offset': 0
    }
    
    url = f'{ALMA_BASE_URL}/almaws/v1/bibs'
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get('bib', [])
    except requests.exceptions.RequestException as e:
        print(f"Error querying Alma API: {e}")
        return []

def extract_isbn(bib_record):
    """Extract ISBN from bibliographic record"""
    try:
        # Check for ISBN in standard number field
        if 'isbn' in bib_record:
            return bib_record['isbn'][0] if isinstance(bib_record['isbn'], list) else bib_record['isbn']
        
        # Parse from MARC record if available
        if 'anies' in bib_record:
            for field in bib_record['anies']:
                if 'isbn' in field.lower():
                    # Extract ISBN (remove hyphens and take first 10 or 13 digits)
                    isbn = ''.join(filter(str.isdigit, field))
                    if len(isbn) in [10, 13]:
                        return isbn
    except:
        pass
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
    except:
        pass
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
    except:
        pass
    return None

def get_cover_image(isbn):
    """Try multiple sources for cover image"""
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
            isbn = extract_isbn(bib)
            
            # Get cover image
            cover_url = get_cover_image(isbn)
            
            book_data = {
                'title': title,
                'author': author,
                'mms_id': mms_id,
                'isbn': isbn,
                'cover_url': cover_url
            }
            
            books.append(book_data)
            print(f"Processed: {title}")
            
        except Exception as e:
            print(f"Error processing book: {e}")
            continue
    
    return books

def main():
    """Main execution function"""
    print("Fetching new books from Alma...")
    bib_records = query_alma_books()
    
    if not bib_records:
        print("No books found or API error occurred")
        return
    
    print(f"Found {len(bib_records)} books")
    
    print("Processing book data and fetching covers...")
    books = process_books(bib_records)
    
    # Randomly select up to 50 books
    if len(books) > 50:
        books = random.sample(books, 50)
        print(f"Randomly selected 50 books from {len(books)} available")
    
    # Save to JSON file
    output_file = 'books.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(books, f, indent=2, ensure_ascii=False)
    
    print(f"Successfully saved {len(books)} books to {output_file}")

if __name__ == '__main__':
    main()
