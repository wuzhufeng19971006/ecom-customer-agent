"""兼容层：实际代码在 common.logger.logger"""
from common.logger.logger import *  # noqa: F401, F403
from common.logger.logger import get_logger, setup_logging  # 显式导出
