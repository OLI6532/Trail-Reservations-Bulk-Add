import argparse
import csv
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import List, Tuple

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

"""
Automated utility created for the ROH to bulk add assets to a Trial reservation.

Uses the Selenium WebDriver to emulate a user session and automate the browser UI process.

Usage: `python reservation_bulk_add.py -R <reservation_id> -C <path_to_csv_file>`
Run `python reservation_bulk_add.py -h` for guidance on how to get started.

Created by Owen Ling 2025-07-18
"""

log = logging.getLogger()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Thread-local storage for browser instances
thread_local = threading.local()

# Thread-safe counter for progress tracking
progress_lock: Lock = threading.Lock()
completed_count: int = 0

# Configure the argument parser to accept flags when running this utility
# interactively from the CLI
parser = argparse.ArgumentParser(
    prog="Trail Bulk Add to Reservation Utility",
    usage="python reservation_bulk_add.py -R <reservation_id> -C <path_to_csv_file>",
    description="Use this utility to bulk add assets to a Trail reservation. This emulates a user session and automates the browser UI process using JavaScript automation.",
    # formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)

parser.add_argument(
    '-R',
    '--reservation_id',
    metavar='Reservation ID',
    required=True,
    help='The reservation ID to add assets to.'
)
parser.add_argument(
    '-C',
    '--csv_file',
    metavar='Path to CSV File',
    required=True,
    help='The path to the CSV file containing the assets to add. This first column should contain the asset barcode number and have no header.'
)

parser.add_argument(
    '-U',
    '--username',
    type=str,
    metavar='Username',
    required=False,
    help='The Trail username to use to login with. If not provided, the script will search for a default username in the .env file with a value of TRAIL_USERNAME.'
)

parser.add_argument(
    '-P',
    '--password',
    type=str,
    metavar='Password',
    help='The Trail password to use to login with. If not provided, the script will search for a default password in the .env file with a value of TRAIL_PASSWORD.'
)

parser.add_argument(
    '-S',
    '--site-url',
    type=str,
    metavar='Trail Site URL',
    required=True,
    help='The URL of the Trail instance to add assets to.'
)
parser.add_argument(
    '-H',
    '--headless',
    action='store_true',
    required=False,
    help='Run the browser session in headless mode.'
)
parser.add_argument(
    '-T',
    '--threads',
    type=int,
    metavar='Threads',
    default=3,
    help='The number of threads to use for parallel browser sessions. (Default: 3).'
)
parser.add_argument(
    '-Q',
    '--quiet',
    action='store_true',
    required=False,
    help='Suppress all output except for errors.',
)


def configure_logging(quiet_mode: bool = False):
    log_level = logging.ERROR if quiet_mode else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        force=True  # Override any previously configured logging configs
    )


def load_asset_ids(filename: str) -> List[str]:
    """Loads asset barcodes from the provided CSV file and return them as a List.
    :param filename: The path to the CSV file containing asset barcodes.
    :return: A List of asset barcodes.
    """
    barcodes: List[str] = []
    log.info(f"Loading asset barcodes from {filename}...")
    with open(filename, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            barcodes.append(row[0].strip())
    log.info(f"Loaded {len(barcodes)} asset barcodes.")
    return barcodes


def create_browser_session(trial_url: str, is_headless: bool = False) -> WebDriver:
    """Configures the Chrome browser session for automation.
    :param trial_url: The URL of the Trail instance to add assets to.
    :param is_headless: Whether to run the browser session in headless mode.
    :return: The configured WebDriver instance.
    """
    chrome_options = webdriver.ChromeOptions()
    if is_headless:
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-notifications')
    chrome_options.add_argument('--disable-infobars')

    browser = webdriver.Chrome(options=chrome_options)

    # Check that we have received the reservation on the end of the URL string
    if trial_url.endswith('/'):
        raise RuntimeError("The Trail URL must end with the reservation ID to add items to.")

    # Initialise the browser and open the Trail URL ready for automation to take place
    browser.get(trial_url)
    return browser


def session_login(browser: WebDriver, username: str, password: str):
    try:
        browser.find_element(By.ID, "user_session_email").send_keys(username)
        browser.find_element(By.ID, "user_session_password").send_keys(password)
        browser.find_element(By.ID, "login-button").click()
    except Exception as e:
        log.error(f"Error occurred during login automation: {e}")
        raise e


def session_setup_input_form(browser: WebDriver):
    try:
        # First, we wait to ensure that the webpage has loaded after authentication before attempting to interact with it
        # We wait for the text field to be available
        element = None
        try:
            element = WebDriverWait(browser, 10).until(
                expected_conditions.presence_of_element_located((By.ID, "reservation_item")))
        finally:
            # Once ready, click on it ready to start typing asset IDs
            element.click()

        # Ensure `Collect only` is selected in the radio group
        if not browser.find_element(By.ID, "scan_mode_collect").is_selected():
            browser.find_element(By.ID, "scan_mode_collect").click()



    except Exception as e:
        log.error(f"Error occurred during input form setup automation: {e}")
        raise e


def session_add_asset(browser: WebDriver, asset_barcode: str):
    """
    Handles typing a single barcode number and clicking the GO button.
    Waits for the loading spinner to disappear before continuing.
    :param asset_barcode: The asset barcode number to add.
    """

    # We wait for this to disappear before continuing
    loading_spinner = browser.find_element(By.CLASS_NAME, "throbber")  # yes, really
    entry_field = browser.find_element(By.ID, "reservation_item")
    go_button = browser.find_element(By.XPATH,
                                     "/html/body/div[1]/div[2]/div/div[2]/div[2]/div[2]/div/div[1]/div/form/table/tbody/tr[1]/td[2]/button")

    entry_field.clear()  # Clear any existing content
    entry_field.send_keys(asset_barcode)
    go_button.click()

    WebDriverWait(browser, 10).until_not(expected_conditions.visibility_of(loading_spinner))

    return


def get_thread_browser(trail_url: str, username: str, password: str, is_headless: bool) -> WebDriver:
    if not hasattr(thread_local, 'browser'):
        thread_local.browser = create_browser_session(trial_url=trail_url, is_headless=is_headless)
        session_login(thread_local.browser, username, password)
        session_setup_input_form(thread_local.browser)
        thread_id = threading.current_thread().ident
        log.info(f"Thread {thread_id}: Browser session initialised.")

    return thread_local.browser


def process_asset(args_tuple) -> Tuple[str, bool, str | None]:
    """Process a single asset barcode.
    :param args_tuple: A tuple containing (asset_barcode, trail_url, username, password, is_headless, total_assets).
    """

    asset_barcode, trail_url, username, password, is_headless, total_assets = args_tuple
    global completed_count
    thread_id = threading.current_thread().ident

    try:
        # Get a thread-local browser instance
        browser = get_thread_browser(trail_url, username, password, is_headless)

        session_add_asset(browser, asset_barcode)

        with progress_lock:
            completed_count += 1
            current_count = completed_count
            completion_percentage = round((current_count / total_assets) * 100, 1)

        log.info(
            f"Thread {thread_id}: [{completion_percentage}% – {current_count}/{total_assets}] Added {asset_barcode} to {arg_reservation_id}.")

        return asset_barcode, True, None

    except Exception as e:
        log.error(f"Thread {thread_id}: Error occurred during asset processing: {e}")
        return asset_barcode, False, str(e)


def cleanup_browsers():
    """Clean up browser instances in all threads"""
    if hasattr(thread_local, 'browser'):
        try:
            thread_local.browser.quit()
        except Exception as e:
            log.warning(f"Error closing browser: {e}")


def main(
        reservation_id: str,
        csv_file: str,
        username: str,
        password: str,
        site_url: str,
        headless: bool,
        threads: int
):
    global completed_count
    completed_count = 0

    # Load the asset barcodes into memory
    asset_barcodes = load_asset_ids(csv_file)
    total_assets = len(asset_barcodes)

    trial_url = f"https://{site_url}/reservations/{reservation_id}"

    log.info(f"Starting bulk add with {threads} concurrent browser sessions...")

    # Prepare arguments for each asset
    task_args = [(barcode, trial_url, username, password, headless, total_assets)
                 for barcode in asset_barcodes]

    failed_assets = []
    successful_count = 0

    try:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            # Submit all tasks
            future_to_barcode = {executor.submit(process_asset, args): args[0] for args in task_args}

            for future in as_completed(future_to_barcode):
                barcode = future_to_barcode[future]
                try:
                    asset_barcode, success, error = future.result()
                    if success:
                        successful_count += 1
                    else:
                        failed_assets.append((asset_barcode, error))
                except Exception as exc:
                    log.error(f'Asset {barcode} generated an exception: {exc}')
                    failed_assets.append((barcode, str(exc)))
    finally:
        # Clean up any remaining browser sessions
        cleanup_browsers()

    # Report results
    log.info("-" * 35)
    log.info(f"Finished! Successfully added {successful_count}/{total_assets} assets to reservation {reservation_id}.")

    if failed_assets:
        log.warning(f"Failed to add {len(failed_assets)} assets:")
        for asset_barcode, error in failed_assets:
            log.warning(f"  - {asset_barcode}: {error}")


if __name__ == '__main__':
    args = parser.parse_args()  # Collect the arguments passed to the parser from STDIN

    configure_logging(quiet_mode=args.quiet)

    arg_reservation_id = args.reservation_id
    arg_csv_file = args.csv_file
    arg_username = args.username
    arg_password = args.password
    arg_site_url = args.site_url
    arg_headless = args.headless
    arg_threads = args.threads

    # If the username or password was not provided, we need to search the dotenv file for them
    if not arg_username or arg_password:
        load_dotenv()  # This expects a .dotenv file in the location the script is being run from
        if not arg_username:
            arg_username = os.getenv('TRAIL_USERNAME')
        if not arg_password:
            arg_password = os.getenv('TRAIL_PASSWORD')

    if not arg_username or not arg_password:
        # If a username or password is still not present, exit the program here
        raise ValueError("A username and password must be provided either as arguments or available in the .env file.")

    if not os.path.exists(arg_csv_file):
        raise FileNotFoundError(f"The specified CSV file '{arg_csv_file}' does not exist.")

    main(reservation_id=arg_reservation_id, csv_file=arg_csv_file, username=arg_username, password=arg_password,
         site_url=arg_site_url, headless=arg_headless, threads=arg_threads)
