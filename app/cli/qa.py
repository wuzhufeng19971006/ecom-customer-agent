"""命令行答疑调试脚本。

用法：
    python -m app.cli.qa "你们的尺码准吗"
    python -m app.cli.qa --interactive
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.agent.qa import QAService
from app.core.logging import setup_logging


async def ask_once(question: str) -> None:
    svc = QAService()
    r = await svc.answer(question)
    print("\n" + "=" * 60)
    print("顾客问题：", question)
    print("-" * 60)
    print("回复：", r.answer)
    print("-" * 60)
    print(f"命中知识库：{r.matched} | 召回片段数：{len(r.sources)}")
    for i, s in enumerate(r.sources, 1):
        print(f"  [{i}] score={s.score:.4f} | {s.text[:80]}...")
    print("=" * 60)


async def interactive() -> None:
    print("客服答疑调试，输入问题开始（exit 退出）：")
    while True:
        try:
            q = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            return
        if q.lower() in ("exit", "quit", "q"):
            return
        if not q:
            continue
        await ask_once(q)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question", nargs="?", help="单次提问")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互模式")
    args = parser.parse_args()

    setup_logging()

    if args.interactive:
        asyncio.run(interactive())
    elif args.question:
        asyncio.run(ask_once(args.question))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
