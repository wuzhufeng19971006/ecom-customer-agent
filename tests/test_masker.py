"""数据脱敏模块单元测试。"""

import pytest

from security.data_mask.masker import MaskResult, Masker


def test_mask_phone():
    """手机号：11 位，保留前 3 后 4。"""
    masker = Masker()
    result = masker.mask_text("我的手机号是 13812345678，请联系我")
    assert result.masked == "我的手机号是 138****5678，请联系我"
    assert result.mask_map == {"138****5678": "13812345678"}


def test_mask_order_id():
    """订单号：15-18 位数字，保留前 4 后 4。"""
    masker = Masker()
    result = masker.mask_text("订单号 123456789012345 已发货")
    assert result.masked == "订单号 1234****2345 已发货"
    assert result.mask_map == {"1234****2345": "123456789012345"}


def test_mask_id_card():
    """身份证号：18 位，保留前 6 后 4。"""
    masker = Masker()
    result = masker.mask_text("身份证号 110101199003071234 已验证")
    assert result.masked == "身份证号 110101********1234 已验证"
    assert result.mask_map == {"110101********1234": "110101199003071234"}


def test_mask_id_card_with_x():
    """身份证号末位为 X 的情况。"""
    masker = Masker()
    result = masker.mask_text("身份证 11010119900307123X")
    assert result.masked == "身份证 110101********123X"
    assert "110101********123X" in result.mask_map


def test_mask_bank_card():
    """银行卡号：16-19 位，保留前 4 后 4。"""
    masker = Masker()
    result = masker.mask_text("银行卡号 6222021234567890123 已绑定")
    assert result.masked == "银行卡号 6222****0123 已绑定"
    assert result.mask_map == {"6222****0123": "6222021234567890123"}


def test_mask_email():
    """邮箱：保留首字母和 @ 后域名。"""
    masker = Masker()
    result = masker.mask_text("邮箱 john.doe@example.com 已验证")
    assert result.masked == "邮箱 j***@example.com 已验证"
    assert result.mask_map == {"j***@example.com": "john.doe@example.com"}


def test_mask_house_number():
    """门牌号：保留路名，门牌号改为 ***。"""
    masker = Masker()
    result = masker.mask_text("收货地址：中山路123号")
    assert result.masked == "收货地址：中山路***号"
    assert result.mask_map == {"***号": "123号"}


def test_mask_restore():
    """脱敏后还原：LLM 输出中的占位符替换回原文。"""
    masker = Masker()
    masker.mask_text("我的手机号是 13812345678")
    restored = masker.restore("您的手机号 138****5678 已验证通过")
    assert restored == "您的手机号 13812345678 已验证通过"


def test_mask_restore_multiple():
    """多种敏感信息混合脱敏与还原。"""
    masker = Masker()
    masker.mask_text("手机 13812345678，邮箱 test@example.com")
    restored = masker.restore("已收到 138****5678 和 t***@example.com")
    assert restored == "已收到 13812345678 和 test@example.com"


def test_mask_dict():
    """递归脱敏字典中的字符串值。"""
    masker = Masker()
    data = {
        "phone": "13812345678",
        "email": "test@example.com",
        "nested": {
            "order_id": "123456789012345",
        },
        "items": ["13812345678", "普通文本"],
        "count": 42,
    }
    result = masker.mask_dict(data)
    assert result["phone"] == "138****5678"
    assert result["email"] == "t***@example.com"
    assert result["nested"]["order_id"] == "1234****2345"
    assert result["items"][0] == "138****5678"
    assert result["items"][1] == "普通文本"
    assert result["count"] == 42  # 非字符串值保持不变


def test_mask_all_types():
    """一段文本中同时包含所有类型的敏感信息。"""
    masker = Masker()
    text = (
        "手机13812345678，订单123456789012345，"
        "身份证110101199003071234，卡号6222021234567890123，"
        "邮箱test@example.com，地址中山路88号"
    )
    result = masker.mask_text(text)
    assert "138****5678" in result.masked
    assert "1234****2345" in result.masked
    assert "110101********1234" in result.masked
    assert "6222****0123" in result.masked
    assert "t***@example.com" in result.masked
    assert "中山路***号" in result.masked
    # 原始数字不应出现在脱敏结果中
    assert "13812345678" not in result.masked
    assert "123456789012345" not in result.masked


def test_chain_call():
    """链式调用：连续脱敏多段文本，映射累积在全局表中。"""
    masker = Masker()
    result = (
        masker
        .mask_text("手机 13812345678")
        .mask_text("邮箱 a@example.com")
    )
    # 最后一次 mask_text 的结果
    assert result.masked == "邮箱 a***@example.com"
    # 两段文本的映射都应在全局表中，可用于 restore
    assert masker.restore("138****5678") == "13812345678"
    assert masker.restore("a***@example.com") == "a@example.com"


def test_reset():
    """清空映射表后 restore 不再还原。"""
    masker = Masker()
    masker.mask_text("手机 13812345678")
    assert masker.restore("138****5678") == "13812345678"
    masker.reset()
    assert masker.restore("138****5678") == "138****5678"


def test_mask_result_fields():
    """MaskResult 数据结构完整性。"""
    masker = Masker()
    result = masker.mask_text("手机 13812345678")
    assert isinstance(result, MaskResult)
    assert result.original == "手机 13812345678"
    assert result.masked == "手机 138****5678"
    assert result.mask_map == {"138****5678": "13812345678"}
