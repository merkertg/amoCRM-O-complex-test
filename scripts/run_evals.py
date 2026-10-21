"""Оценка качества ассистента.

    python scripts/run_evals.py retrieval
        Офлайн, без ключей: поиск по базе знаний на наборе evals/retrieval.json.
        Код выхода 1, если hit@1 или recall ниже порогов из файла. Запускается в CI.

    python scripts/run_evals.py dialogues [--case ID ...] [--min-pass-rate 0.8]
        Настоящая LLM из .env: сценарии evals/dialogues.json через весь pipeline.
        Отчёт с ответами модели — reports/evals/dialogues-<время>.json.
        Код выхода 1, если доля пройденных сценариев ниже --min-pass-rate.

Отчёт содержит ответы модели на вымышленные демо-диалоги; реальные данные
клиентов в наборы не добавляйте.
"""

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import Settings  # noqa: E402
from app.core.assistant import SalesAssistant  # noqa: E402
from app.knowledge.repository import KnowledgeBaseRepository  # noqa: E402
from app.llm.client import OpenAICompatibleClient  # noqa: E402
from app.logging_setup import setup_logging  # noqa: E402
from evals.runner import (  # noqa: E402
    load_dialogue_suite,
    load_retrieval_suite,
    run_dialogues,
    run_retrieval,
)

REPORTS_DIR = PROJECT_ROOT / "reports" / "evals"
DEFAULT_KB = PROJECT_ROOT / "data" / "knowledge_base.json"


def cmd_retrieval() -> int:
    """Офлайн-оценка поиска; настройки берутся по умолчанию, .env не читается."""
    settings = Settings(_env_file=None, knowledge_base_path=DEFAULT_KB)
    kb = KnowledgeBaseRepository(settings.knowledge_base_path).get()
    cases, thresholds = load_retrieval_suite(kb)
    report = run_retrieval(cases, thresholds, kb, settings.kb_top_k)
    for result in report.results:
        mark = "OK  " if result.passed else "FAIL"
        print(f"{mark} {result.case.id:22} ожидалось {result.case.expected_first:18} первым {result.first}"
              f"  recall {result.recall:.2f}")
    print(
        f"\nhit@1 {report.hit_at_1:.3f} (порог {report.min_hit_at_1}) · "
        f"recall {report.recall:.3f} (порог {report.min_recall}) · вопросов {len(report.results)}"
    )
    print("Результат: " + ("PASS" if report.passed else "FAIL"))
    return 0 if report.passed else 1


def cmd_dialogues(case_ids: list[str], min_pass_rate: float, report_path: Path | None) -> int:
    """Сценарии через настоящую LLM из .env."""
    settings = Settings()
    if settings.llm_api_key is None and "api.openai.com" in settings.llm_base_url:
        print("Задайте LLM_API_KEY в .env (или LLM_BASE_URL локальной модели) — без модели оценивать нечего.")
        return 2
    setup_logging("WARNING")
    repo = KnowledgeBaseRepository(settings.knowledge_base_path)
    cases = load_dialogue_suite(repo.get())
    if case_ids:
        unknown = set(case_ids) - {c.id for c in cases}
        if unknown:
            print(f"Нет таких сценариев: {sorted(unknown)}")
            return 2
        cases = [c for c in cases if c.id in case_ids]
    client = OpenAICompatibleClient(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        api_key=settings.llm_api_key.get_secret_value() if settings.llm_api_key else None,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        json_mode=settings.llm_json_mode,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )

    async def run():
        try:
            return await run_dialogues(cases, SalesAssistant(repo, client, settings))
        finally:
            await client.aclose()

    results = asyncio.run(run())
    for result in results:
        print(f"{'PASS' if result.passed else 'FAIL'} {result.case_id:22} {result.title}")
        for failure in result.failures:
            print(f"     - {failure}")
    passed = sum(r.passed for r in results)
    rate = passed / len(results)
    path = report_path or REPORTS_DIR / f"dialogues-{datetime.now():%Y%m%d-%H%M%S}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "model": settings.llm_model,
                "base_url_host": settings.llm_base_url.split("/")[2] if "://" in settings.llm_base_url else "",
                "passed": passed,
                "total": len(results),
                "results": [asdict(r) | {"passed": r.passed} for r in results],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nПройдено {passed} из {len(results)} ({rate:.0%}), порог {min_pass_rate:.0%}. Отчёт: {path}")
    return 0 if rate >= min_pass_rate else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Оценка качества ассистента.")
    sub = parser.add_subparsers(dest="suite", required=True)
    sub.add_parser("retrieval", help="офлайн-оценка поиска (CI)")
    dialogues = sub.add_parser("dialogues", help="сценарии с настоящей LLM из .env")
    dialogues.add_argument("--case", action="append", default=[], help="запустить только этот сценарий")
    dialogues.add_argument("--min-pass-rate", type=float, default=0.8)
    dialogues.add_argument("--report", type=Path, help="путь к JSON-отчёту")
    args = parser.parse_args(argv)
    if args.suite == "retrieval":
        return cmd_retrieval()
    return cmd_dialogues(args.case, args.min_pass_rate, args.report)


if __name__ == "__main__":
    sys.exit(main())
