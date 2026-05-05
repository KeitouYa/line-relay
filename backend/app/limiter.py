from slowapi import Limiter
from slowapi.util import get_remote_address

# 独立文件，避免 main.py 和 routers/relay.py 之间的循环导入
limiter = Limiter(key_func=get_remote_address)