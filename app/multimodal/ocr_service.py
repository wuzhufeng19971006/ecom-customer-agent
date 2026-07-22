"""兼容层：实际代码在 runtime.multimodal.ocr_service"""
from runtime.multimodal.ocr_service import *  # noqa: F401, F403
from runtime.multimodal.ocr_service import OCRResult, OCRService, MiMoOCRService, filter_ocr_text, get_ocr
