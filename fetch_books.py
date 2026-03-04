import requests
import json
import os

# Configuration
ALMA_API_KEY = os.environ.get('ALMA_API_KEY')
ALMA_BASE_URL = 'https://api-na.hosted.exlibrisgroup.com'
GOOGLE_BOOKS_API = 'https://www.googleapis.com/books/v1/volumes'
OPEN_LIBRARY_API = 'https://covers.openlibrary.org/b/isbn'

# List of MMS IDs to retrieve (you can add more here)
MMS_IDS = [
    '99179893604141',
    # Add more MMS IDs here as needed
]

def get_single_bib(mms_id):
    """Retrieve a single bibliographic record by MMS ID"""
    headers = {
        'Authorization': f'apikey {ALMA_API_KEY}',
        'Accept': 'application/json'
    }
    
    url = f'{ALMA_BASE_URL}/almaws/v1/bibs/{mms_id}'
    
    print(f"Fetching MMS ID: {mms_id}")
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            print(f"✓ Successfully retrieved: {mms_id}")
            return response.json()
        else:
            print(f"✗ Error {response.status_code} for {mms_id}: {response.text}")
            return None
    except Exception as e:
        print(f"✗ Exception for {mms_id}: {e}")
        return None

def extract_isbn(bib_record):
    """Extract ISBN from bibliographic record"""
    try:
        if 'isbn' in bib_record:
            isbn_list = bib_record['isbn']
            if isinstance(isbn_list, list) and len(isbn_list) > 0:
                isbn = str(isbn_list[0]).strip().replace('-', '').replace(' ', '')
                isbn = isbn.split('(')[0].split()[0]
                if len(isbn) in [10, 13]:
                    return isbn
            elif isinstance(isbn_list, str):
                isbn = isbn_list.strip().replace('-', '').replace(' ', '')
                isbn = isbn.split('(')[0].split()[0]
                if len(isbn) in [10, 13]:
                    return isbn
        
        if 'network_number' in bib_record:
            for num in bib_record.get('network_number', []):
                num_str = str(num)
                if 'ISBN' in num_str.upper():
                    isbn = ''.join(filter(lambda x: x.isdigit() or x.upper() == 'X', num_str))
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
            return image_links.get('thumbnail') or image_links.get('smallThumbnail')
    except Exception as e:
        print(f"Google Books API error for ISBN {isbn}: {e}")
    return None

def get_cover_from_open_library(isbn):
    """Fetch cover image URL from Open Library"""
    if not isbn:
        return None
    
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
    
    cover = get_cover_from_google_books(isbn)
    if cover:
        return cover
    
    cover = get_cover_from_open_library(isbn)
    if cover:
        return cover
    
    return 'https://via.placeholder.com/128x192.png?text=No+Cover'

def process_book(bib_record):
    """Process a single bibliographic record"""
    try:
        title = bib_record.get('title', 'Unknown Title')
        author = bib_record.get('author', 'Unknown Author')
        mms_id = bib_record.get('mms_id', '')
        
        isbn = extract_isbn(bib_record)
        print(f"Processing: {title[:50]}... (ISBN: {isbn})")
        
        cover_url = get_cover_image(isbn)
        
        return {
            'title': title,
            'author': author,
            'mms_id': mms_id,
            'isbn': isbn,
            'cover_url': cover_url
        }
    except Exception as e:
        print(f"Error processing book: {e}")
        return None

def main():
    """Main execution function"""
    print("=" * 60)
    print("Starting Book Carousel Update (Test Mode)")
    print("=" * 60)
    
    books = []
    
    print(f"\nFetching {len(MMS_IDS)} book(s) from Alma...")
    
    for mms_id in MMS_IDS:
        bib_record = get_single_bib(mms_id)
        if bib_record:
            book_data = process_book(bib_record)
            if book_data:
                books.append(book_data)
    
    print(f"\n✓ Successfully processed {len(books)} book(s)")
    
    # Save to JSON file
    output_file = 'books.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(books, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Successfully saved {len(books)} book(s) to {output_file}")
    print("=" * 60)
    print("Book Carousel Update Complete!")
    print("=" * 60)

if __name__ == '__main__':
    main()

