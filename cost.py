import streamlit as st
import pandas as pd
import time
import io
import os

import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- AUTO-INSTALL CHROMEDRIVER ---
chromedriver_autoinstaller.install()

# --- STREAMLIT SETUP ---
st.set_page_config(page_title="Lightspeed Scraper", layout="centered")
st.title("🛒 Lightspeed Stock Scraper + Pivot Tool")
st.markdown("Paste your **weekly stock transfer report URL** from Lightspeed and hit Run.")

# --- USER INPUT ---
url = st.text_input("📎 Paste Report URL:", placeholder="https://shosha.retail.lightspeed.app/inventory/stock-transfer?...")

# --- CREDENTIALS (hardcoded here; best to use secrets in production) ---
LOGIN_URL = 'https://shosha.retail.lightspeed.app/signin/?return=%2F'
USERNAME = 'KeyurV'
PASSWORD = '12@Harshang'

if st.button("🚀 Run Scraper") and url:
    with st.spinner("Logging in, scraping data, and creating pivot table..."):

        # --- CHROME OPTIONS ---
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=chrome_options)

        try:
            # --- LOGIN ---
            driver.get(LOGIN_URL)
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.NAME, 'username'))).send_keys(USERNAME)
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.NAME, 'password'))).send_keys(PASSWORD + Keys.RETURN)
            WebDriverWait(driver, 15).until(EC.url_changes(LOGIN_URL))

            # --- GO TO DYNAMIC URL ---
            driver.get(url)
            time.sleep(5)

            # --- SCROLL TO LOAD DATA ---
            scrollable_element = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "section.vd-main-content"))
            )

            last_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_element)
            same_height_count = 0
            max_retries = 5

            while same_height_count < max_retries:
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_element)
                time.sleep(2)
                new_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_element)
                if new_height == last_height:
                    same_height_count += 1
                else:
                    same_height_count = 0
                last_height = new_height

            # --- SCRAPE TABLE ---
            html = driver.page_source
            tables = pd.read_html(io.StringIO(html))
            if not tables:
                st.error("⚠️ No tables found on the page.")
                st.stop()

            df = tables[0]
            df.to_excel("output.xlsx", index=False)

        finally:
            driver.quit()

        # --- PROCESSING ---
        df = pd.read_excel("output.xlsx")
        df = df.dropna(subset=['Reference', 'Total cost'])

        df['Total cost'] = (
            df['Total cost']
            .astype(str)
            .str.replace(r'^\$', '', regex=True)
            .str.replace(',', '')
            .astype(float)
        )

        split_cols = df['Reference'].str.split('_', expand=True)
        valid_rows = split_cols[0].notnull() & split_cols[1].notnull()
        split_cols = split_cols[valid_rows]
        df = df.loc[split_cols.index]

        df['Location'] = split_cols[0]
        df['Category'] = split_cols[1].str.strip().str.capitalize()

        pivot_df = df.pivot_table(
            index='Location',
            columns='Category',
            values='Total cost',
            aggfunc='sum',
            fill_value=0
        ).reset_index()

        desired_order = ['Location', 'Vape', 'E-liquid', 'Smoking']
        pivot_df = pivot_df.reindex(columns=[col for col in desired_order if col in pivot_df.columns])

        pivot_df.to_excel("pivot_output.xlsx", index=False)

        # --- UI DOWNLOAD ---
        st.success("✅ Done! Download your pivoted Excel file below.")
        with open("pivot_output.xlsx", "rb") as f:
            st.download_button("⬇️ Download Pivot Output", f, file_name="pivot_output.xlsx")

