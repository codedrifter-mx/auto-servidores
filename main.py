import datetime
from multiprocessing import Manager
from multiprocessing.context import Process
from multiprocessing.spawn import freeze_support
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
import threading
import os
import pandas as pd
import time
import re
import PyPDF2
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

APP_PATH = os.path.dirname(os.path.realpath(__file__))
CHROMEDRIVER_PATH = APP_PATH + "\\chromedriver.exe"
DOWNLOAD_PATH = APP_PATH + "\\declaraciones"

threadLocal = threading.local()

def main_workflow(num_proc):
    names_df = pd.read_excel('seed.xlsx')

    # Extract the data from the first column and convert it to a list
    names_df.iloc[:, 0] = names_df.iloc[:, 0].str.upper().str.strip().replace('/', ' ')

    # Extract the cleaned data as a list
    names_list = names_df.iloc[:, 0].tolist()

    # names_df['fullname'] = names_df['fullname'].str.upper().str.strip().replace('/', ' ')
    # names_list = list(names_df['fullname'])

    processes = []
    not_founded = manager.list()  # <-- can be shared between processes.
    founded = manager.list()  # <-- can be shared between processes.
    founded_name = manager.list()  # <-- can be shared between processes.
    founded_email = manager.list()  # <-- can be shared between processes.
    founded_phone = manager.list()  # <-- can be shared between processes.
    founded_ext = manager.list()  # <-- can be shared between processes.

    names_chunks = chunkList(names_list, num_proc)

    # multiprocesses
    for names_chunk in names_chunks:
        p = Process(target=sub_workflow,
                    args=(names_chunk, not_founded, founded, founded_name, founded_email, founded_phone, founded_ext))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

    # print count of each list
    print("+++++ No encontradas: " + str(len(list(not_founded))))
    print("+++++ Encontradas: " + str(len(list(founded))))
    print("+++++ Nombre: " + str(len(list(founded_name))))
    print("+++++ Email: " + str(len(list(founded_email))))
    print("+++++ Tel: " + str(len(list(founded_phone))))
    print("+++++ Ext: " + str(len(list(founded_ext))))

    # once finished all processes, save data
    not_founded_df = pd.DataFrame(list(not_founded), columns=['RFC'])
    founded_df = pd.DataFrame(list(founded), columns=['RFC'])

    # Save data to Excel
    not_founded_df.to_excel('NO_ENCONTRADAS.xlsx', index=False)
    founded_df.to_excel('ENCONTRADAS.xlsx', index=False)

    print("Workflow completed.")


def sub_workflow(names, not_founded, founded, founded_name, founded_email, founded_phone, founded_ext):
    driver = get_driver()
    for fullname in names:
        try:
            driver.get("https://servidorespublicos.gob.mx")

            WebDriverWait(driver, 5).until(expected_conditions.visibility_of_element_located(
                (By.NAME, "nombre")))

            fullname_input = driver.find_element(By.NAME, "nombre")
            fullname_input.send_keys(fullname)

            btn_search_fullname = driver.find_element(By.XPATH,
                                                      "/html/body/app-root/app-busqueda/div/div[3]/div/div/form/div/div/div[1]/div[2]/button")

            driver.execute_script('arguments[0].removeAttribute("disabled");', btn_search_fullname)
            driver.execute_script("arguments[0].click();", btn_search_fullname)
        except Exception as e:
            not_founded.append(fullname)
            print("-- Error de busqueda con " + fullname)
            # print(e)
            continue

        try:
            WebDriverWait(driver, 4).until(expected_conditions.visibility_of_element_located(
                (By.XPATH, "/html/body/app-root/app-busqueda/div/div[4]/div/table/tbody/tr/td[1]")))

            xpath_selected = "/html/body/app-root/app-busqueda/div/div[4]/div/table/tbody/tr[1]/td[1]/a"

            link_selected = driver.find_element(By.XPATH, xpath_selected)
            driver.execute_script("arguments[0].click();", link_selected)

        except Exception as e:
            not_founded.append(fullname)
            print("-- Nombre o dependencia de " + fullname + " no encontrado")
            # print(e)
            continue

        try:
            # Espero a que aparezca texto a base xpath
            WebDriverWait(driver, 5).until(expected_conditions.visibility_of_element_located(
                (By.XPATH, "/html/body/app-root/app-declaraciones/div[3]/div/table/tbody/tr/td[2]")))

            # Localizo TODOS los textos a base de xpath
            textos_persona = driver.find_elements(By.XPATH,
                                                  '/html/body/app-root/app-declaraciones/div[3]/div/table/tbody/tr/td[2]')

            xpath_download_btn = ""
            xpath_no_comprobante = ""

            is_showed = False
            # Recorrer textos pero con su indice, para saber cual boton
            for index, texto in enumerate(textos_persona):
                # Get the current year
                current_year = datetime.datetime.now().year

                # Create the string with the current year
                search_string = f"MODIFICACIÓN {current_year}"
                if texto.text == search_string:
                    is_showed = True

                    xpath_download_btn = "/html/body/app-root/app-declaraciones/div[3]/div/table/tbody/tr[" + str(
                        index + 1) + "]/td[5]/a/i"

                    xpath_no_comprobante = "/html/body/app-root/app-declaraciones/div[3]/div/table/tbody/tr[" + str(
                        index + 1) + "]/td[3]"

                    break
            if not xpath_download_btn or not xpath_no_comprobante:
                raise Exception("Required elements not found on the page.")

        except Exception as e:
            not_founded.append(fullname)
            print("-- Archivo de " + fullname + " no encontrado")
            # print(e)
            continue

        try:

            no_comprobante = driver.find_element(By.XPATH, xpath_no_comprobante)

            no_comprobante_string = no_comprobante.text
            download_dir_temp = DOWNLOAD_PATH + "\\" + fullname

            # Assuming the downloaded file has a .pdf extension
            pdf_file_path = os.path.join(download_dir_temp, no_comprobante_string + '.pdf')

            # check if the file is downloaded or not
            while not os.path.exists(pdf_file_path):
                # Cambio direccion de descarga del chromedrive con el nombre de la persona
                driver.command_executor._commands["send_command"] = (
                    "POST", '/session/$sessionId/chromium/send_command')
                params = {'cmd': 'Page.setDownloadBehavior',
                          'params': {'behavior': 'allow', 'downloadPath': download_dir_temp}}
                driver.execute("send_command", params)

                # Localizo boton documento con xpath
                btn_download_file = driver.find_element(By.XPATH, xpath_download_btn)
                driver.execute_script("arguments[0].click();", btn_download_file)

                time.sleep(3)
                WebDriverWait(driver, 5).until(
                    expected_conditions.element_to_be_clickable((By.XPATH, '//*[@id="download"]')))

                button_descargar = driver.find_element(By.XPATH, '//*[@id="download"]')
                button_descargar.click()

                time.sleep(2)

            founded.append(fullname)
            print("++" + fullname + " exitoso")

            # Open the PDF file
            with open(pdf_file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                num_pages = len(reader.pages)

                # search_strings = ['NOMBRE(S):', 'CORREO ELECTRÓNICO INSTITUCIONAL:', 'TELÉFONO DE OFICINA Y EXTENSIÓN:']
                search_strings = ['NOMBRE(S):', 'CORREO ELECTRÓNICO INSTITUCIONAL:']

                page = reader.pages[0]
                text = page.extract_text()

                flag = False
                for search_string in search_strings:
                    if search_string in text:
                        # Get the next string after the search string
                        next_string_index = text.index(search_string) + len(search_string)

                        # Perform the validations
                        if search_string == 'NOMBRE(S):':
                            next_string = text[next_string_index:]
                            next_string = next_string.splitlines()[0].strip()
                            next_string = next_string[next_string.find('\n') + 1:].strip()
                            if re.match(r'^[A-Za-z ]+$', next_string):
                                # print(f"Valid name '{next_string}'")
                                founded_name.append(next_string)
                            else:
                                # print(f"Invalid name format on page {page_num + 1}")
                                founded_name.append('X')

                        elif search_string == 'CORREO ELECTRÓNICO INSTITUCIONAL:':
                            next_string = text[next_string_index:]
                            next_string = next_string.splitlines()[0].strip()
                            next_string = next_string[next_string.find('\n') + 1:].strip()

                            if re.match(r'^[\w.-]+@[\w.-]+$', next_string):
                                # print(f"Valid email '{next_string}'")
                                founded_email.append(next_string)
                            else:
                                # print(f"Invalid email format on page {page_num + 1}")
                                founded_email.append('X')

                        elif search_string == 'TELÉFONO DE OFICINA Y EXTENSIÓN:':

                            pattern = r'\n\d{4}-\d{2}-\d{2}\n(\d+)'
                            match = re.search(pattern, text)

                            if match:
                                phone_number = match.group(1)

                                # Check if phone_number is a valid number and not separated by spaces
                                if re.match(r'^\d+$', phone_number) and ' ' not in phone_number:
                                    founded_phone.append(phone_number)

                                    next_string_index = text.index(phone_number)
                                    next_string = text[next_string_index:]
                                    next_string = next_string.splitlines()[0].strip()
                                    next_string = next_string[next_string.find('\n') + 1:].strip()
                                    next_string_parts = next_string.split(' ')

                                    if len(next_string_parts) > 1 and next_string_parts[1].isdigit():
                                        founded_ext.append(next_string_parts[1])
                                        print(next_string_parts[1])
                                    else:
                                        founded_ext.append('X')
                                else:
                                    founded_ext.append('X')



        except Exception as e:
            print("!!++ Hubo un error al descargar el archivo, pero si esta en la plataforma: " + fullname)
            founded.append(fullname)
            print(e)
            pass

    print("Termine! +++")


def chunkList(list, num):
    avg = len(list) / float(num)
    out = []
    last = 0.0

    while last < len(list):
        out.append(list[int(last):int(last + avg)])
        last += avg

    return out




def get_driver():
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_experimental_option('prefs', {
        "download.default_directory": DOWNLOAD_PATH,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing_for_trusted_sources_enabled": False,
        "safebrowsing.enabled": False,
        'profile.default_content_setting_values.automatic_downloads': 1
    })
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument("--headless")

    try:
        # Specify a path with write permissions
        service = Service(ChromeDriverManager().install())
        driverobj = webdriver.Chrome(service=service, options=chrome_options)
        return driverobj
    except Exception as e:
        print("Failed to initialize the Chrome driver:", str(e))
        return None


if __name__ == '__main__':
    driver = get_driver()
    if driver:
        try:
            freeze_support()
            manager = Manager()

            # let's go
            main_workflow(1)
            pass
        finally:
            driver.quit()