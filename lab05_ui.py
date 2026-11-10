"""Local Lab 5 interface for the existing Lab 4 team.

Run with: .venv/bin/streamlit run lab05_ui.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Callable

import streamlit as st

import report_workflow as desk
from lab04_team import ROOT, LazyGoogle, Team, new_folder


NODE_ORDER = [
    "steps",
    "Research Analyst",
    "Financial Analyst",
    "Investment Advisor",
    "Strategy Manager",
    "Verifier",
]


def parse_request(ticker: str, peers_text: str, price_text: str) -> tuple[str, list[str], float | None]:
    """Validate UI input before the workflow touches saved data or a provider."""
    ticker = ticker.strip().upper()
    if not ticker or not ticker.replace("-", "").isalnum():
        raise ValueError("Enter a ticker using letters, numbers, or hyphens.")
    peers = list(dict.fromkeys(
        part.strip().upper() for part in peers_text.split(",") if part.strip()
    ))
    if any(not peer.replace("-", "").isalnum() for peer in peers):
        raise ValueError("Separate peer tickers with commas.")
    if not price_text.strip():
        return ticker, peers, None
    try:
        price = float(price_text)
    except ValueError as error:
        raise ValueError("Price must be a positive number.") from error
    if not math.isfinite(price) or price <= 0:
        raise ValueError("Price must be a positive number.")
    return ticker, peers, price


class ProgressTeam(Team):
    """Adds UI callbacks around the unchanged Lab 4 node implementations."""

    def __init__(self, *args, on_progress: Callable[[str, str], None], **kwargs):
        super().__init__(*args, **kwargs)
        self.on_progress = on_progress

    def event(self, node, inputs, output):
        super().event(node, inputs, output)
        display = node.removeprefix("revise_")
        if display in NODE_ORDER:
            self.on_progress(display, "complete")

    def steps(self, state):
        self.on_progress("steps", "running")
        return super().steps(state)

    def role(self, role, state):
        self.on_progress(role, "running")
        return super().role(role, state)

    def verifier(self, state):
        self.on_progress("Verifier", "running")
        return super().verifier(state)


def load_marks(folder: Path) -> list[dict]:
    """Load the saved verifier marks after the workflow has completed."""
    records = sorted(folder.glob("verification_round_*.json"))
    if not records:
        return []
    try:
        marks = json.loads(records[-1].read_text(encoding="utf-8")).get("marks", [])
    except (OSError, ValueError):
        return []
    return marks if isinstance(marks, list) else []


def safe_error(summary: dict) -> str:
    """Show only errors already sanitized by the workflow."""
    errors = summary.get("errors", []) if isinstance(summary, dict) else []
    return "; ".join(str(item) for item in errors) or "The run did not complete."


def run_workflow(
    ticker: str,
    peers: list[str],
    price: float | None,
    saved_source: str,
    model_name: str,
    on_progress: Callable[[str, str], None],
) -> tuple[Path, dict]:
    """Create a separate Lab 4 run folder and execute the existing team unchanged."""
    source = Path(saved_source).expanduser() if saved_source.strip() else None
    if source:
        company = desk.load(source, "company.json")
        if company.get("ticker", "").upper() != ticker:
            raise desk.ReportError("Saved evidence ticker does not match the ticker field.")
    else:
        company = {"name": ticker}
    folder = new_folder(company.get("name") or ticker, ROOT / "lab04_runs")
    team = ProgressTeam(
        folder,
        LazyGoogle(model_name.strip()),
        source=source,
        ticker=ticker,
        peers=peers,
        price=price,
        on_progress=on_progress,
    )
    return folder, team.run()


def main() -> None:
    st.set_page_config(page_title="Lab 5 Equity Desk", layout="wide")
    st.title("Lab 5 Equity Desk")
    st.caption("This interface invokes the existing Lab 4 graph without changing its order.")

    with st.form("run_form"):
        left, middle, right = st.columns(3)
        ticker = left.text_input("Ticker", placeholder="Example: ABC")
        peers_text = middle.text_input("Peers (optional, comma-separated)", placeholder="XYZ, DEF")
        price_text = right.text_input("Price (optional)", placeholder="Instructor-supplied price")
        with st.expander("Saved evidence (optional)"):
            saved_source = st.text_input(
                "Saved evidence folder",
                help="Reuses the saved seven-step evidence and does not download filings again.",
            )
            model_name = st.text_input("Model", value="models/gemini-2.5-flash")
        submitted = st.form_submit_button("Run")

    if not submitted:
        return
    try:
        ticker, peers, price = parse_request(ticker, peers_text, price_text)
    except ValueError as error:
        st.error(str(error))
        return

    states = {node: "waiting" for node in NODE_ORDER}
    progress = st.empty()

    def show_progress(node: str, state: str) -> None:
        states[node] = state
        labels = [f"{'●' if states[name] == 'complete' else '◐' if states[name] == 'running' else '○'} {name}" for name in NODE_ORDER]
        progress.markdown("  \n".join(labels))

    show_progress("steps", "waiting")
    try:
        with st.spinner("The team is running. Each node saves its input and output in its run folder."):
            folder, summary = run_workflow(ticker, peers, price, saved_source, model_name, show_progress)
    except desk.ReportError as error:
        st.error(str(error))
        return
    except OSError:
        st.error("The local run could not be created or read.")
        return

    report_path = folder / "verified_report.md"
    st.subheader("Verified report")
    st.code(str(report_path), language=None)
    if report_path.exists():
        st.markdown(report_path.read_text(encoding="utf-8"))
    else:
        st.error("No verified report was saved.")

    st.subheader("Verifier marks")
    marks = load_marks(folder)
    if marks:
        st.dataframe(marks, use_container_width=True)
    else:
        st.info("No verifier marks were saved. " + safe_error(summary))


if __name__ == "__main__":
    main()
