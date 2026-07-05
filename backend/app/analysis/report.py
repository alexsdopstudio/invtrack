"""Opt-in AI analysis of 10-K sections with the user's own Claude API key.

The model does semantic analysis only — it is explicitly told that all
financial numbers come from structured sources and it must not compute
ratios. Reports are cached per accession number so re-running is free unless
a newer 10-K has been filed."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..ingestion import http
from ..models import AiReport, DimTicker
from .edgar_sections import SECTIONS, fetch_latest_10k_sections

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a cynical, hyper-analytical forensic accountant and former short-seller \
reviewing sections of a company's official 10-K filing. Your job is to find what \
management is downplaying, not to summarize their marketing.

Rules:
- Base every claim strictly on the provided filing text. If the text does not \
answer a question, say "not disclosed in the provided sections" — never guess.
- Do NOT compute financial ratios or metrics; numbers are handled by a separate \
structured pipeline. You may quote figures the filing states verbatim.
- Quote short passages (with the item they came from) as evidence for the most \
important findings.

Produce a markdown report with exactly these sections:

## Verdict
2-3 sentences: the single most important thing a potential investor should \
understand from this filing, in plain language.

## Red flags
The concerning items, most serious first. Specifically check: customer \
concentration (any customer >20% of revenue), outstanding or threatened \
litigation / IP disputes, going-concern or liquidity language, reliance on a \
single supplier/platform/regulatory approval, related-party transactions, \
downward guidance revisions or hedged outlook language.

## Moat & business quality
Summarize the company's core advantage in 3 sentences using precise technical \
or industry terminology, then state — bluntly — how defensible it actually is.

## Management tone
Is the MD&A candid or promotional? Note hedging language, blame-shifting, or \
changes in how they describe the business versus their stated risks.

## What to verify next
3-5 concrete follow-up checks a diligent researcher should do (specific \
filings, metrics, or external sources)."""


class AnalysisError(Exception):
    """User-actionable analysis failure (bad key, no filing, rate limit)."""


def analysis_enabled() -> bool:
    return bool(get_settings().anthropic_api_key)


def build_user_prompt(ticker: str, name: str | None, sections: dict[str, str]) -> str:
    parts = [
        f"Company: {name or ticker} (ticker {ticker}).",
        "Below are sections extracted from the company's latest 10-K filing "
        "(each may be truncated to a length budget).",
    ]
    for key, content in sections.items():
        parts.append(f"\n<section name=\"{SECTIONS[key]}\">\n{content}\n</section>")
    parts.append("\nWrite the report now.")
    return "\n".join(parts)


def latest_report(db: Session, ticker: str) -> AiReport | None:
    return db.scalar(
        select(AiReport)
        .where(AiReport.ticker == ticker)
        .order_by(AiReport.created_at.desc())
        .limit(1)
    )


def _call_claude(system: str, user_prompt: str) -> str:
    import anthropic

    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    try:
        # Streaming: filing sections make this a long-input request.
        with client.messages.stream(
            model=settings.analysis_model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            message = stream.get_final_message()
    except anthropic.AuthenticationError as exc:
        raise AnalysisError(
            "Claude API key rejected — check ANTHROPIC_API_KEY in .env"
        ) from exc
    except anthropic.RateLimitError as exc:
        raise AnalysisError("Claude API rate limit hit — try again in a minute") from exc
    except anthropic.APIStatusError as exc:
        raise AnalysisError(f"Claude API error {exc.status_code}: {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise AnalysisError(f"could not reach the Claude API: {exc}") from exc

    if message.stop_reason == "refusal":
        raise AnalysisError("the model declined to analyze this filing")
    text = "".join(block.text for block in message.content if block.type == "text")
    if not text.strip():
        raise AnalysisError("the model returned an empty report")
    return text


def analyze(db: Session, ticker: str, force: bool = False) -> AiReport:
    """Fetch the latest 10-K sections and produce (or reuse) a report."""
    if not analysis_enabled():
        raise AnalysisError(
            "AI analysis is disabled — set ANTHROPIC_API_KEY in .env to enable it"
        )
    dim = db.get(DimTicker, ticker)
    if dim is None or not dim.cik:
        raise AnalysisError(
            f"no SEC CIK known for {ticker} — run the 'tickers' ingestion first"
        )

    with http.client() as client:
        result = fetch_latest_10k_sections(client, dim.cik)
    if result is None:
        raise AnalysisError(f"no 10-K found in EDGAR's recent filings for {ticker}")
    sections, meta = result
    if not sections:
        raise AnalysisError(
            f"could not extract Item 1/1A/7 from {ticker}'s 10-K — filing layout "
            "not recognized"
        )

    # Cost control: reuse the cached report for the same accession.
    existing = latest_report(db, ticker)
    if existing is not None and existing.accession_no == meta["accession_no"] and not force:
        return existing

    settings = get_settings()
    report_md = _call_claude(SYSTEM_PROMPT, build_user_prompt(ticker, dim.name, sections))
    report = AiReport(
        ticker=ticker,
        accession_no=meta["accession_no"],
        model=settings.analysis_model,
        report_md=report_md,
        sections_meta=meta,
    )
    db.add(report)
    db.commit()
    return report
