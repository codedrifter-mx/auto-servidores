from multiprocessing import Manager
from multiprocessing.context import Process
from multiprocessing.spawn import freeze_support
from selenium import webdriver
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
import threading
import zipfile
import requests
import wget
import os
import pandas as pd
import time

APP_PATH = os.path.dirname(os.path.realpath(__file__))
CHROMEDRIVER_PATH = APP_PATH + "\\chromedriver.exe"
DOWNLOAD_PATH = APP_PATH + "\\declaraciones"

threadLocal = threading.local()

def main_workflow(num_proc):
    names_df = pd.read_excel("seed.xlsx", names=['fullname'])
    names_df['fullname'] = names_df['fullname'].str.upper().str.strip().replace('/', ' ')
    names_list = list(names_df['fullname'])

    processes = []
    not_founded = manager.list()  # <-- can be shared between processes.
    founded = manager.list()  # <-- can be shared between processes.

    names_chunks = chunkList(names_list, num_proc)

    # multiprocesses
    for names_chunk in names_chunks:
        p = Process(target=sub_workflow,
                    args=(names_chunk, not_founded, founded))
        p.start()
        processes.append(p)
    for p in processes:
        p.join()

    # once finished all processes, save data

    not_founded_df = pd.DataFrame(list(not_founded), columns=['fullname'])
    founded_df = pd.DataFrame(list(founded), columns=['fullname'])

    not_founded_df.to_excel('NO_ENCONTRADAS.xlsx', index=False)
    founded_df.to_excel('NO_ENCONTRADAS.xlsx', index=False)

    print("+++++ Fin del flujo de trabajo")


def sub_workflow(names, not_founded, founded):
    driver = get_driver()
    
    for fullname in names:
        try:
            driver.get("https://servidorespublicos.gob.mx")

            # WebDriverWait(driver, 5).until(expected_conditions.element_to_be_clickable(
            #     (By.XPATH, "/html/body/app-root/app-busqueda/div/div[4]/div/div/div[3]/button")))
            #
            # button_aviso = driver.find_element_by_xpath(
            #     "/html/body/app-root/app-busqueda/div/div[4]/div/div/div[3]/button")
            # driver.execute_script("arguments[0].click();", button_aviso)

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

            people_list = driver.find_elements(By.XPATH,
                '/html/body/app-root/app-busqueda/div/div[4]/div/table/tbody/tr/td[1]')

            institutes_list = driver.find_elements(By.XPATH,
                '/html/body/app-root/app-busqueda/div/div[4]/div/table/tbody/tr/td[2]')

            xpath_selected = ""

            for index, institute in enumerate(institutes_list):
                if institute.text.upper() == "INSTITUTO MEXICANO DEL SEGURO SOCIAL" or institute.text == "Instituto Mexicano del Seguro Social":
                    if people_list[index].text.upper() == fullname.upper():
                        xpath_selected = "/html/body/app-root/app-busqueda/div/div[4]/div/table/tbody/tr[" + str(
                            index + 1) + "]/td[1]/a"

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

            is_showed = False
            # Recorrer textos pero con su indice, para saber cual boton
            for index, texto in enumerate(textos_persona):
                if texto.text == "MODIFICACIÓN 2022":
                    is_showed = True

                    xpath_download_btn = "/html/body/app-root/app-declaraciones/div[3]/div/table/tbody/tr[" + str(index + 1) + "]/td[5]/a/i"

                    break

            if is_showed:
                # Cambio direccion de descarga del chromedrive con el nombre de la persona
                download_dir_temp = DOWNLOAD_PATH + "\\" + fullname
                driver.command_executor._commands["send_command"] = (
                    "POST", '/session/$sessionId/chromium/send_command')
                params = {'cmd': 'Page.setDownloadBehavior',
                          'params': {'behavior': 'allow', 'downloadPath': download_dir_temp}}
                driver.execute("send_command", params)

                # Localizo boton documento con xpath
                btn_download_file = driver.find_element(By.XPATH, xpath_download_btn)
                driver.execute_script("arguments[0].click();", btn_download_file)
            else:
                not_founded.append(fullname)
                print("-- " + fullname + " no MODIFICACIÓN 2022")
                continue

        except Exception as e:
            not_founded.append(fullname)
            print("-- Archivo de " + fullname + " no encontrado")
            # print(e)
            continue

        try:
            time.sleep(3)
            WebDriverWait(driver, 5).until(
                expected_conditions.element_to_be_clickable((By.XPATH, '//*[@id="download"]')))

            button_descargar = driver.find_element(By.XPATH, '//*[@id="download"]')
            button_descargar.click()

            time.sleep(2)

            founded.append(fullname)
            print("++" + fullname + " exitoso")
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
    url = 'https://chromedriver.storage.googleapis.com/LATEST_RELEASE'
    response = requests.get(url)
    version_number = response.text

    # build the donwload url
    download_url = "https://chromedriver.storage.googleapis.com/" + version_number + "/chromedriver_win32.zip"
    # download the zip file using the url built above
    latest_driver_zip = wget.download(download_url, 'chromedriver.zip')

    # extract the zip file
    try:
        with zipfile.ZipFile(latest_driver_zip, 'r') as zip_ref:
            zip_ref.extractall()    # you can specify the destination folder path here
    except:
        print('chromedriver.exe is in use, omitted .zip extraction')
    os.remove(latest_driver_zip)    # delete the zip file downloaded above

    # prepare Object for MultiProcess
    driver = getattr(threadLocal, 'driver', None)

    # Set config once
    if driver is None:
        chrome_options = Options()
        chrome_options.add_experimental_option('prefs', {
            "download.default_directory": DOWNLOAD_PATH,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing_for_trusted_sources_enabled": False,
            "safebrowsing.enabled": False,
            'profile.default_content_setting_values.automatic_downloads': 1
        })
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument("--headless")

        driver = webdriver.Chrome(options=chrome_options, executable_path=CHROMEDRIVER_PATH)

    return driver

if __name__ == '__main__':
    # This is needed for MultiProcesses
    freeze_support()
    manager = Manager()

    # let's go
    main_workflow(3)
