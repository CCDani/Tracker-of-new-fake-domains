import os
import whois
import requests
from lxml import html
from zipfile import ZipFile
from flask import Flask, request, jsonify, render_template, send_file
import logging
import datetime
import tempfile

app = Flask(__name__)

# Configuración de logs
logging.basicConfig(level=logging.INFO)

BASE_URL = "https://www.whoisds.com/newly-registered-domains"
DOWNLOAD_PATH = "downloads"
EXTRACTED_PATH = "extracted"
COMBINED_FILE_PATH = os.path.join("static", "domain-names.txt")
PATTERNS_FILE = "patterns.txt"

def file_available(url):
    """Verifica si el archivo está disponible en la URL proporcionada."""
    response = requests.head(url)
    logging.info(f"Checking availability for {url} - Status code: {response.status_code}")
    return response.status_code == 200

def is_valid_zip(file_path):
    """Verifica si el archivo es un ZIP válido."""
    try:
        with ZipFile(file_path, 'r') as zip_ref:
            return True
    except:
        return False

def get_download_urls():
    response = requests.get(BASE_URL)
    response.raise_for_status()
    tree = html.fromstring(response.content)
    rows = tree.xpath('//tr')
    urls_and_dates = []

    for row in rows:
        date = row.xpath('./td[1]/text()')
        link = row.xpath('.//a[@href and contains(@href, "/whois-database/newly-registered-domains/")]/@href')
        if date and link:
            full_url = "https://www.whoisds.com" + link[0] if not link[0].startswith("http") else link[0]
            urls_and_dates.append((full_url, date[0].strip()))
    
    logging.info(f"Download URLs and dates: {urls_and_dates}")
    return urls_and_dates[:4]

def download_files(urls_and_dates):
    if not os.path.exists(DOWNLOAD_PATH):
        os.makedirs(DOWNLOAD_PATH)
    file_paths = []
    dates = []
    not_available_dates = []
    for url, date in urls_and_dates:
        if file_available(url):
            response = requests.get(url)
            response.raise_for_status()
            file_name = os.path.join(DOWNLOAD_PATH, url.split('/')[-2] + '.zip')
            with open(file_name, 'wb') as f:
                f.write(response.content)
            if is_valid_zip(file_name):
                file_paths.append(file_name)
                dates.append(date)
            else:
                logging.warning(f"Invalid ZIP file: {file_name}")
                not_available_dates.append(date)
        else:
            not_available_dates.append(date)
    logging.info(f"Downloaded files: {file_paths}")
    logging.info(f"Not available dates: {not_available_dates}")
    return file_paths, dates, not_available_dates

def extract_files(file_paths):
    if not os.path.exists(EXTRACTED_PATH):
        os.makedirs(EXTRACTED_PATH)
    extracted_files = []
    for idx, file_path in enumerate(file_paths):
        with ZipFile(file_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                extracted_file_name = f"extracted_{idx}_{member}"
                extracted_file_path = os.path.join(EXTRACTED_PATH, extracted_file_name)
                with open(extracted_file_path, 'wb') as extracted_file:
                    extracted_file.write(zip_ref.read(member))
                extracted_files.append(extracted_file_path)
    logging.info(f"Extracted files: {extracted_files}")
    return extracted_files

def combine_files(file_paths, output_file):
    line_count = 0
    with open(output_file, 'w', encoding='utf-8') as outfile:
        for file_path in file_paths:
            with open(file_path, 'r', encoding='utf-8') as infile:
                lines = infile.readlines()
                outfile.writelines(lines)
                line_count += len(lines)
                outfile.write("\n")
    logging.info(f"Total lines combined: {line_count}")
    return line_count

def download_and_combine_files(num_files=1):
    urls_and_dates = get_download_urls()
    downloaded_files, dates, not_available_dates = download_files(urls_and_dates[:num_files])
    if downloaded_files:
        extracted_files = extract_files(downloaded_files)
        line_count = combine_files(extracted_files, COMBINED_FILE_PATH)
    else:
        line_count = 0
    return dates, not_available_dates, line_count

@app.route('/')
def index():
    pattern_index = request.args.get('pattern', 0)
    domains, patterns = get_domains_by_pattern(pattern_index)
    return render_template("index.html", domains=domains, patterns=patterns, selected_pattern=pattern_index)

@app.route('/run-script', methods=['POST'])
def run_script():
    data = request.json
    num_files = int(data.get('days', 1))
    try:
        dates, not_available_dates, line_count = download_and_combine_files(num_files)
        message = "<br>".join([f"The database of day {date} was updated correctly." for date in dates])
        if not_available_dates:
            message += "<br>" + "<br>".join([f"The database of day {date} is not available yet." for date in not_available_dates])
        message += f"<br>[{line_count} domains]"
        logging.info(message)
        return jsonify({'success': message, 'dates': dates, 'not_available_dates': not_available_dates, 'line_count': line_count})
    except Exception as e:
        logging.error(f"Error updating database: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_domains')
def get_domains():
    pattern_index = request.args.get('pattern', 0)
    domains, _ = get_domains_by_pattern(pattern_index)
    return jsonify({'domains': domains})

@app.route('/search_domains')
def search_domains():
    query = request.args.get('query', '')
    domains = []
    if os.path.exists(COMBINED_FILE_PATH):
        with open(COMBINED_FILE_PATH, 'r', encoding='utf-8') as file:
            for line in file:
                if query.lower() in line.lower():
                    domains.append(line.strip())
    return jsonify({'domains': domains})

@app.route('/whois_lookup', methods=['GET'])
def whois_lookup():
    domain = request.args.get('domain', '')
    if not domain:
        return jsonify({'error': 'No domain provided'}), 400

    try:
        w = whois.whois(domain)
        return jsonify({
            'domain_name': w.domain_name,
            'registrar': w.registrar,
            'creation_date': w.creation_date,
            'expiration_date': w.expiration_date,
            'last_updated': w.updated_date,
            'status': w.status,
            'name_servers': w.name_servers
        })
    except Exception as e:
        logging.error(f"Error performing WHOIS lookup: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/whois_export', methods=['POST'])
def whois_export():
    data = request.json
    domains = data.get('domains', [])
    extended = data.get('extended', False)
    results = {}
    reliability_results = {}

    def check_registration_status(w):
        if w.domain_name:
            return "Is already registered"
        else:
            return "Is available\t"

    for domain in domains:
        try:
            w = whois.whois(domain)
            registration_status = check_registration_status(w)
            reliability_results[domain] = registration_status

            result = f"""
Registrar: {w.registrar}
Creation Date: {w.creation_date}
Expiration Date: {w.expiration_date}
Last Updated: {w.updated_date}
Status: {w.status}
Name Servers: {', '.join(w.name_servers or [])}
            """
            if extended:
                results[domain] = result
            else:
                results[domain] = f"{registration_status}\t{domain}"
        except Exception as e:
            reliability_results[domain] = "Error\t\t"
            if extended:
                results[domain] = f"Error: {str(e)}"
            else:
                results[domain] = f"Error\t\t{domain}"

    with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8', suffix='.txt') as reliability_file:
        current_pattern = ""
        for domain, status in reliability_results.items():
            pattern = get_pattern_from_domain(domain)
            if pattern != current_pattern:
                reliability_file.write(f"\n[+]____{pattern}____[+]\n")
                current_pattern = pattern
            reliability_file.write(f"{status}\t{domain}\n")
        reliability_file_path = reliability_file.name

    with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8', suffix='.txt') as whois_file:
        current_pattern = ""
        for domain, result in results.items():
            pattern = get_pattern_from_domain(domain)
            if pattern != current_pattern:
                whois_file.write(f"\n[+]____{pattern}____[+]\n")
                current_pattern = pattern
            whois_file.write(f"Domain: {domain}\n{result}\n{'='*40}\n")
        whois_file_path = whois_file.name

    return jsonify({
        'reliabilityFile': reliability_file_path,
        'whoisFile': whois_file_path,
    })

@app.route('/download', methods=['GET'])
def download():
    file_path = request.args.get('file')
    if file_path and os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return jsonify({'error': 'File not found'}), 404

def get_pattern_from_domain(domain):
    patterns = []
    if os.path.exists(PATTERNS_FILE):
        with open(PATTERNS_FILE, 'r', encoding='utf-8') as file:
            patterns.extend([line.strip() for line in file])
    for pattern in patterns:
        if pattern.lower() in domain.lower():
            return pattern
    return "unknown"

def get_domains_by_pattern(pattern):
    domains = []
    patterns = ["Select the pattern to find"]
    if os.path.exists(PATTERNS_FILE):
        with open(PATTERNS_FILE, 'r', encoding='utf-8') as file:
            patterns.extend([line.strip() for line in file])
    if os.path.exists(COMBINED_FILE_PATH):
        with open(COMBINED_FILE_PATH, 'r', encoding='utf-8') as file:
            for line in file:
                if int(pattern) != 0 and patterns[int(pattern)] in line:
                    domains.append(line.strip())
    return domains, patterns

if __name__ == '__main__':
    try:
        download_and_combine_files()
    except Exception as e:
        print(f"Error occurred: {e}")
    app.run(debug=True)
