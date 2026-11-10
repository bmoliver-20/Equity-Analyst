# Lab 5 local interface

Run the local interface with:

```sh
.venv/bin/streamlit run lab05_ui.py
```

Enter a ticker, optional comma-separated peers, and an optional instructor-supplied price. The optional saved-evidence folder reuses the saved seven-step inputs and avoids new SEC downloads.

The interface imports `Team` from `lab04_team.py`; it does not modify the LangGraph graph. It displays the fixed sequence `steps`, Research Analyst, Financial Analyst, Investment Advisor, Strategy Manager, and Verifier as each node starts or completes. Each click creates a separate folder under `lab04_runs/`, then displays that run's `verified_report.md` and saved verifier marks.
