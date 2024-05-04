import time

import requests
import json
import hashlib
import base64
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_session():
    session = requests.Session()
    session.headers.update({'Content-Type': 'application/json'})
    return session

def search_person(session, name, collName):
    url = f'https://servicios.dn.funcionpublica.gob.mx/declaranet/consulta-servidores-publicos/buscarsp?busqueda={name}&collName={collName}'
    response = session.post(url)
    return response.json()

def get_declaration_history(session, idUsrDecnet, collName):
    url = f'https://servicios.dn.funcionpublica.gob.mx/declaranet/consulta-servidores-publicos/historico?idUsrDecnet={idUsrDecnet}&collName={collName}'
    response = session.post(url)
    return response.json()

def generate_sha3_digest(declaracion):
    declaracion_json = json.dumps(declaracion, separators=(',', ':'))
    hash_object = hashlib.sha3_512()
    hash_object.update(declaracion_json.encode())
    return hash_object.hexdigest()

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
            return True
        elif response.status_code == 504:
            logging.warning(f"Attempt {attempts + 1}: Failed to download PDF for {name} due to a 504 error. Retrying...")
            time.sleep(2 ** attempts)  # Exponential backoff
            attempts += 1
        else:
            logging.error(f"Failed to download PDF for {name}. HTTP status: {response.status_code}")
            return False
    logging.error(f"Failed to download PDF for {name} after multiple retries. Giving up.")
    return False

def process_person_data(name, collName):
    session = setup_session()
    person_result = search_person(session, name, collName)
    if person_result['estatus'] and person_result['datos']:
        person_data = person_result['datos'][0]
        declaration_result = get_declaration_history(session, person_data['idUsrDecnet'], collName)
        if declaration_result['estatus']:
            for declaration in declaration_result['datos']:
                if declaration['tipoDeclaracion'] == 'MODIFICACION' and declaration['anio'] == 2024:
                    return download_declaration(name, session, declaration), name
    return False, name

def main():
    # Load names from Excel
    names_df = pd.read_excel('seed.xlsx')
    names_list = names_df.iloc[:, 0].apply(lambda x: x.upper().strip().replace('/', ' ')).tolist()
    found = []
    not_found = []

    # Process each person in the list concurrently
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_person_data, name, 100) for name in names_list]
        for future in as_completed(futures):
            result, name = future.result()
            if result:
                found.append([name])
            else:
                not_found.append([name])

    # Save results to Excel
    pd.DataFrame(found, columns=['Nombre']).to_excel('ENCONTRADOS.xlsx', index=False)
    pd.DataFrame(not_found, columns=['Nombre']).to_excel('NOT_ENCONTRADOS.xlsx', index=False)

    logging.info("All data processing completed.")

if __name__ == "__main__":
    main()
