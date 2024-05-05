import time
import requests
import json
import hashlib
import base64
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import PyPDF2

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def setup_session():
    session = requests.Session()
    session.headers.update({'Content-Type': 'application/json'})
    return session


def search_person(session, name, collName):
    url = f'https://servicios.dn.funcionpublica.gob.mx/declaranet/consulta-servidores-publicos/buscarsp?busqueda={name}&collName={collName}'
    response = session.post(url)
    if response.status_code != 200:
        return None
    return response.json()


def get_declaration_history(session, idUsrDecnet, collName):
    url = f'https://servicios.dn.funcionpublica.gob.mx/declaranet/consulta-servidores-publicos/historico?idUsrDecnet={idUsrDecnet}&collName={collName}'
    response = session.post(url)
    if response.status_code != 200:
        return None
    return response.json()


def generate_sha3_digest(declaracion):
    declaracion_json = json.dumps(declaracion, separators=(',', ':'))
    hash_object = hashlib.sha3_512()
    hash_object.update(declaracion_json.encode())
    return hash_object.hexdigest()


def extract_metadata(pdf_file_path):
    with open(pdf_file_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        page = reader.pages[0]
        text = page.extract_text()
        results = {'Name': '', 'Email': '', 'Phone': '', 'Extension': ''}

        search_strings = {
            'NOMBRE(S):': 'Name',
            'CORREO ELECTRÓNICO INSTITUCIONAL:': 'Email',
            'TELÉFONO DE OFICINA Y EXTENSIÓN:': 'Phone'
        }

        for search_string, key in search_strings.items():
            if search_string in text:
                start_index = text.index(search_string) + len(search_string)
                next_string = text[start_index:].splitlines()[0].strip()
                results[key] = next_string

        return results


def download_declaration(name, session, declaration):
    digitoVerificador = generate_sha3_digest(declaration)
    url = 'https://servicios.dn.funcionpublica.gob.mx/declaranet/consulta-servidores-publicos/consulta-declaracion'
    payload = {
        "declaracion": declaration,
        "digitoVerificador": digitoVerificador
    }
    attempts = 0
    while attempts < 3:  # Max number of attempts
        response = session.post(url, json=payload)
        if response.status_code == 200:
            pdf_data = base64.b64decode(response.text)
            os.makedirs('declaraciones', exist_ok=True)
            file_path = os.path.join('declaraciones', f'{name}_{declaration["anio"]}.pdf')
            with open(file_path, 'wb') as f:
                f.write(pdf_data)
            logging.info(f"PDF downloaded and saved to {file_path}")
            return extract_metadata(file_path)
        elif response.status_code == 504:
            logging.warning(
                f"Attempt {attempts + 1}: Failed to download PDF for {name} due to a 504 error. Retrying...")
            time.sleep(2 ** attempts)  # Exponential backoff
            attempts += 1
        else:
            logging.error(f"Failed to download PDF for {name}. HTTP status: {response.status_code}")
            return {'Name': name, 'Status': 'Error', 'Details': f'HTTP status: {response.status_code}'}
    logging.error(f"Failed to download PDF for {name} after multiple retries. Giving up.")
    return {'Name': name, 'Status': 'Error', 'Details': 'Multiple retries failed'}


def process_person_data(name, collName):
    session = setup_session()
    person_result = search_person(session, name, collName)
    if person_result and person_result['estatus'] and person_result['datos']:
        person_data = person_result['datos'][0]
        declaration_result = get_declaration_history(session, person_data['idUsrDecnet'], collName)
        if declaration_result and declaration_result['estatus']:
            for declaration in declaration_result['datos']:
                metadata = download_declaration(name, session, declaration)
                if metadata:
                    return metadata
    return {'Name': name, 'Status': 'Not found', 'Details': 'No data available or validation failed'}


def main():
    # Load names from Excel
    names_df = pd.read_excel('seed.xlsx')
    names_list = names_df.iloc[:, 0].apply(lambda x: x.upper().strip().replace('/', ' ')).tolist()
    results = []

    # Process each person in the list concurrently
    with ThreadPoolExecutor(max_workers=300) as executor:
        futures = [executor.submit(process_person_data, name, collName=100) for name in names_list]
        for future in as_completed(futures):
            results.append(future.result())

    # Split results into found and not found
    found = [r for r in results if r.get('Status') != 'Not found' and r.get('Status') != 'Error']
    not_found = [r for r in results if r.get('Status') == 'Not found' or r.get('Status') == 'Error']

    # Save results to Excel
    pd.DataFrame(found).to_excel('ENCONTRADOS.xlsx', index=False)
    pd.DataFrame(not_found).to_excel('NOT_ENCONTRADOS.xlsx', index=False)

    logging.info("All data processing completed.")


if __name__ == "__main__":
    main()
