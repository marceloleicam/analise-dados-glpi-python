"""Reusable rules for service-desk and SLA analytics.

The module is independent from Streamlit so the same logic can be reused in
scheduled jobs, notebooks, APIs and automated tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import pandas as pd


REQUIRED_COLUMNS = [
    "ticket_id",
    "opened_at",
    "first_response_at",
    "resolved_at",
    "status",
    "priority",
    "category",
    "technician",
    "requester_department",
    "sla_target_hours",
    "satisfaction_score",
]

DATETIME_COLUMNS = ["opened_at", "first_response_at", "resolved_at"]
TEXT_COLUMNS = [
    "ticket_id",
    "status",
    "priority",
    "category",
    "technician",
    "requester_department",
]
RESOLVED_STATUSES = {"solucionado", "fechado"}
OPEN_STATUSES = {"novo", "aberto", "atribuido", "em atendimento", "pendente"}


class TicketValidationError(ValueError):
    """Raised when the ticket dataset does not follow the expected schema."""


@dataclass(frozen=True)
class ServiceDeskResult:
    """Complete output of one service-desk analysis."""

    summary: dict[str, int | float]
    tickets: pd.DataFrame
    technician_metrics: pd.DataFrame
    category_metrics: pd.DataFrame
    quality_checks: pd.DataFrame
    daily_volume: pd.DataFrame
    analysis_time: pd.Timestamp


def _normalize_label(value: object) -> str:
    """Return a normalized label used only for business-rule comparisons."""

    if pd.isna(value):
        return ""
    translation = str.maketrans("áàâãéêíóôõúç", "aaaaeeiooouc")
    return str(value).strip().casefold().translate(translation)


def _validate_columns(frame: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise TicketValidationError(
            "A base não contém as colunas obrigatórias: " + ", ".join(missing) + "."
        )


def prepare_tickets(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize a ticket dataset without hiding invalid values."""

    tickets = frame.copy()
    tickets.columns = [str(column).strip().lower() for column in tickets.columns]
    _validate_columns(tickets)
    tickets = tickets[REQUIRED_COLUMNS].copy()

    for column in TEXT_COLUMNS:
        tickets[column] = tickets[column].astype("string").str.strip()
    for column in DATETIME_COLUMNS:
        tickets[column] = pd.to_datetime(tickets[column], errors="coerce")

    tickets["sla_target_hours"] = pd.to_numeric(
        tickets["sla_target_hours"], errors="coerce"
    )
    tickets["satisfaction_score"] = pd.to_numeric(
        tickets["satisfaction_score"], errors="coerce"
    )
    return tickets


def _infer_analysis_time(tickets: pd.DataFrame) -> pd.Timestamp:
    timestamps = pd.concat(
        [tickets[column].dropna() for column in DATETIME_COLUMNS], ignore_index=True
    )
    if timestamps.empty:
        raise TicketValidationError("A base não possui nenhuma data válida para análise.")
    return pd.Timestamp(timestamps.max()) + pd.offsets.Hour(1)


def _quality_checks(tickets: pd.DataFrame) -> pd.DataFrame:
    status_normalized = tickets["status"].map(_normalize_label)
    resolved = status_normalized.isin(RESOLVED_STATUSES)
    known_status = status_normalized.isin(RESOLVED_STATUSES | OPEN_STATUSES)

    checks = [
        (
            "duplicate_ticket_id",
            int(tickets.duplicated("ticket_id", keep=False).sum()),
            "Registros envolvidos em identificadores duplicados.",
        ),
        (
            "invalid_opened_at",
            int(tickets["opened_at"].isna().sum()),
            "Chamados sem data de abertura válida.",
        ),
        (
            "resolved_without_date",
            int((resolved & tickets["resolved_at"].isna()).sum()),
            "Chamados solucionados ou fechados sem data de resolução.",
        ),
        (
            "response_before_opening",
            int(
                (
                    tickets["first_response_at"].notna()
                    & tickets["opened_at"].notna()
                    & (tickets["first_response_at"] < tickets["opened_at"])
                ).sum()
            ),
            "Primeiras respostas anteriores à abertura do chamado.",
        ),
        (
            "resolution_before_opening",
            int(
                (
                    tickets["resolved_at"].notna()
                    & tickets["opened_at"].notna()
                    & (tickets["resolved_at"] < tickets["opened_at"])
                ).sum()
            ),
            "Resoluções anteriores à abertura do chamado.",
        ),
        (
            "invalid_sla_target",
            int(
                (
                    tickets["sla_target_hours"].isna()
                    | (tickets["sla_target_hours"] <= 0)
                ).sum()
            ),
            "Chamados com meta de SLA vazia, inválida ou menor que zero.",
        ),
        (
            "unknown_status",
            int((~known_status).sum()),
            "Chamados com status não reconhecido pelas regras do projeto.",
        ),
        (
            "invalid_satisfaction",
            int(
                (
                    tickets["satisfaction_score"].notna()
                    & ~tickets["satisfaction_score"].between(1, 5)
                ).sum()
            ),
            "Avaliações de satisfação fora da escala de 1 a 5.",
        ),
    ]
    return pd.DataFrame(
        [
            {
                "check": check,
                "issue_count": count,
                "status": "OK" if count == 0 else "ATENÇÃO",
                "detail": detail,
            }
            for check, count, detail in checks
        ]
    )


def _calculate_ticket_metrics(
    tickets: pd.DataFrame, analysis_time: pd.Timestamp
) -> pd.DataFrame:
    result = tickets.copy()
    result["status_normalized"] = result["status"].map(_normalize_label)
    result["is_resolved"] = result["status_normalized"].isin(RESOLVED_STATUSES)
    result["sla_due_at"] = result["opened_at"] + pd.to_timedelta(
        result["sla_target_hours"], unit="h"
    )
    result["first_response_hours"] = (
        result["first_response_at"] - result["opened_at"]
    ).dt.total_seconds() / 3600
    result["resolution_hours"] = (
        result["resolved_at"] - result["opened_at"]
    ).dt.total_seconds() / 3600

    result["met_sla"] = pd.Series(pd.NA, index=result.index, dtype="boolean")
    valid_resolved = result["is_resolved"] & result["resolved_at"].notna()
    result.loc[valid_resolved, "met_sla"] = (
        result.loc[valid_resolved, "resolved_at"]
        <= result.loc[valid_resolved, "sla_due_at"]
    )
    result["is_overdue"] = (
        ~result["is_resolved"]
        & result["sla_due_at"].notna()
        & (result["sla_due_at"] < analysis_time)
    )
    end_time = result["resolved_at"].where(result["is_resolved"], analysis_time)
    result["age_hours"] = (
        end_time - result["opened_at"]
    ).dt.total_seconds() / 3600
    result["opened_date"] = result["opened_at"].dt.date
    return result


def _build_summary(tickets: pd.DataFrame) -> dict[str, int | float]:
    resolved = tickets[tickets["is_resolved"] & tickets["resolved_at"].notna()]
    evaluated_sla = resolved["met_sla"].dropna()
    satisfaction = resolved["satisfaction_score"].dropna()

    return {
        "total_tickets": int(len(tickets)),
        "open_tickets": int((~tickets["is_resolved"]).sum()),
        "resolved_tickets": int(tickets["is_resolved"].sum()),
        "overdue_tickets": int(tickets["is_overdue"].sum()),
        "sla_compliance_rate": round(
            float(evaluated_sla.astype(bool).mean() * 100), 2
        )
        if not evaluated_sla.empty
        else 0.0,
        "avg_resolution_hours": round(float(resolved["resolution_hours"].mean()), 2)
        if not resolved.empty
        else 0.0,
        "avg_first_response_hours": round(
            float(tickets["first_response_hours"].dropna().mean()), 2
        )
        if tickets["first_response_hours"].notna().any()
        else 0.0,
        "avg_satisfaction": round(float(satisfaction.mean()), 2)
        if not satisfaction.empty
        else 0.0,
    }


def _technician_metrics(tickets: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for technician, group in tickets.groupby("technician", dropna=False):
        resolved = group[group["is_resolved"] & group["resolved_at"].notna()]
        sla = resolved["met_sla"].dropna()
        satisfaction = resolved["satisfaction_score"].dropna()
        rows.append(
            {
                "technician": technician,
                "assigned_tickets": int(len(group)),
                "resolved_tickets": int(group["is_resolved"].sum()),
                "open_tickets": int((~group["is_resolved"]).sum()),
                "overdue_tickets": int(group["is_overdue"].sum()),
                "sla_compliance_rate": round(float(sla.astype(bool).mean() * 100), 2)
                if not sla.empty
                else 0.0,
                "avg_resolution_hours": round(
                    float(resolved["resolution_hours"].mean()), 2
                )
                if not resolved.empty
                else 0.0,
                "avg_satisfaction": round(float(satisfaction.mean()), 2)
                if not satisfaction.empty
                else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["resolved_tickets", "sla_compliance_rate"], ascending=[False, False]
    )


def _category_metrics(tickets: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for category, group in tickets.groupby("category", dropna=False):
        resolved = group[group["is_resolved"] & group["resolved_at"].notna()]
        sla = resolved["met_sla"].dropna()
        rows.append(
            {
                "category": category,
                "total_tickets": int(len(group)),
                "open_tickets": int((~group["is_resolved"]).sum()),
                "overdue_tickets": int(group["is_overdue"].sum()),
                "sla_compliance_rate": round(float(sla.astype(bool).mean() * 100), 2)
                if not sla.empty
                else 0.0,
                "avg_resolution_hours": round(
                    float(resolved["resolution_hours"].mean()), 2
                )
                if not resolved.empty
                else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values("total_tickets", ascending=False)


def analyze_tickets(
    frame: pd.DataFrame, *, analysis_time: str | pd.Timestamp | None = None
) -> ServiceDeskResult:
    """Process tickets and calculate operational and SLA indicators."""

    prepared = prepare_tickets(frame)
    reference = (
        pd.Timestamp(analysis_time)
        if analysis_time is not None
        else _infer_analysis_time(prepared)
    )
    quality = _quality_checks(prepared)
    tickets = _calculate_ticket_metrics(prepared, reference)

    daily = (
        tickets.groupby("opened_date", dropna=False)
        .size()
        .reset_index(name="opened_tickets")
        .sort_values("opened_date")
    )
    return ServiceDeskResult(
        summary=_build_summary(tickets),
        tickets=tickets,
        technician_metrics=_technician_metrics(tickets),
        category_metrics=_category_metrics(tickets),
        quality_checks=quality,
        daily_volume=daily,
        analysis_time=reference,
    )


def build_excel_report(result: ServiceDeskResult) -> bytes:
    """Create an Excel workbook with the analysis and supporting details."""

    output = BytesIO()
    summary = pd.DataFrame(
        [{"metric": key, "value": value} for key, value in result.summary.items()]
    )
    export_tickets = result.tickets.drop(columns=["status_normalized"])
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="summary", index=False)
        export_tickets.to_excel(writer, sheet_name="tickets", index=False)
        result.technician_metrics.to_excel(
            writer, sheet_name="technicians", index=False
        )
        result.category_metrics.to_excel(writer, sheet_name="categories", index=False)
        result.quality_checks.to_excel(
            writer, sheet_name="quality_checks", index=False
        )
        result.daily_volume.to_excel(writer, sheet_name="daily_volume", index=False)
    return output.getvalue()
