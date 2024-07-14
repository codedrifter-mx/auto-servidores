import glob
import hashlib
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests

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


def process_person_data(name, rfc, collName):
    try:
        session = setup_session()
        person_result = search_person(session, rfc, collName)
        if person_result and person_result['estatus'] and person_result['datos']:
            person_data = person_result['datos'][0]
            declaration_result = get_declaration_history(session, person_data['idUsrDecnet'], collName)
            if declaration_result:
                for declaration in declaration_result['datos']:
                    if (declaration['anio'] == 2024 and declaration['tipoDeclaracion'] == 'MODIFICACION' and
                            declaration['institucionReceptora'] == 'INSTITUTO MEXICANO DEL SEGURO SOCIAL'):
                        return {'Name': name, 'RFC': rfc, 'noComprobante': declaration['noComprobante'],
                                'Status': 'Found'}
        return {'Name': name, 'RFC': rfc, 'Status': 'Not found'}
    except:
        return {'Name': name, 'RFC': rfc, 'Status': 'Not found'}
        pass


def main(seed_filename):
    # Load names and RFCs from Excel
    names_df = pd.read_excel(seed_filename)
    results = []

    # Process each person in the list concurrently
    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(process_person_data, row.iloc[0].upper().strip().replace('/', ' '), row.iloc[1],
                                   collName=100) for index, row in names_df.iterrows()]
        for future in as_completed(futures):
            results.append(future.result())

    # Split results into found and not found
    found = [r for r in results if r.get('Status') != 'Not found' and r.get('Status') != 'Error']
    not_found = [r for r in results if r.get('Status') == 'Not found' or r.get('Status') == 'Error']

    # Filter columns
    found_filtered = [{'Name': r['Name'], 'RFC': r['RFC'], 'noComprobante': r['noComprobante']} for r in found]
    not_found_filtered = [{'Name': r['Name'], 'RFC': r['RFC']} for r in not_found]

    # Filter columns and save results to Excel
    pd.DataFrame(found_filtered).to_excel(f'{os.path.splitext(os.path.basename(seed_filename))[0]}_ENCONTRADOS.xlsx',
                                          index=False)
    pd.DataFrame(not_found_filtered).to_excel(
        f'{os.path.splitext(os.path.basename(seed_filename))[0]}_NO_ENCONTRADOS.xlsx', index=False)


if __name__ == "__main__":
    logging.info("Starting data processing")
    seed_files = glob.glob('seed/*.xlsx')  # Assuming seed files are in 'seed/' directory
    for seed_file in seed_files:
        logging.info(f"Processing seed file: {seed_file}")
        main(seed_file)
    logging.info("All data processing completed.")
