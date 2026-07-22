"""多模态理解模块：图片理解 + OCR + 图片分析编排。

- vision_service: 调用 MiMo-V2.5 输出结构化 vision_context
- ocr_service:    独立 OCR 服务（先用 MiMo 做 OCR 实现，接口预留 PaddleOCR 替换）
- image_analyzer: 编排 vision + ocr，产出最终 multimodal context
"""
