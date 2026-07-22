"""兼容层：实际代码在 common.database.database"""
from common.database.database import *  # noqa: F401, F403
from common.database.database import Base, SessionRow, MessageRow, HandoffTask, init_db
