from selenium import webdriver
from selenium.webdriver.chrome.options import Options 
from selenium.webdriver.chrome.service import Service 
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException
import pandas as pd
import fitz
import urllib
from alive_progress import alive_bar
import re
import time
import os
import html
from random import uniform
from selenium.webdriver.common.by import By
from urllib.parse import urlencode
import requests
from bs4 import BeautifulSoup

service = Service(executable_path=r"/usr/local/bin/chromedriver")

chrome_options = Options()
options = [
    "--disable-gpu",
    "--window-size=1920,1200",
    "--ignore-certificate-errors",
    "--disable-extensions",
    "--no-sandbox",
    "--disable-dev-shm-usage",
]
for option in options:
    chrome_options.add_argument(option)

driver = webdriver.Chrome(service=service, options=chrome_options)

def randsleep():
    time.sleep(uniform(0.5, 2.5))

           
if os.path.isfile("Reports.csv"):
    reports = pd.read_csv("Reports.csv")
    reports = reports.to_dict('records')

else:

    base_url = "https://www.cybenetics.com/"
    url = base_url + "index.php?option=database&params=2,1,"
    driver.get(url)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    table = soup.find(id="myTable")

    rows = table.find_all("tr")

    brands = []
    for r in rows:
        header = r.find("th")
        if header:
            link = header.find("a", href=True)
            if link:
                brands.append(base_url + link["href"])
     
    print("Fetching PSU report links...")
    reports = []
    with alive_bar(len(brands)) as bar:
        for i in brands:
            driver.get(i)
            try:
                table = soup.find(id="myTable")
                soup = BeautifulSoup(driver.page_source, "html.parser")
                table = soup.find(id="myTable")
                rows = table.find_all("tr")
                brandname = rows[0].find("th").text
            except (AttributeError, IndexError):
                time.sleep(2)
                table = soup.find(id="myTable")
                soup = BeautifulSoup(driver.page_source, "html.parser")
                table = soup.find(id="myTable")
                rows = table.find_all("tr")
                brandname = rows[0].find("th").text
            modelname = ""
            form_factor = ""
            rating = ""
            for r in rows:
                header = r.find("th")
                if header:
                    continue

                td = r.find_all("td")
                if len(td) > 8:
                    modelname = td[0].text
                    form_factor = td[1].text
                    rating = td[8].text
                else:
                    continue
                links = r.find_all("a")

                for a in links:
                    if a:
                        download = a.get("download")
                        if download:
                            if "SHORT" in a.text:
                                continue
                            link = base_url + a.get("href")
                            entry = {'Brand': brandname, 'Model': modelname, 'Form Factor': form_factor, 'Cybenetics Rating': rating, 'Report Link': link}
                            reports.append(entry)
            bar()


    reports = pd.DataFrame.from_dict(reports)
    reports.to_csv("Reports.csv", encoding="utf-8", index=False)


if os.path.isfile("ReportsPriced.csv"):
    reports = pd.read_csv("ReportsPriced.csv")
    reports = reports.to_dict('records')

else:
    print("Getting prices...")
    driver.get("https://geizhals.de/?cat=gehps")
    # Click on 'Accept cookies'
    try:
        cookie_accept = driver.find_element("id", "onetrust-accept-btn-handler")
        randsleep()
        cookie_accept.click()
    except NoSuchElementException:
        pass

    randsleep()
    for psu in reports:
        if re.match(".*(Sample|#\d+).*", psu["Model"]):
            price = None
        else:
            params = {
                    'cat': 'gehps',
                    'asuch' : psu["Brand"] + " " + psu["Model"],
                    'v': 'e',
                    'sort': 't',
                    'bl1_id': 30
                    }
            url = f"https://geizhals.de/?{urlencode(params)}"
            print(url)
            driver.get(url)
            randsleep()
            try:
                no_results = driver.find_element(By.CLASS_NAME, "category_list__empty-list")
                price = None
            except NoSuchElementException:
                randsleep()
                soup = BeautifulSoup(driver.page_source, "html.parser")
                price = soup.find("div", {"id": "product0"})\
                            .find("div", {"class": "cell productlist__price"})\
                            .find("span", {"class": "gh_price"}).find("span").text
            except:
                price = None

        psu["Lowest Price (Geizhals.de)"] = price

    reports = pd.DataFrame.from_dict(reports)
    reports.to_csv("ReportsPriced.csv", encoding="utf-8", index=False)


df = pd.DataFrame(columns=["Brand", "Model", "Form Factor", "Cybenetics Rating", "20W Efficiency", "40W Efficiency", "60W Efficiency", "80W Efficiency", "Report Link", "Lowest Price (Geizhals.de)"])
print("Fetching individual PSU data...")
with alive_bar(len(reports)) as bar:
    for psu in reports:
        response = requests.get(psu["Report Link"])
        with open('/tmp/downloaded_pdf.pdf', 'wb') as pdf_file:
                pdf_file.write(response.content)
        with open('/tmp/downloaded_pdf.pdf', 'rb') as file:
            pdf_reader = fitz.open(file)
            for page in pdf_reader:
                text = page.get_text()
                
                if not "20-80W LOAD TESTS" in text:
                    continue
                else:
                    title_count = -1
                    for line in text.splitlines():
                        title_count += 1
                        if "20-80W LOAD TESTS" in line:
                            break

                    efficiency = [re.search(r"^.*%", line).group(0) for line in text.splitlines()[title_count:] if re.search(r"^.*%", line) is not None]


                    df_new = pd.DataFrame([{"Brand": psu['Brand'], 
                                            "Model": psu['Model'], 
                                            "Form Factor": psu['Form Factor'], 
                                            "Cybenetics Rating": psu['Cybenetics Rating'], 
                                            "20W Efficiency": efficiency[0],
                                            "40W Efficiency": efficiency[1],
                                            "60W Efficiency": efficiency[2],
                                            "80W Efficiency": efficiency[3],
                                            "Report Link": psu['Report Link'],
                                            "Lowest Price (Geizhals.de)": psu['Lowest Price (Geizhals.de)']
                                            }])
                    df = pd.concat([df, df_new], ignore_index=True)
                    break
                break

                        


        open('/tmp/downloaded_pdf.pdf', 'w').close()
        bar()


print(df)
df.to_csv("PSUs.csv", encoding='utf-8', index=False)
