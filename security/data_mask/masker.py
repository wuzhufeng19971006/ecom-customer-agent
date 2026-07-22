"""数据脱敏模块：保护敏感信息不进入 LLM。

支持的脱敏类型：
- 手机号 (11 位)
- 订单号 (15-18 位数字)
- 身份证号 (18 位)
- 银行卡号 (16-19 位)
- 邮箱
- 门牌号
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MaskResult:
    """单次脱敏结果。"""
    original: str
    masked: str
    # 映射表：masked_token -> original_token
    mask_map: dict[str, str] = field(default_factory=dict)
    # 父 Masker 引用，用于链式调用
    _masker: Masker | None = field(default=None, repr=False)

    def mask_text(self, text: str) -> MaskResult:
        """链式调用：继续脱敏下一段文本。"""
        if self._masker is None:
            raise RuntimeError("MaskResult 未关联 Masker 实例，无法链式调用")
        return self._masker.mask_text(text)


class Masker:
    """数据脱敏器。

    用法：
        masker = Masker()
        result = masker.mask_text("我的手机号是 13812345678")
        # result.masked == "我的手机号是 138****5678"
        # result.mask_map == {"138****5678": "13812345678"}

        # LLM 输出后恢复
        restored = masker.restore("您的手机号 138****5678 已验证")
        # restored == "您的手机号 13812345678 已验证"
    """

    # 邮箱：local-part@domain.tld
    _EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    # 身份证号：18 位，前 17 位数字，末位为数字或 X/x
    _ID_CARD_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
    # 手机号：11 位，以 1[3-9] 开头
    _PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
    # 银行卡号：16-19 位数字
    _BANK_CARD_RE = re.compile(r"(?<!\d)\d{16,19}(?!\d)")
    # 订单号：15-18 位数字
    _ORDER_ID_RE = re.compile(r"(?<!\d)\d{15,18}(?!\d)")
    # 门牌号：1-5 位数字 + 地址后缀（长后缀优先匹配）
    _HOUSE_NO_RE = re.compile(r"(\d{1,5})(号楼|号院|号|栋|室|楼|单元|幢|弄|支弄)")

    def __init__(self) -> None:
        self._global_map: dict[str, str] = {}

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def mask_text(self, text: str) -> MaskResult:
        """脱敏文本中的所有敏感信息。

        按优先级依次匹配：邮箱 → 身份证 → 手机号 → 银行卡 → 订单号 → 门牌号。
        每种模式替换后，占位符中的 ``*`` 会打断后续数字匹配，避免重复脱敏。
        """
        original = text
        local_map: dict[str, str] = {}

        def _replace(pattern: re.Pattern[str], fn) -> None:
            nonlocal text

            def _sub(m: re.Match[str]) -> str:
                token = m.group(0)
                masked = fn(token)
                if masked != token:
                    local_map[masked] = token
                    self._global_map[masked] = token
                return masked

            text = pattern.sub(_sub, text)

        _replace(self._EMAIL_RE, self._mask_email)
        _replace(self._ID_CARD_RE, self._mask_id_card)
        _replace(self._PHONE_RE, self._mask_phone)
        _replace(self._BANK_CARD_RE, self._mask_bank_card)
        _replace(self._ORDER_ID_RE, self._mask_order_id)
        _replace(self._HOUSE_NO_RE, self._mask_house_number)

        return MaskResult(
            original=original,
            masked=text,
            mask_map=local_map,
            _masker=self,
        )

    def mask_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """递归脱敏字典中的字符串值。

        遍历 dict / list 结构，对其中的每个 str 值调用 :meth:`mask_text`。
        """
        def _process(obj: Any) -> Any:
            if isinstance(obj, str):
                return self.mask_text(obj).masked
            if isinstance(obj, dict):
                return {k: _process(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_process(item) for item in obj]
            return obj

        return _process(data)

    def restore(self, text: str) -> str:
        """把脱敏后的文本中的占位符还原为原文。

        利用 ``_global_map`` 中记录的 masked → original 映射，
        通过单次正则替换还原所有占位符。
        """
        if not self._global_map:
            return text
        # 按长度降序排列，确保更长的占位符优先匹配（避免短占位符
        # 误匹配长占位符的子串）
        keys = sorted(self._global_map.keys(), key=len, reverse=True)
        pattern = re.compile("|".join(re.escape(k) for k in keys))
        return pattern.sub(lambda m: self._global_map[m.group(0)], text)

    def reset(self) -> None:
        """清空映射表。"""
        self._global_map.clear()

    # ------------------------------------------------------------------
    # 单项脱敏函数
    # ------------------------------------------------------------------

    @staticmethod
    def _mask_phone(token: str) -> str:
        """手机号：保留前 3 后 4，中间 ****"""
        return token[:3] + "****" + token[-4:]

    @staticmethod
    def _mask_order_id(token: str) -> str:
        """订单号：保留前 4 后 4，中间 ****"""
        return token[:4] + "****" + token[-4:]

    @staticmethod
    def _mask_id_card(token: str) -> str:
        """身份证号：保留前 6 后 4，中间 ********"""
        return token[:6] + "********" + token[-4:]

    @staticmethod
    def _mask_bank_card(token: str) -> str:
        """银行卡号：保留前 4 后 4，中间 ****"""
        return token[:4] + "****" + token[-4:]

    @staticmethod
    def _mask_email(token: str) -> str:
        """邮箱：保留首字母和 @ 后域名，中间 ***"""
        at = token.index("@")
        if at == 0:
            return token  # 本地部分为空，无法脱敏
        return token[0] + "***" + token[at:]

    @staticmethod
    def _mask_house_number(token: str) -> str:
        """门牌号：数字部分替换为 ***，保留后缀。

        token 形如 ``"123号"`` → ``"***号"``。
        """
        m = re.match(r"(\d+)(.*)", token)
        if m:
            return "***" + m.group(2)
        return token
