from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# storage_uri mac dinh "memory://" - dung cho 1 tien trinh gunicorn duy nhat
# (dung tinh than "khong dung Redis giai doan dau" cua kien truc muc tieu).
# default_limits rong - tung route tu ap gioi han rieng qua @limiter.limit(...).
limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")
