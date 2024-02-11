"""
Scrape Indeed for Company rankings, and number of reviews
"""

import logging
import os
from pathlib import Path
from random import randint
from time import sleep
# Third-party packages
import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import (ElementClickInterceptedException,
                                        TimeoutException)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as ExpeC
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
# Local packages
from drapi.code.drapi.drapi import (getTimestamp,
                                    makeDirPath,
                                    successiveParents)

# Arguments
SLEEP_BOUND_LOWER = 1
SLEEP_BOUND_UPPER = 10
WEBDRIVERWAIT_TIMEOUT_LIMIT = 20
GCUP = "https://webcache.googleusercontent.com/search?q=cache:"  # Google Cache URL Prefix
EMAIL_ADDRESS = os.environ["HFA_PICR_EMAIL"]
PASSWORD = os.environ["HFA_PICR_PWD"]

NUM_MAX_CLICKS = 100

APPROACH_NEXT_PAGE_BUTTON = True

# Arguments: Meta-variables
PROJECT_DIR_DEPTH = 2
USER_HOME_DIRECTORY_DEPTH = PROJECT_DIR_DEPTH + 3
ROOT_DIRECTORY_DEPTH = PROJECT_DIR_DEPTH + 5

ROOT_DIRECTORY = "PROJECT_OR_PORTION_DIRECTORY"  # TODO One of the following:
                                                 # ["PROJECT_OR_PORTION_DIRECTORY",  # noqa
                                                 #  "USER_HOME_DIRECTORY",           # noqa
                                                 #  "ROOT_DIRECTORY"]                # noqa

LOG_LEVEL = "INFO"

# Variables: Path construction: General
runTimestamp = getTimestamp()
thisFilePath = Path(__file__)
thisFileStem = thisFilePath.stem
projectDir, _ = successiveParents(thisFilePath.absolute(), PROJECT_DIR_DEPTH)
userHomeDir, _ = successiveParents(thisFilePath.absolute(), USER_HOME_DIRECTORY_DEPTH)
rootDir, _ = successiveParents(thisFilePath.absolute(), ROOT_DIRECTORY_DEPTH)
dataDir = projectDir.joinpath("data")
if dataDir:
    inputDataDir = dataDir.joinpath("input")
    outputDataDir = dataDir.joinpath("output")
    if outputDataDir:
        runOutputDir = outputDataDir.joinpath(thisFileStem, runTimestamp)
logsDir = projectDir.joinpath("logs")
if logsDir:
    runLogsDir = logsDir.joinpath(thisFileStem)
sqlDir = projectDir.joinpath("sql")

if ROOT_DIRECTORY == "PROJECT_OR_PORTION_DIRECTORY":
    rootDirectory = projectDir
elif ROOT_DIRECTORY == "USER_HOME_DIRECTORY":
    rootDirectory = userHomeDir
elif ROOT_DIRECTORY == "ROOT_DIRECTORY":
    rootDirectory = rootDir
else:
    raise Exception("An unexpected error occurred.")

# Variables: Other
pass

# Directory creation: General
makeDirPath(runOutputDir)
makeDirPath(runLogsDir)

# Logging block
logpath = runLogsDir.joinpath(f"log {runTimestamp}.log")
logFormat = logging.Formatter("""[%(asctime)s][%(levelname)s](%(funcName)s): %(message)s""")

logger = logging.getLogger(__name__)

fileHandler = logging.FileHandler(logpath)
fileHandler.setLevel(9)
fileHandler.setFormatter(logFormat)

streamHandler = logging.StreamHandler()
streamHandler.setLevel(LOG_LEVEL)
streamHandler.setFormatter(logFormat)

logger.addHandler(fileHandler)
logger.addHandler(streamHandler)

logger.setLevel(9)

if __name__ == "__main__":
    logger.info(f"""Begin running "{thisFilePath}".""")
    logger.info(f"""All other paths will be reported in debugging relative to `{ROOT_DIRECTORY}`: "{rootDirectory}".""")
    logger.info(f"""Script arguments:


    # Arguments
    `SLEEP_BOUND_LOWER`: "{SLEEP_BOUND_LOWER}"
    `SLEEP_BOUND_UPPER`: "{SLEEP_BOUND_UPPER}"
    `EMAIL_ADDRESS`: "{EMAIL_ADDRESS}"
    `NUM_MAX_CLICKS`: "{NUM_MAX_CLICKS}"

    # Arguments: General
    `PROJECT_DIR_DEPTH`: "{PROJECT_DIR_DEPTH}" ---------> "{projectDir}"
    `USER_HOME_DIRECTORY_DEPTH`: "{USER_HOME_DIRECTORY_DEPTH}" -> "{userHomeDir}"
    `ROOT_DIRECTORY_DEPTH`: "{ROOT_DIRECTORY_DEPTH}" ------> "{rootDir}"

    `LOG_LEVEL` = "{LOG_LEVEL}"
    """)

    # Start driver
    options = webdriver.ChromeOptions()
    # options.headless = True
    options.add_argument('window-size=1920x1080')
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
    if True:
        # Go to companies page.
        logger.info("Going to companies page.")
        COMPANIES_HOMEPAGE = "https://www.indeed.com/companies"
        driver.get(GCUP + COMPANIES_HOMEPAGE)
        logger.info("Going to companies page - done.")
        # Search first group of industry pages
        logger.info("Getting first six industry category links.")
        industryCategoryLinks = {}
        # Select with: a[data-tn-element="cmp-Industry-link"]
        categoriesGroup1 = driver.find_elements_by_css_selector(css_selector='a[data-tn-element="cmp-Industry-link"]')
        for el in categoriesGroup1:
            categoryName = el.get_attribute("text")
            categoryLink = el.get_attribute("href")
            industryCategoryLinks[categoryName] = categoryLink
        logger.info("Getting first six industry category links. - done.")

        # See all the other industry categories.
        logger.info("See all industries.")
        if len(GCUP) == 0:
            SELECTOR_CSS_ALL_INDUSTRY_CATEGORIES = '[data-tn-element="cmp-Industry-see-all-desktop-link"]'
        elif len(GCUP) > 0:
            SELECTOR_CSS_ALL_INDUSTRY_CATEGORIES = '[data-tn-element="cmp-Industry-see-all-mobile-link"]'
        element = driver.find_element_by_css_selector(css_selector=SELECTOR_CSS_ALL_INDUSTRY_CATEGORIES)
        try:
            element.click()
        except ElementClickInterceptedException as err:
            message, *_ = err.args
            if "CookiePrivacyNoticeBanner" in message:
                element = driver.find_element_by_css_selector(css_selector=SELECTOR_CSS_ALL_INDUSTRY_CATEGORIES)
                driver.execute_script("arguments[0].click();", element)  # h/t to https://stackoverflow.com/a/48667924/5478086
            else:
                raise err
        logger.info("See all industries - done.")
        logger.info("Scraping all other industry category links.")
        categoriesGroup2 = driver.find_elements_by_css_selector(css_selector='a[data-tn-element="cmp-Industry-link"]')
        for el in categoriesGroup2:
            categoryName = el.get_attribute("text")
            categoryLink = el.get_attribute("href")
            industryCategoryLinks[categoryName] = categoryLink
        # For industry category in `industryCategoryLinks`
        logger.info("Visiting category pages.")
        allCompanies = []
        for categoryName, categoryLink in industryCategoryLinks.items():
            logger.info(f"""  Working on category "{categoryName}".""")
            categoryNextPageLinksFpath = runOutputDir.joinpath(f"{categoryName} Page Links.CSV")
            categoryDataFpath = runOutputDir.joinpath(f"{categoryName}.CSV")
            categoryDir = runOutputDir.joinpath(categoryName)
            makeDirPath(categoryDir)
            driver.get(GCUP + categoryLink)
            categoryCompanies = {}
            # Get next page link
            SELECTOR_CSS_NEXT_PAGE_BUTTON = 'a[data-tn-element="next-page"]'
            if APPROACH_NEXT_PAGE_BUTTON:
                try:
                    nextPageButton = WebDriverWait(driver,
                                                   WEBDRIVERWAIT_TIMEOUT_LIMIT).until(ExpeC.element_to_be_clickable((By.CSS_SELECTOR,
                                                                                                                      SELECTOR_CSS_NEXT_PAGE_BUTTON)))
                    condition = True
                except TimeoutException as err:
                    message, *_ = err.args
                    condition = False
            elif True:
                elListNextPageButton = driver.find_elements_by_css_selector(css_selector=SELECTOR_CSS_NEXT_PAGE_BUTTON)
                condition = len(elListNextPageButton) > 0
            pageNum = 0
            companyNum = 0
            while condition:
                logger.info(f"""    Working on page {pageNum:,}.""")
                pageNum += 1
                categoryCompaniesTemp = {}
                elListCompanyBox = driver.find_elements_by_css_selector(css_selector='div[class="css-srfrud e1gufzzf0"]')
                for el in elListCompanyBox:
                    companyNum += 1
                    elCompanyName = el.find_element_by_css_selector(css_selector='a[data-tn-element="company-name"]')
                    elCompanyLink = el.find_element_by_css_selector(css_selector='a[data-tn-element="company-name"]')
                    elStarRating = el.find_element_by_css_selector(css_selector='span[class="css-1qqp5xo e1wnkr790"]')
                    elNumReviews = el.find_element_by_css_selector(css_selector='a[class="css-1kxybv0 e19afand0"]')
                    companyName = elCompanyName.text
                    companyLink = elCompanyLink.get_attribute('href')
                    starRating = elStarRating.text
                    numReviews = elNumReviews.text
                    categoryCompaniesTemp[companyNum] = {"Company Name": companyName,
                                                        "Star Rating": starRating,
                                                        "Number of Reviews": numReviews}
                    categoryCompanies.update(categoryCompaniesTemp)
                # Save page source
                logger.info("    Saving page source.")
                source = driver.page_source
                pagepath = categoryDir.joinpath(f"Page {pageNum}.HTML")
                with open(pagepath, "w") as file:
                    file.write(source)
                logger.info("    Saving page source - done.")
                # Save page results to file
                logger.info("""    Saving page results to file.""")
                df = pd.DataFrame.from_dict(categoryCompaniesTemp, orient="index")
                df.to_csv(categoryDataFpath, mode="a")
                logger.info("""    Saving page results to file - done.""")
                logger.info(f"""    Working on page {pageNum:,} - done.""")
                # Get next page link
                if pageNum == 1:
                    if APPROACH_NEXT_PAGE_BUTTON:
                        nextPageButton = nextPageButton
                    elif True:
                        nextPageButton = elListNextPageButton[0]
                else:
                    if APPROACH_NEXT_PAGE_BUTTON:
                        try:
                            nextPageButton = WebDriverWait(driver,
                                                        WEBDRIVERWAIT_TIMEOUT_LIMIT).until(ExpeC.element_to_be_clickable((By.CSS_SELECTOR,
                                                                                                                            SELECTOR_CSS_NEXT_PAGE_BUTTON)))
                            condition = True
                        except TimeoutException as err:
                            message, *_ = err.args
                            condition = False
                    elif True:
                        elListNextPageButton = driver.find_elements_by_css_selector(css_selector=SELECTOR_CSS_NEXT_PAGE_BUTTON)
                        condition = len(elListNextPageButton) > 0
                nextPageLink = nextPageButton.get_attribute('href')
                logger.info(f"""    Going to next page: "{nextPageLink}".""")
                # Write next page link to file, one file per category.
                with open(categoryNextPageLinksFpath, "a") as file:
                    file.write(nextPageLink)
                    file.write("\n")
                sleep(randint(SLEEP_BOUND_LOWER, SLEEP_BOUND_UPPER))
                driver.get(GCUP + nextPageLink)
                if pageNum > 1:
                    break
            allCompanies.append((categoryName, categoryCompanies))
            sleep(randint(SLEEP_BOUND_LOWER, SLEEP_BOUND_UPPER))
            logger.info(f"""  Working on category "{categoryName}" - done.""")
        logger.info("Visiting category pages - done.")

    # End script
    logger.info(f"""Finished running "{thisFilePath.absolute().relative_to(rootDirectory)}".""")
