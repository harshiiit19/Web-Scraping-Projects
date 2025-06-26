import psycopg2
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time

# Database configuration
DB_HOST = "localhost"
DB_NAME = "data_scrap"
DB_USER = "postgres"
DB_PASSWORD = "password"

def create_table_if_not_exists(conn):
    """Create the table if it doesn't exist"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS seller_data (
                id SERIAL PRIMARY KEY,
                game_name TEXT,
                server TEXT,
                price TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    except Exception as e:
        print(f"Error creating table: {e}")
        conn.rollback()

def connect_to_db():
    """Establish database connection and ensure table exists"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        create_table_if_not_exists(conn)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def handle_cookie_popup(driver):
    """Handle the cookie popup if it appears"""
    try:
        popup = WebDriverWait(driver, 3).until(
            EC.visibility_of_element_located((By.ID, 'isEurope'))
        )
        accept_btn = popup.find_element(By.CSS_SELECTOR, '#acceptCookiesButton')
        accept_btn.click()
        print("Cookie popup closed")
        time.sleep(1)
    except (TimeoutException, NoSuchElementException):
        pass

def scrape_page(driver, page_num, conn):
    print(f"\n--- Page {page_num} ---")
    
    try:
        games = WebDriverWait(driver, 10).until(
            EC.visibility_of_all_elements_located((By.CSS_SELECTOR, '.offer-title-colum'))
        )

        servers = WebDriverWait(driver, 10).until(
            EC.visibility_of_all_elements_located((By.CLASS_NAME, 'offer-title-id'))
        )

        prices = WebDriverWait(driver, 10).until(
            EC.visibility_of_all_elements_located((By.CSS_SELECTOR, '.offer-price-tag.price'))
        )

        cursor = conn.cursor()
        inserted_count = 0
        
        for i in range(min(len(games), len(servers), len(prices))):
            try:
                game_name = games[i].text.strip()
                server = servers[i].text.strip()
                price = prices[i].text.strip()

                print(f'Game Name: {game_name}, Server: {server}, Price: {price}')

                cursor.execute(
                    "INSERT INTO seller_data (game_name, server, price) VALUES (%s, %s, %s)",
                    (game_name, server, price)
                )
                inserted_count += 1
                
            except NoSuchElementException as e:
                print(f"Error extracting data from an offer: {e}")
                continue
            except Exception as e:
                print(f"Database error on record {i}: {e}")
                conn.rollback()
                continue
        
        conn.commit()
        print(f"Successfully inserted {inserted_count} records from page {page_num}")
        
    except Exception as e:
        print(f"Error scraping page {page_num}: {e}")
        conn.rollback()

def click_next_page(driver):
    """Attempt to click the next page button with multiple safeguards"""
    handle_cookie_popup(driver)  
    
    try:
        next_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.page-link[aria-label="Next Page"]:not([aria-disabled="true"])'))
        )
        
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", next_button)
        return True
    except Exception as e:
        print(f"Failed to click next button: {str(e)}")
        return False

def main():
    page_num = 1
    max_pages = 24
    
    # Establish database connection once
    conn = connect_to_db()
    if not conn:
        print("Failed to connect to database. Exiting.")
        return
    
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)
    driver.get("url/ website link ")
    
    handle_cookie_popup(driver)

    try:
        while page_num <= max_pages:
            scrape_page(driver, page_num, conn)
            
            if not click_next_page(driver):
                print("No more pages available or navigation failed")
                break
                
            page_num += 1
            time.sleep(2)
            handle_cookie_popup(driver)
    
    except Exception as e:
        print(f"Error in main scraping loop: {e}")
    finally:
        driver.quit()
        if conn:
            conn.close()
            print("Database connection closed")

if __name__ == "__main__":
    main()