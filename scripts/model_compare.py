"""DeepSeek V4 Flash (GA) vs V4 Pro (Preview) 逻辑强小说写作对比测试。

同一个逻辑密集的写作任务，两个模型各跑一次，输出对比供人工评估。
"""
import asyncio
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

API_BASE = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com").rstrip("/")
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

PROMPT = """写一段 800 字以内的古风仙侠小说开头，必须满足以下逻辑约束（违反任何一条都算失败）：

1. 时间线：故事发生在「焚天宗灭门事件」三年后。主角周砚是唯一幸存弟子，如今化名潜伏在仇家叶家当杂役。叶家老祖三年前在灭门现场"力挽狂澜"、声望暴涨。
2. 信息差：只有读者知道周砚的真实身份；叶家所有人都以为他是普通杂役。
3. 关键伏笔：周砚随身带着一枚从不离身的铜镜——那是灭门之夜师父临终塞给他的。铜镜背面刻着"三"字。本章结尾必须让铜镜第一次在叶家老祖面前出现，且老祖看到铜镜后有一个异常反应，但周砚没注意到。
4. 因果闭环：本章要出现一个"周砚故意为之"的小动作（比如故意打碎一个值钱的碗），它必须同时达成两个目的：让叶家管家觉得他毛手毛脚（降低戒心），以及让他能靠近叶家老祖的丹房。
5. 禁止直白交代"周砚是主角""这是伏笔"，一切通过动作和细节呈现。

直接输出小说正文，不要任何解释。"""


async def call_model(model: str) -> tuple[str, float]:
    async with httpx.AsyncClient(timeout=120) as client:
        t0 = time.time()
        resp = await client.post(
            f"{API_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": PROMPT}],
                "temperature": 0.7,
                "max_tokens": 1200,
                "stream": False,
            },
        )
        elapsed = time.time() - t0
        if resp.status_code != 200:
            return f"HTTP {resp.status_code}: {resp.text[:200]}", elapsed
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return (
            f"{content}\n\n[usage: prompt={usage.get('prompt_tokens')} "
            f"completion={usage.get('completion_tokens')} total={usage.get('total_tokens')}]",
            elapsed,
        )


async def main() -> None:
    for model in ["deepseek-v4-flash", "deepseek-v4-pro"]:
        print("=" * 60)
        print(f"模型: {model}")
        print("=" * 60)
        try:
            content, elapsed = await call_model(model)
            print(f"耗时: {elapsed:.1f}s")
            print(content)
        except Exception as e:  # noqa: BLE001
            print(f"调用失败: {type(e).__name__}: {e}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
