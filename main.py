import threading
import time
import requests
import wget
import zipfile
import os
import requests
import numpy as np
import xlsxwriter
import os

from multiprocessing import Manager
from multiprocessing.context import Process
from multiprocessing.spawn import freeze_support
from selenium import webdriver
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.chrome.options import Options
from xlrd import open_workbook
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By

path_del_proyecto = os.path.realpath(__file__)
directorio_del_proyecto = os.path.dirname(path_del_proyecto)
chromedriver = directorio_del_proyecto + "\\chromedriver.exe"
download_dir = directorio_del_proyecto + "\\declaraciones"

def automatizar_descargas():
    book = open_workbook("seed.xlsx")
    sheet = book.sheet_by_index(0)  # If your data is on sheet 1
    columna_nombres = []
    for row in range(1, sheet.nrows):  # start from 1, to leave out row 0
        name = " ".join(str(sheet.row_values(row)[0]).upper().strip().split()).replace('/', ' ')
        columna_nombres.append(name)  # extract from zero col

    lista_personas_no_encontradas = list()  # <-- can be shared between processes.
    lista_personas_encontradas = list()  # <-- can be shared between processes.

    # nombres = chunkIt(columna_nombres,3)
    nombres = columna_nombres


    processes = []

    for nombre in nombres:
        descargar_archivos_persona(nombres, lista_personas_no_encontradas, lista_personas_encontradas)
        # p = Process(target=descargar_archivos_persona,
        #             args=(nombre, lista_personas_no_encontradas, lista_personas_encontradas))  # Passing the list
        # p.start()
        # processes.append(p)
    # for p in processes:
    #     p.join()\

    with xlsxwriter.Workbook('NO_ENCONTRADAS.xlsx') as workbook:
        worksheet = workbook.add_worksheet()
        worksheet.write_column('A1', lista_personas_no_encontradas)

    with xlsxwriter.Workbook('ENCONTRADAS.xlsx') as workbook:
        worksheet = workbook.add_worksheet()
        worksheet.write_column('A1', lista_personas_encontradas)

    # done
    print("+++++++++++++++++ Descargas terminadas!!!!!")


def descargar_archivos_persona(nombres, lista_personas_no_encontradas, lista_personas_encontradas):
    driver = get_driver()
    driver.get("http://servidorespublicos.gob.mx")

    # WebDriverWait(driver, 5).until(expected_conditions.element_to_be_clickable(
    #     (By.XPATH, "/html/body/app-root/app-busqueda/div/div[4]/div/div/div[3]/button")))
    #
    # button_aviso = driver.find_element_by_xpath(
    #     "/html/body/app-root/app-busqueda/div/div[4]/div/div/div[3]/button")
    # driver.execute_script("arguments[0].click();", button_aviso)

    # try:
    for nombre in nombres:

        try:
            driver.get("https://servidorespublicos.gob.mx")

            WebDriverWait(driver, 3).until(expected_conditions.element_to_be_clickable(
                (By.NAME, "nombre")))

            input_nombre = driver.find_element_by_name("nombre")
            input_nombre.send_keys(nombre)

            btn_buscar = driver.find_element_by_xpath(
                "/html/body/app-root/app-busqueda/div/div[3]/div/div/form/div/div/div[1]/div[2]/button")
            driver.execute_script('arguments[0].removeAttribute("disabled");', btn_buscar)
            driver.execute_script("arguments[0].click();", btn_buscar)
        except:
            lista_personas_no_encontradas.append(nombre)
            print("-- Error de busqueda con " + nombre)
            continue

        try:
            WebDriverWait(driver, 3).until(expected_conditions.visibility_of_element_located(
                (By.XPATH, "/html/body/app-root/app-busqueda/div/div[4]/div/table/tbody/tr/td[1]")))

            nombre_personas = driver.find_elements_by_xpath(
                '/html/body/app-root/app-busqueda/div/div[4]/div/table/tbody/tr/td[1]')

            nombre_institutos = driver.find_elements_by_xpath(
                '/html/body/app-root/app-busqueda/div/div[4]/div/table/tbody/tr/td[2]')

            xpath_link_persona = ""

            for indice_dos, instituto in enumerate(nombre_institutos):
                if (instituto.text.upper() == "INSTITUTO MEXICANO DEL SEGURO SOCIAL" or instituto.text == "Instituto Mexicano del Seguro Social"):
                    if nombre_personas[indice_dos].text.upper() == nombre.upper():
                        xpath_link_persona = "/html/body/app-root/app-busqueda/div/div[4]/div/table/tbody/tr[" + str(
                            indice_dos + 1) + "]/td[1]/a"

            link_persona = driver.find_element_by_xpath(xpath_link_persona)
            driver.execute_script("arguments[0].click();", link_persona)

        except:
            lista_personas_no_encontradas.append(nombre)
            print(" - Link o dependencia de " + nombre + " no encontrado")
            continue

        try:
            # Espero a que aparezca texto a base xpath
            WebDriverWait(driver, 3).until(expected_conditions.visibility_of_element_located(
                (By.XPATH, "/html/body/app-root/app-declaraciones/div[3]/div/table/tbody/tr/td[2]")))

            # Localizo TODOS los textos a base de xpath
            textos_persona = driver.find_elements_by_xpath(
                '/html/body/app-root/app-declaraciones/div[3]/div/table/tbody/tr/td[2]')

            xpath_button_archivo = ""

            bandera = False
            # Recorrer textos pero con su indice, para saber cual boton
            for indice, texto in enumerate(textos_persona):
                if texto.text == "MODIFICACIÓN 2022":
                    bandera = True
                    break

            if bandera:
                lista_personas_encontradas.append(nombre)
                print("++ " + nombre + " exitoso")
            else:
                lista_personas_no_encontradas.append(nombre)
                print("-- " + nombre + " no 2022")

            # # Cambio direccion de descarga del chromedrive con el nombre de la persona
            # download_dir_temp = download_dir + "\\" + nombre
            # driver.command_executor._commands["send_command"] = (
            #     "POST", '/session/$sessionId/chromium/send_command')
            # params = {'cmd': 'Page.setDownloadBehavior',
            #           'params': {'behavior': 'allow', 'downloadPath': download_dir_temp}}
            # driver.execute("send_command", params)

            # # Localizo boton documento con xpath
            # button_documento = driver.find_element_by_xpath(xpath_button_archivo)
            # driver.execute_script("arguments[0].click();", button_documento)
            return
        except:
            lista_personas_no_encontradas.append(nombre)
            print("-- Archivo de " + nombre + " no encontrado")
            continue
        #
        # try:
        #     # time.sleep(3)
        #     # WebDriverWait(driver, 5).until(
        #     #     expected_conditions.element_to_be_clickable((By.XPATH, '//*[@id="download"]')))
        #     #
        #     # button_descargar = driver.find_element_by_xpath('//*[@id="download"]')
        #     # button_descargar.click()
        #     #
        #     # time.sleep(2)
        #     #
        #     lista_personas_encontradas.append(nombre)
        #     print("++" + nombre + " exitoso")
        # except Exception as e:
        #     print("!!++ Hubo un error al descargar el archivo, pero si esta en la plataforma: " + nombre)
        #     lista_personas_encontradas.append(nombre)
        #     print()
        #     pass

    print("Termine! +++")
    # except Exception as e:
    #     print("HUBO UN ERROR MUY GRANDE")
    #     print(e)


def chunkIt(seq, num):
    avg = len(seq) / float(num)
    out = []
    last = 0.0

    while last < len(seq):
        out.append(seq[int(last):int(last + avg)])
        last += avg

    return out


threadLocal = threading.local()


def get_driver():
    # url = 'https://chromedriver.storage.googleapis.com/LATEST_RELEASE'
    # response = requests.get(url)
    # version_number = response.text
    #
    # # build the donwload url
    # download_url = "https://chromedriver.storage.googleapis.com/" + version_number + "/chromedriver_win32.zip"
    #
    # # download the zip file using the url built above
    # latest_driver_zip = wget.download(download_url, 'chromedriver.zip')
    #
    # # extract the zip file
    # with zipfile.ZipFile(latest_driver_zip, 'r') as zip_ref:
    #     zip_ref.extractall()  # you can specify the destination folder path here
    # # delete the zip file downloaded above
    # os.remove(latest_driver_zip)
    #
    # driver = getattr(threadLocal, 'driver', None)
    # if driver is None:
    #     chrome_options = Options()
    #     chrome_options.add_experimental_option('prefs', {
    #         "download.default_directory": download_dir,
    #         "download.prompt_for_download": False,
    #         "download.directory_upgrade": True,
    #         "safebrowsing_for_trusted_sources_enabled": False,
    #         "safebrowsing.enabled": False,
    #         'profile.default_content_setting_values.automatic_downloads': 1
    #     })
    #     chrome_options.add_argument('--no-sandbox')
    #     # chrome_options.add_argument("--headless")
    #
    #     driver = webdriver.Chrome(options=chrome_options, executable_path=chromedriver)

    chrome_options = Options()
    chrome_options.add_experimental_option('prefs', {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing_for_trusted_sources_enabled": False,
        "safebrowsing.enabled": False,
        'profile.default_content_setting_values.automatic_downloads': 1
    })
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument("--headless")

    driver = webdriver.Chrome(options=chrome_options, executable_path=chromedriver)

    return driver


if __name__ == '__main__':
    freeze_support()
    manager = Manager()
    automatizar_descargas()
