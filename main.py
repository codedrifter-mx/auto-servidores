import time

import xlsxwriter
import os

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
    for row in range(0, sheet.nrows):  # start from 1, to leave out row 0
        columna_nombres.append(str(sheet.row_values(row)[0]).upper())  # extract from zero col

    lista_personas_no_encontradas = []  # <-- can be shared between processes.
    lista_personas_encontradas = []  # <-- can be shared between processes.

    try:
        descargar_archivos_persona(columna_nombres, lista_personas_no_encontradas, lista_personas_encontradas)
    except:
        try:
            with xlsxwriter.Workbook('NO_ENCONTRADAS.xlsx') as workbook:
                worksheet = workbook.add_worksheet()
                worksheet.write_column('A1', lista_personas_no_encontradas)

            with xlsxwriter.Workbook('ENCONTRADAS.xlsx') as workbook:
                worksheet = workbook.add_worksheet()
                worksheet.write_column('A1', lista_personas_encontradas)
        except:
            print("No se guardaron los xlsx")
        print("Ocurrio algo grave :(")

    with xlsxwriter.Workbook('NO_ENCONTRADAS.xlsx') as workbook:
        worksheet = workbook.add_worksheet()
        worksheet.write_column('A1', lista_personas_no_encontradas)

    with xlsxwriter.Workbook('ENCONTRADAS.xlsx') as workbook:
        worksheet = workbook.add_worksheet()
        worksheet.write_column('A1', lista_personas_encontradas)

    # done
    print("Descargas terminadas, esperando 5 seg...")
    time.sleep(5)


def descargar_archivos_persona(nombres, lista_personas_no_encontradas, lista_personas_encontradas):
    # driver = get_driver()

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

    driver.get("https://servidorespublicos.gob.mx")

    WebDriverWait(driver, 3).until(expected_conditions.element_to_be_clickable(
        (By.XPATH, "/html/body/app-root/app-busqueda/div/div[4]/div/div/div[3]/button")))

    button_aviso = driver.find_element_by_xpath(
        "/html/body/app-root/app-busqueda/div/div[4]/div/div/div[3]/button")
    driver.execute_script("arguments[0].click();", button_aviso)

    # try:
    for nombre in nombres:
        driver.get("https://servidorespublicos.gob.mx")

        try:
            WebDriverWait(driver, 4).until(expected_conditions.element_to_be_clickable(
                (By.NAME, "nombre")))

            input_nombre = driver.find_element_by_name("nombre")
            input_nombre.send_keys(nombre)

            WebDriverWait(driver, 4).until(expected_conditions.element_to_be_clickable(
                (By.XPATH, "/html/body/app-root/app-busqueda/div/div[3]/div/div/form/div/div/div/div[2]/button")))

            btn_buscar = driver.find_element_by_xpath(
                "/html/body/app-root/app-busqueda/div/div[3]/div/div/form/div/div/div/div[2]/button")
            driver.execute_script("arguments[0].click();", btn_buscar)
        except:
            lista_personas_no_encontradas.append(nombre)
            print(" - Error de busqueda con " + nombre)
            continue

        try:
            WebDriverWait(driver, 5).until(expected_conditions.visibility_of_element_located(
                (By.XPATH, "/html/body/app-root/app-busqueda/div/div[4]/div/table/tbody/tr/td[1]")))

            nombre_personas = driver.find_elements_by_xpath(
                '/html/body/app-root/app-busqueda/div/div[4]/div/table/tbody/tr/td[1]')

            nombre_institutos = driver.find_elements_by_xpath(
                '/html/body/app-root/app-busqueda/div/div[4]/div/table/tbody/tr/td[2]')

            xpath_link_persona = ""

            for indice, texto in enumerate(nombre_personas):
                for indice_dos, instituto in enumerate(nombre_institutos):
                    if texto.text.upper() == nombre.upper() and (instituto.text.upper() == "INSTITUTO MEXICANO DEL SEGURO SOCIAL"):
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
            WebDriverWait(driver, 5).until(expected_conditions.visibility_of_element_located(
                (By.XPATH, "/html/body/app-root/app-declaraciones/div[3]/div/table/tbody/tr/td[2]")))

            # Localizo TODOS los textos a base de xpath
            textos_persona = driver.find_elements_by_xpath(
                '/html/body/app-root/app-declaraciones/div[3]/div/table/tbody/tr/td[2]')

            xpath_button_archivo = ""

            # Recorrer textos pero con su indice, para saber cual boton
            for indice, texto in enumerate(textos_persona):
                if texto.text == "MODIFICACIÓN 2020":
                    # print("Encontrado en indice: " + str(indice))
                    xpath_button_archivo = "/html/body/app-root/app-declaraciones/div[3]/div/table/tbody/tr[" + str(
                        indice + 1) + "]/td[5]/a"

            # Cambio direccion de descarga del chromedrive con el nombre de la persona
            download_dir_temp = download_dir + "\\" + nombre
            driver.command_executor._commands["send_command"] = (
            "POST", '/session/$sessionId/chromium/send_command')
            params = {'cmd': 'Page.setDownloadBehavior',
                      'params': {'behavior': 'allow', 'downloadPath': download_dir_temp}}
            driver.execute("send_command", params)

            # Localizo boton documento con xpath
            button_documento = driver.find_element_by_xpath(xpath_button_archivo)
            driver.execute_script("arguments[0].click();", button_documento)

        except:
            lista_personas_no_encontradas.append(nombre)
            print(" - Archivo de " + nombre + " no encontrado")
            continue

        try:
            time.sleep(3)
            WebDriverWait(driver, 10).until(
                expected_conditions.element_to_be_clickable((By.XPATH, '//*[@id="download"]')))

            button_descargar = driver.find_element_by_xpath('//*[@id="download"]')
            button_descargar.click()

            time.sleep(2)

            lista_personas_encontradas.append(nombre)
            print("++" + nombre + " exitoso")
        except Exception as e:
            print("!!++ Hubo un error al descargar el archivo, pero si esta en la plataforma: " + nombre)
            lista_personas_encontradas.append(nombre)
            print()
            pass

    print("Termine! +++")
        # except Exception as e:
        #     print("HUBO UN ERROR MUY GRANDE")
        #     print(e)



# def get_driver():
#     driver = getattr(threadLocal, 'driver', None)
#     if driver is None:
#         # inicializar chrome
#         chrome_options = Options()
#         chrome_options.add_experimental_option('prefs', {
#             "download.default_directory": download_dir,
#             "download.prompt_for_download": False,
#             "download.directory_upgrade": True,
#             "plugins.always_open_pdf_externally": True
#         })
#         chrome_options.add_argument("--headless")
#
#         driver = webdriver.Chrome(options=chrome_options, executable_path=chromedriver)
#     return driver


# def chunkIt(seq, num):
#     avg = len(seq) / float(num)
#     out = []
#     last = 0.0
#
#     while last < len(seq):
#         out.append(seq[int(last):int(last + avg)])
#         last += avg
#
#     return out


automatizar_descargas()



# def automatizar_descargas():
#     # Obtener lista de Excel
#     book = open_workbook("seed.xlsx")
#     sheet = book.sheet_by_index(0)  # If your data is on sheet 1
#     columna_nombres = []
#     for row in range(1, sheet.nrows):  # start from 1, to leave out row 0
#         columna_nombres.append(str(sheet.row_values(row)[13]).upper())  # extract from six col
#
#     # Recorrer nombres y descargar su archivo
#
#     with Manager() as manager:
#         lista_personas_no_encontradas = manager.list()  # <-- can be shared between processes.
#         lista_personas_encontradas = manager.list()  # <-- can be shared between processes.
#         columnas_de_nombres = chunkIt(columna_nombres, 2)
#
#         processes = []
#         for nombres in columnas_de_nombres:
#             p = Process(target=descargar_archivos_persona,
#                         args=(nombres, lista_personas_no_encontradas, lista_personas_encontradas))  # Passing the list
#             p.start()
#             processes.append(p)
#         for p in processes:
#             p.join()
#         print(lista_personas_encontradas)
#         print(lista_personas_no_encontradas)
#
#         with xlsxwriter.Workbook('NO_ENCONTRADAS.xlsx') as workbook:
#             worksheet = workbook.add_worksheet()
#             worksheet.write_column('A1', lista_personas_no_encontradas)
#
#         with xlsxwriter.Workbook('ENCONTRADAS.xlsx') as workbook:
#             worksheet = workbook.add_worksheet()
#             worksheet.write_column('A1', lista_personas_encontradas)
#
#         # done
#         print("Descargas terminadas, esperando 5 seg...")
#         time.sleep(5)
