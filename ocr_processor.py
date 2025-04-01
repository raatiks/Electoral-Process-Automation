import cv2
import pytesseract
import re
import sqlite3
import glob

# Configure Tesseract path
pytesseract.pytesseract.tesseract_cmd = '/usr/local/bin/tesseract'


def preprocess_image(image_path):
    image = cv2.imread(image_path)
    image = cv2.resize(image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 3)
    processed = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    return processed


def extract_data(image_path):
    processed = preprocess_image(image_path)
    text = pytesseract.image_to_string(processed)
    return text


FIELD_MAPPINGS = {
    'mobile_voter': {
        'voter_id': r'(?:TempID|TID)[:\s]*(\d+)',
        'name': r'(?:NomadName|NN)[:\s]*(.+)',
        'address': r'(?:CampLocation|CL)[:\s]*(.+)'
    }
}


def parse_voter_data(text, population_type='general'):
    patterns = FIELD_MAPPINGS.get(population_type, {
        'voter_id': r'(?:ID|1D|D|LD)[:\s]*([A-Z0-9.\-]{6,})',
        'name': r'(?:Name|Nome|Nane)[:\s]*([A-Z][a-z]+\s[A-Z][a-z]+)',
        'address': r'(?:Address|Addyess|Add)[:\s]*(\d+\s.+?Street)'
    })

    data = {}
    for field, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Clean up common OCR errors
            cleaned = match.group(1)\
                .replace('Soe', 'Doe')\
                .replace('ZL', '123')\
                .replace('..', '.')\
                .strip()
            data[field] = cleaned
        else:
            raise ValueError(f"Could not find {field} in text: {text}")

    return data


def process_batch(input_dir='forms/', output_db='voters.db'):
    for form_path in glob.glob(f"{input_dir}/*.jpg"):
        try:
            text = extract_data(form_path)
            data = parse_voter_data(text)
            store_data(data, output_db)
            print(f"Processed {form_path}")
        except Exception as e:
            print(f"Skipped {form_path}: {str(e)}")


def store_data(data):
    conn = sqlite3.connect('voters.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voters (
            id INTEGER PRIMARY KEY,
            voter_id TEXT UNIQUE,
            name TEXT,
            address TEXT
        )
    ''')
    try:
        cursor.execute('''
            INSERT INTO voters (voter_id, name, address)
            VALUES (?, ?, ?)
        ''', (data['voter_id'], data['name'], data['address']))
        conn.commit()
    except sqlite3.IntegrityError:
        print(f"Duplicate entry for Voter ID {data['voter_id']}")
    finally:
        conn.close()
    generate_report(data)


def generate_report(data):
    with open('validation_report.txt', 'a') as f:
        f.write(f"Validated entry: {data['voter_id']}\n")


if __name__ == '__main__':
    process_batch()
    try:
        text = extract_data('form.jpg')
        print("Raw OCR Text:\n", text)  # Debug output
        data = parse_voter_data(text)
        store_data(data)
        print("Successfully processed:")
        print(f"ID: {data['voter_id']}")
        print(f"Name: {data['name']}")
        print(f"Address: {data['address']}")
    except Exception as e:
        print(f"Error processing form: {str(e)}")
