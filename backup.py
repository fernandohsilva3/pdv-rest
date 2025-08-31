
import os, shutil, datetime

DB_FILE = os.getenv("PDV_DB_PATH", "pdv.db")
BACKUP_DIR = "backups"

os.makedirs(BACKUP_DIR, exist_ok=True)
now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
backup_file = os.path.join(BACKUP_DIR, f"backup_{now}.db")
shutil.copy2(DB_FILE, backup_file)
print(f"Backup criado: {backup_file}")
