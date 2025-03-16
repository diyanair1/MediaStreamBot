# Description: This script downloads all videos of the sessions on a specific date from the North Dakota Legislative Assembly website.
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import subprocess
import yaml
from datetime import datetime
import os

def load_config():
    config_path = "/Users/diya/Desktop/Selenium/gov_sesh/config_nd.yaml"
    with open(config_path, "r") as file:
        return yaml.safe_load(file)

# Accessing the config file
config = load_config()
chromedriver_path = config["chromedriver_path"]
download_path = config["download_path"]
start_date = config["start_date"]
end_date = config["end_date"]
home_url = config["home_url"]
success_failed_path = config["success_failed_path"]

def get_driver():
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    options = webdriver.ChromeOptions()
    options.add_argument(f"user-agent={user_agent}")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument('--ignore-certificate-errors')
    # maximize window
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    # Set performance logging capabilities directly on the options
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    
    # Setting up Chrome WebDriver
    service = Service(path=chromedriver_path)
    driver = webdriver.Chrome(service=service, options=options)

    driver.execute_cdp_cmd("Network.enable", {})  # Enable network logging
    driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": user_agent})
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })

    return driver

def append_to_json(entry, filename):
    # Load existing data or start a new list
    try:
        with open(os.path.join(success_failed_path, filename), "r") as file:
            event_list = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        event_list = []

    # Append the new entry to the list
    event_list.append(entry)

    # Save the updated list back to the file
    with open(os.path.join(success_failed_path, filename), "w") as file:
        json.dump(event_list, file, indent=4)  

def download_video(driver):

    driver.get(home_url)
    time.sleep(2)

    startDate = driver.find_element(By.ID, 'txtStartDate')
    startDate.click()
    startDate.send_keys(start_date)

    time.sleep(1)

    endDate = driver.find_element(By.ID, 'txtEndDate')
    endDate.click()
    endDate.send_keys(end_date)
    time.sleep(1)

    filter = driver.find_element(By.ID, 'btnFilter')
    filter.click()
    time.sleep(5)
    second_card = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'upcomingeventlist'))
    )
    # second_card = driver.find_element(By.CLASS_NAME, 'upcomingeventlist')

    # Get event urls from the session cards
    event_urls = [a.get_attribute("href") for a in second_card.find_elements(By.CSS_SELECTOR, ".divEvent a")]
    event_titles = [a.text for a in second_card.find_elements(By.CSS_SELECTOR, "a > div > table > tbody > tr > td.tdEventTitle > span")]

    current_date = datetime.now().strftime("%Y-%m-%d")

    for i in range(len(event_urls)):

        # Now finding m3u8 urls
        driver.get_log("performance")

        # Click on the event
        driver.get(event_urls[i])
        time.sleep(5)

        logs = driver.get_log("performance")
        m3u8_links = []

        print ("Checking for m3u8 links in the network logs...\n")
        
        for log in logs:
            try:
                # Parse log entry's message
                message = json.loads(log["message"])["message"]
            except Exception:
                continue
        
                # Look for network response events
            if message.get("method") == "Network.responseReceived":
                # Extract the response data
                response = message.get("params", {}).get("response", {})
                headers = response.get("headers", {})
                content_type = headers.get("Content-Type", "")
                url = response.get("url", "")

                # Check if the MIME type and URL match our criteria
                if ".m3u8" in url:
                    m3u8_links.append(url)

        if m3u8_links:
            try: 
                start_time = time.time()
                # Downloading video using ffmpeg
                ffmpeg_command = [
                    "ffmpeg",
                    "-headers", "Referer: https://wralarchives.com/",
                    "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                    "-i", m3u8_links[0],  # Input: the m3u8 URL (location of the video playlist)
                    "-c", "copy", # Copy the video codecs without re-encoding
                    f"{download_path}{event_titles[i]}.mp4"
                ]

                subprocess.run(ffmpeg_command)
                # Updating the success list
                entry = {
                    "title": event_titles[i],
                    "recorded_date": start_date,
                    "link": m3u8_links[0],
                    "last_attempted_scrape_date": current_date
                }
                append_to_json(entry, "success_list.json")
                print(f"Video downloaded successfully! -> {event_titles[i]}")

                end_time = time.time()
                time_taken = (end_time - start_time)/60
                print(f"Time taken to download video: {time_taken:.2f} min")
                
            except subprocess.CalledProcessError as e:
                entry = {
                    "title": event_titles[i],
                    "recorded_date": start_date,
                    "link": m3u8_links[0],
                    "last_attempted_scrape_date": current_date
                }
                append_to_json(entry, "failed_list.json")
                print(f"Failed to download video! -> {event_titles[i]}")
            
        else:
            print("No .m3u8 links were found in the network logs.")
            entry = {
                "title": event_titles[i],
                "recorded_date": start_date,
                "link": m3u8_links[0],
                "last_attempted_scrape_date": current_date
            }
            append_to_json(entry, "failed_list.json")
            print(f"Failed to download video! -> {event_titles[i]}")


def main():
    driver = get_driver()

    download_video(driver)

    driver.quit()

if __name__ == "__main__":
    main()