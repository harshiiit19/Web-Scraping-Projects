from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import psycopg2

# Database configuration
DB_HOST = "host"
DB_NAME = "database name"
DB_USER = "postgres"
DB_PASSWORD = "password"
DB_PORT = "5432"

def create_table(conn):
    """Create the table if it doesn't exist"""
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS 'table name' (
                    id SERIAL PRIMARY KEY,
                    account_name TEXT NOT NULL,
                    seller_name TEXT NOT NULL,
                    price_in_USD TEXT NOT NULL,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        conn.commit()
    except psycopg2.Error as e:
        print(f"Error creating table: {e}")
        conn.rollback()

def save_to_db(conn, data):
    """Save scraped data to PostgreSQL"""
    try:
        with conn.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO 'table name' (account_name, seller_name, price_in_USD) VALUES (%s, %s, %s)",
                data
            )
        conn.commit()
    except psycopg2.Error as e:
        print(f"Error inserting data: {e}")
        conn.rollback()


def scrape_data(driver):
    wait = WebDriverWait(driver, 10)
    scraped_items = []

    for i in range(1, 100):
        try:
            xpath_account = f'//*[@id="q-app"]/div/div[1]/main/div/div[5]/div[1]/div[2]/div/div[2]/div/div[{i}]/div/a/div[1]/div/span'
            xpath_seller = f'//*[@id="q-app"]/div/div[1]/main/div/div[5]/div[1]/div[2]/div/div[2]/div/div[{i}]/div/div/a[1]/div/div[2]/div[1]'
            xpath_price = f'//*[@id="q-app"]/div/div[1]/main/div/div[5]/div[1]/div[2]/div/div[2]/div/div[{i}]/div/div/a[2]/span[1]'

            account_element = wait.until(EC.presence_of_element_located((By.XPATH, xpath_account)))
            seller_element = wait.until(EC.presence_of_element_located((By.XPATH, xpath_seller)))
            price_element = wait.until(EC.presence_of_element_located((By.XPATH, xpath_price)))

            account_name = account_element.text.strip()
            seller_name = seller_element.text.strip()
            price = price_element.text.strip()

            print(f"{i}: {account_name} || {seller_name} || {price}")
            scraped_items.append((account_name, seller_name, price))

        except Exception as e:
            print(f"{i}: Element not found or error: {e}")
            break  

    return scraped_items


def go_to_next_page(driver):
    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        pagination = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'q-pagination'))
        )

        buttons = pagination.find_elements(By.CLASS_NAME, 'q-btn')
        if not buttons or len(buttons) < 2:
            print("Next button not found")
            return False

        next_button = buttons[-1]
        icon = next_button.find_element(By.TAG_NAME, 'i')

        if icon.get_attribute("innerHTML").strip() != "keyboard_arrow_right":
            print("Last button is not the next page button.")
            return False

        driver.execute_script("arguments[0].click();", next_button)
        time.sleep(5)
        return True

    except Exception as e:
        print(f"Error navigating to next page: {e}")
        return False


def main():

    # Connect to database
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        return

    create_table(conn)

    try:
        driver = webdriver.Chrome()
        driver.get('url/link of the website where you get the data')

        page_number = 1
        max_pages = 2

        while page_number <= max_pages:
            print(f"\n--- Scraping Page {page_number} ---")
            items = scrape_data(driver)

            if items:
                save_to_db(conn, items)
            else:
                print("No items found on this page.")
                break

            page_number += 1

            if page_number <= max_pages:
                next_success = go_to_next_page(driver)
                if not next_success:
                    print("Failed to go to next page.")
                    break

    finally:
        driver.quit()
        conn.close()


if __name__ == "__main__":
    main()
