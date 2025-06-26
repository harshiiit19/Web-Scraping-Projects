from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import psycopg2


# Database configuration
DB_HOST = "localhost"
DB_NAME = "data_scrap"
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
                    seller_name TEXT NOT NULL,
                    price TEXT NOT NULL,
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
                "INSERT INTO 'table name' (seller_name, price) VALUES (%s, %s)",
                data
            )
        conn.commit()
    except psycopg2.Error as e:
        print(f"Error inserting data: {e}")
        conn.rollback()


def scrape(driver):
    results = []
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, 'q-ml-sm'))
        )

        sellers = driver.find_elements(By.CLASS_NAME, 'q-ml-sm')
        prices = driver.find_elements(By.CSS_SELECTOR, '.text-body1, .text-subtitle2')

        for i in range(min(len(sellers), len(prices))):
            seller = sellers[i].text.strip()
            price = prices[i].text.strip()
            if price in ('Unit price', 'Buy now'):
                continue
            print(f'Seller and Level: {seller}, Price: {price}')
            results.append((seller, price))

    except Exception as e:
        print(f'Error during scraping: {e}')
    return results


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
        driver.get("url/ website link")
        time.sleep(5)

        page_number = 1
        max_pages = 5

        while page_number <= max_pages:
            print(f"\n--- Scraping Page {page_number} ---")
            items = scrape(driver)

            if items:
                save_to_db(conn, items)
            else:
                print("No items found on this page.")
                break

            if not go_to_next_page(driver):
                print("Reached last page or couldn't navigate.")
                break

            page_number += 1

    finally:
        driver.quit()
        conn.close()


if __name__ == "__main__":
    main()
