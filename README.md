# File Web Scrapper on servidorespublicos.gob.mx 

A python script with selenium (Chrome) that download and verify public servants with updated annual declaration

## Requirements

* Python 3.10
* Latest Chrome
* Windows (Linux todo)

## Use this script

1. Install libraries:
`
pip install -r requirements.txt
`

2. Set a your seed Excel files inside of /seed folder, 1st column should be "Nombres", 2nd should be "RFC", otherwise will fail

3. Run:
`
python .\main.py 
`

## How It Works
The script reads names and RFCs from seed.xlsx, navigates to the servidorespublicos.gob.mx website, and attempts to find and download the annual declaration documents for each listed public servant. It uses headless Chrome to navigate the site, meaning Chrome runs in the background without a visible window.

## Output
The script will create two Excel files:

ENCONTRADAS.xlsx: Contains details of public servants whose declarations were successfully found and downloaded.
NO_ENCONTRADAS.xlsx: Contains details of public servants whose declarations were not found.
Each file will include the names, RFCs, and other relevant details extracted during the scraping process.