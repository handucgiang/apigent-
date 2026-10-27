"""Command line: ``apigent ask|tools|eval|serve``."""

from __future__ import annotations

import argparse
import asyncio
import sys

from apigent.agent import dump_trace
from apigent.config import load_agent
from apigent.context import UserContext
from apigent.evals import load_cases, run_eval, summarise


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="apigent", description="Turn your APIs into an assistant.")
    p.add_argument("-c", "--config", default="apigent.yaml", help="path to apigent.yaml")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("ask", help="ask one question")
    a.add_argument("question")
    a.add_argument("--token", help="end-user Authorization value")
    a.add_argument("--trace", action="store_true", help="print tool calls")

    sub.add_parser("tools", help="list generated tools")

    e = sub.add_parser("eval", help="run an eval file")
    e.add_argument("file")

    s = sub.add_parser("serve", help="run the HTTP server")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8080)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    agent = load_agent(args.config)

    if args.cmd == "ask":
        res = asyncio.run(agent.ask(args.question, ctx=UserContext(auth_token=args.token)))
        print(res.answer)
        if args.trace:
            print("\n" + dump_trace(res), file=sys.stderr)
        return 0

    if args.cmd == "tools":
        reg = asyncio.run(agent.registry())
        for t in reg:
            print(f"- {t.name}: {t.description.splitlines()[0][:100]}")
        return 0

    if args.cmd == "eval":
        outcomes = asyncio.run(run_eval(agent, load_cases(args.file)))
        print(summarise(outcomes))
        return 0 if all(o.passed for o in outcomes) else 1

    if args.cmd == "serve":
        import uvicorn

        from apigent.server import create_app

        uvicorn.run(create_app(agent), host=args.host, port=args.port)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
