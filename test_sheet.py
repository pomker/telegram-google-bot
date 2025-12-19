import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Имя таблицы
SHEET_NAME = "Телефоны"
CRED_FILE = "credentials.json"

# Авторизация
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CRED_FILE, scope)
client = gspread.authorize(creds)

# Открываем таблицу
sheet = client.open(SHEET_NAME).sheet1

# Добавляем тестовую строку
sheet.append_row(["+79991234567", "123456789", "TestUser"])

print("✅ Тестовая запись прошла")
