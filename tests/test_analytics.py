from io import BytesIO

import pandas as pd
import pytest

from src.analytics import TicketValidationError, analyze_tickets, build_excel_report


def sample_tickets() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticket_id": "INC-001",
                "opened_at": "2026-09-01 08:00",
                "first_response_at": "2026-09-01 08:30",
                "resolved_at": "2026-09-01 11:00",
                "status": "Fechado",
                "priority": "Alta",
                "category": "Rede",
                "technician": "Ana Lima",
                "requester_department": "Financeiro",
                "sla_target_hours": 4,
                "satisfaction_score": 5,
            },
            {
                "ticket_id": "INC-002",
                "opened_at": "2026-09-01 09:00",
                "first_response_at": "2026-09-01 10:00",
                "resolved_at": "2026-09-02 11:00",
                "status": "Solucionado",
                "priority": "Média",
                "category": "Software",
                "technician": "Bruno Costa",
                "requester_department": "RH",
                "sla_target_hours": 8,
                "satisfaction_score": 3,
            },
            {
                "ticket_id": "INC-003",
                "opened_at": "2026-09-02 08:00",
                "first_response_at": "2026-09-02 09:00",
                "resolved_at": None,
                "status": "Em atendimento",
                "priority": "Crítica",
                "category": "Acesso e senha",
                "technician": "Ana Lima",
                "requester_department": "Operações",
                "sla_target_hours": 2,
                "satisfaction_score": None,
            },
        ]
    )


def test_calculates_summary_and_sla_metrics() -> None:
    result = analyze_tickets(sample_tickets(), analysis_time="2026-09-02 12:00")

    assert result.summary["total_tickets"] == 3
    assert result.summary["resolved_tickets"] == 2
    assert result.summary["open_tickets"] == 1
    assert result.summary["overdue_tickets"] == 1
    assert result.summary["sla_compliance_rate"] == 50.0
    assert result.summary["avg_resolution_hours"] == 14.5
    assert result.summary["avg_first_response_hours"] == pytest.approx(0.83, abs=0.01)
    assert result.summary["avg_satisfaction"] == 4.0


def test_flags_met_sla_and_open_overdue_tickets() -> None:
    result = analyze_tickets(sample_tickets(), analysis_time="2026-09-02 12:00")
    tickets = result.tickets.set_index("ticket_id")

    assert bool(tickets.loc["INC-001", "met_sla"]) is True
    assert bool(tickets.loc["INC-002", "met_sla"]) is False
    assert bool(tickets.loc["INC-003", "is_overdue"]) is True


def test_builds_technician_and_category_metrics() -> None:
    result = analyze_tickets(sample_tickets(), analysis_time="2026-09-02 12:00")

    ana = result.technician_metrics.query("technician == 'Ana Lima'").iloc[0]
    network = result.category_metrics.query("category == 'Rede'").iloc[0]
    assert ana["assigned_tickets"] == 2
    assert ana["overdue_tickets"] == 1
    assert network["sla_compliance_rate"] == 100.0


def test_rejects_dataset_with_missing_columns() -> None:
    invalid = sample_tickets().drop(columns="priority")

    with pytest.raises(TicketValidationError, match="priority"):
        analyze_tickets(invalid)


def test_detects_quality_problems() -> None:
    invalid = pd.concat([sample_tickets(), sample_tickets().iloc[[0]]], ignore_index=True)
    invalid.loc[0, "first_response_at"] = "2026-08-31 07:00"
    invalid.loc[1, "satisfaction_score"] = 9

    result = analyze_tickets(invalid, analysis_time="2026-09-02 12:00")
    checks = result.quality_checks.set_index("check")
    assert checks.loc["duplicate_ticket_id", "issue_count"] == 2
    assert checks.loc["response_before_opening", "issue_count"] == 1
    assert checks.loc["invalid_satisfaction", "issue_count"] == 1


def test_excel_report_contains_expected_sheets() -> None:
    result = analyze_tickets(sample_tickets(), analysis_time="2026-09-02 12:00")
    workbook = pd.ExcelFile(BytesIO(build_excel_report(result)))

    assert set(workbook.sheet_names) == {
        "summary",
        "tickets",
        "technicians",
        "categories",
        "quality_checks",
        "daily_volume",
    }

