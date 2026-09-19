from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analytics import TicketValidationError, analyze_tickets, build_excel_report


BASE_DIR = Path(__file__).resolve().parent
SAMPLE_FILE = BASE_DIR / "data" / "sample_tickets.csv"

st.set_page_config(
    page_title="GLPI Service Desk Analytics",
    layout="wide",
)


@st.cache_data
def load_sample_data() -> pd.DataFrame:
    return pd.read_csv(SAMPLE_FILE)


st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.35rem;
            padding-bottom: 2rem;
            max-width: 1480px;
        }
        .glpi-hero {
            position: relative;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 2rem;
            padding: 1.55rem 1.8rem;
            margin-bottom: 1.15rem;
            border: 1px solid rgba(96, 165, 250, 0.22);
            border-radius: 22px;
            background: radial-gradient(circle at 85% 25%, rgba(37, 99, 235, 0.32), transparent 32%), linear-gradient(120deg, #071426 0%, #0b2341 55%, #123765 100%);
            box-shadow: 0 18px 45px rgba(15, 23, 42, 0.16);
        }
        .glpi-hero::after {
            content: "";
            position: absolute;
            width: 220px;
            height: 220px;
            right: -80px;
            bottom: -150px;
            border: 26px solid rgba(147, 197, 253, 0.12);
            border-radius: 50%;
        }
        .glpi-kicker {
            display: inline-block;
            margin-bottom: 0.5rem;
            color: #93c5fd;
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.16em;
            text-transform: uppercase;
        }
        .glpi-hero h1 {
            margin: 0;
            color: #ffffff;
            font-size: clamp(1.65rem, 3vw, 2.65rem);
            line-height: 1.08;
            letter-spacing: -0.035em;
        }
        .glpi-hero p {
            max-width: 730px;
            margin: 0.65rem 0 0;
            color: #cbd5e1;
            font-size: 0.96rem;
            line-height: 1.55;
        }
        .monitor-badge {
            position: relative;
            z-index: 1;
            display: inline-flex;
            align-items: center;
            gap: 0.55rem;
            flex: 0 0 auto;
            padding: 0.65rem 0.9rem;
            color: #dcfce7;
            font-size: 0.73rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            white-space: nowrap;
            text-transform: uppercase;
            border: 1px solid rgba(74, 222, 128, 0.3);
            border-radius: 999px;
            background: rgba(22, 163, 74, 0.16);
        }
        .monitor-dot {
            width: 9px;
            height: 9px;
            border-radius: 50%;
            background: #4ade80;
            box-shadow: 0 0 0 5px rgba(74, 222, 128, 0.12);
        }
        .ticket-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.85rem;
            margin-bottom: 0.85rem;
        }
        .ticket-card {
            padding: 1rem 1.05rem;
            border: 1px solid #e2e8f0;
            border-radius: 16px;
            background: #ffffff;
            box-shadow: 0 7px 20px rgba(15, 23, 42, 0.055);
        }
        .ticket-card .label {
            color: #64748b;
            font-size: 0.76rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.055em;
        }
        .ticket-card .value {
            margin-top: 0.32rem;
            color: #0f172a;
            font-size: 1.85rem;
            font-weight: 800;
            line-height: 1;
        }
        .ticket-card .detail {
            margin-top: 0.45rem;
            color: #94a3b8;
            font-size: 0.76rem;
        }
        .ticket-card.total { border-top: 4px solid #2563eb; }
        .ticket-card.open { border-top: 4px solid #f59e0b; }
        .ticket-card.resolved { border-top: 4px solid #16a34a; }
        .ticket-card.overdue { border-top: 4px solid #dc2626; }
        .service-health {
            display: grid;
            grid-template-columns: 1.35fr 2fr;
            gap: 0.85rem;
            margin-bottom: 1.25rem;
        }
        .sla-panel, .service-stats {
            border: 1px solid #dbe4ee;
            border-radius: 18px;
            background: #f8fafc;
        }
        .sla-panel { padding: 1rem 1.15rem; }
        .sla-heading {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 1rem;
        }
        .sla-title { color: #475569; font-size: 0.78rem; font-weight: 750; }
        .sla-value { color: #0f172a; font-size: 1.65rem; font-weight: 850; line-height: 1; margin-top: 10px;}
        .sla-status { font-size: 0.76rem; font-weight: 800; }
        .sla-track {
            height: 9px;
            margin: 0.8rem 0 0.55rem;
            overflow: hidden;
            border-radius: 999px;
            background: #e2e8f0;
        }
        .sla-fill { height: 100%; border-radius: inherit; }
        .sla-note { color: #64748b; font-size: 0.74rem; }
        .service-stats {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            overflow: hidden;
        }
        .service-stat { padding: 1rem 1.1rem; }
        .service-stat + .service-stat { border-left: 1px solid #dbe4ee; }
        .service-stat span { display: block; color: #64748b; font-size: 0.73rem; font-weight: 700; }
        .service-stat strong { display: block; margin-top: 0.35rem; color: #0f172a; font-size: 1.35rem; }
        .service-stat small { color: #94a3b8; font-size: 0.7rem; }
        @media (max-width: 900px) {
            .glpi-hero { align-items: flex-start; flex-direction: column; }
            .ticket-grid { grid-template-columns: repeat(2, 1fr); }
            .service-health { grid-template-columns: 1fr; }
        }
        @media (max-width: 560px) {
            .ticket-grid, .service-stats { grid-template-columns: 1fr; }
            .service-stat + .service-stat { border-top: 1px solid #dbe4ee; border-left: 0; }
        }
    </style>
    <section class="glpi-hero">
        <div>
            <span class="glpi-kicker">Central de serviços • Visão operacional</span>
            <h1>Análise de Dados GLPI</h1>
        </div>
        <div class="monitor-badge"><span class="monitor-dot"></span> Monitoramento ativo</div>
    </section>
    """,
    unsafe_allow_html=True,
)


with st.sidebar:
    st.header("Fonte de dados", anchor=False)
    use_sample = st.toggle("Usar dados de demonstração", value=True)
    uploaded_file = None
    if not use_sample:
        uploaded_file = st.file_uploader("Arquivo de chamados", type="csv")
   

if use_sample:
    source = load_sample_data()
elif uploaded_file is None:
    st.warning("Envie um arquivo CSV para iniciar a análise.")
    st.stop()
else:
    raw = pd.read_csv(
        uploaded_file,
        sep=None,
        engine="python",
        encoding="utf-8-sig",
    )

    raw = raw.dropna(axis=1, how="all")

    opened_at = pd.to_datetime(
        raw["Data de abertura"],
        format="%d-%m-%Y %H:%M",
        errors="coerce",
    )

    resolved_at = pd.to_datetime(
        raw["Data da solução"],
        format="%d-%m-%Y %H:%M",
        errors="coerce",
    )

    sla_due_at = pd.to_datetime(
        raw["Tempo para solução"],
        format="%d-%m-%Y %H:%M",
        errors="coerce",
    )

    status = raw["Status"].replace(
        {
            "Processando (atribuído)": "Em atendimento",
            "Processando (planejado)": "Em atendimento",
        }
    )

    source = pd.DataFrame(
        {
            "ticket_id": raw["ID"],
            "opened_at": opened_at,

            # Esta informação não existe no CSV exportado.
            "first_response_at": pd.NaT,

            "resolved_at": resolved_at,
            "status": status,
            "priority": raw["Prioridade"],
            "category": raw["Categoria"],
            "technician": raw["Atribuído para - Técnico"],
            "requester_department": raw["Entidade"],

            # Converte o prazo final do GLPI em quantidade de horas.
            "sla_target_hours": (
                sla_due_at - opened_at
            ).dt.total_seconds() / 3600,

            "satisfaction_score": pd.to_numeric(
                raw["Pesquisa de satisfação - Satisfação"],
                errors="coerce",
            ),
        }
    )

try:
    initial_result = analyze_tickets(source)
except TicketValidationError as error:
    st.error(str(error))
    st.stop()
except Exception as error:  # pragma: no cover - UI safety boundary
    st.error(f"Não foi possível processar o arquivo: {error}")
    st.stop()

tickets = initial_result.tickets

with st.sidebar:
    st.header("Filtros")
    statuses = sorted(tickets["status"].dropna().unique())
    priorities = sorted(tickets["priority"].dropna().unique())
    categories = sorted(tickets["category"].dropna().unique())
    technicians = sorted(tickets["technician"].dropna().unique())
    selected_statuses = st.multiselect("Status", statuses, default=statuses)
    selected_priorities = st.multiselect("Prioridade", priorities, default=priorities)
    selected_categories = st.multiselect("Categoria", categories, default=categories)
    selected_technicians = st.multiselect(
        "Técnico", technicians, default=technicians
    )

filtered_source = tickets[
    tickets["status"].isin(selected_statuses)
    & tickets["priority"].isin(selected_priorities)
    & tickets["category"].isin(selected_categories)
    & tickets["technician"].isin(selected_technicians)
]

if filtered_source.empty:
    st.warning("Nenhum chamado corresponde aos filtros selecionados.")
    st.stop()

result = analyze_tickets(filtered_source, analysis_time=initial_result.analysis_time)
summary = result.summary

sla_rate = summary["sla_compliance_rate"]
if sla_rate >= 90:
    sla_status = "Dentro da meta"
    sla_color = "#16a34a"
elif sla_rate >= 75:
    sla_status = "Ponto de atenção"
    sla_color = "#f59e0b"
else:
    sla_status = "Abaixo da meta"
    sla_color = "#dc2626"

st.markdown(
    f"""
    <section class="ticket-grid">
        <article class="ticket-card total">
            <div class="label">Total de chamados</div>
            <div class="value">{summary['total_tickets']}</div>
            <div class="detail">Volume considerado nos filtros</div>
        </article>
        <article class="ticket-card open">
            <div class="label">Em aberto</div>
            <div class="value">{summary['open_tickets']}</div>
            <div class="detail">Demandas em acompanhamento</div>
        </article>
        <article class="ticket-card resolved">
            <div class="label">Resolvidos</div>
            <div class="value">{summary['resolved_tickets']}</div>
            <div class="detail">Atendimentos concluídos</div>
        </article>
        <article class="ticket-card overdue">
            <div class="label">Atrasados</div>
            <div class="value">{summary['overdue_tickets']}</div>
            <div class="detail">Chamados que exigem ação</div>
        </article>
    </section>
    <section class="service-health">
        <article class="sla-panel">
            <div class="sla-heading">
                <div>
                    <div class="sla-title">Cumprimento geral do SLA</div>
                    <div class="sla-value">{sla_rate:.1f}%</div>
                </div>
                <div class="sla-status" style="color: {sla_color};">{sla_status}</div>
            </div>
            <div class="sla-track">
                <div class="sla-fill" style="width: {min(max(sla_rate, 0), 100):.1f}%; background: {sla_color};"></div>
            </div>
        </article>
        <article class="service-stats">
            <div class="service-stat">
                <span>Tempo médio de resolução</span>
                <strong>{summary['avg_resolution_hours']:.1f} h</strong>
                <small>Chamados concluídos</small>
            </div>
            <div class="service-stat">
                <span>Primeira resposta</span>
                <strong>{summary['avg_first_response_hours']:.1f} h</strong>
                <small>Tempo médio de retorno</small>
            </div>
            <div class="service-stat">
                <span>Satisfação média</span>
                <strong>{summary['avg_satisfaction']:.1f} / 5</strong>
                <small>Avaliação dos usuários</small>
            </div>
        </article>
    </section>
    """,
    unsafe_allow_html=True,
)

overview_tab, sla_tab, team_tab, data_tab = st.tabs(
    ["Visão geral", "SLA e atrasos", "Equipe", "Dados e qualidade"]
)

with overview_tab:
    left, right = st.columns(2)
    with left:
        st.subheader("Chamados por status", anchor=False)
        status_count = (
            result.tickets["status"]
            .value_counts()
            .rename_axis("status")
            .reset_index(name="tickets")
        )
        figure = px.bar(
            status_count,
            x="status",
            y="tickets",
            color="status",
            labels={"status": "Status", "tickets": "Chamados"},
        )
        figure.update_layout(showlegend=False)
        st.plotly_chart(figure, width="stretch")
    with right:
        st.subheader("Chamados por categoria", anchor=False)
        figure = px.bar(
            result.category_metrics,
            x="total_tickets",
            y="category",
            orientation="h",
            color="total_tickets",
            labels={"total_tickets": "Chamados", "category": "Categoria"},
            color_continuous_scale="Blues",
        )
        figure.update_layout(coloraxis_showscale=False)
        st.plotly_chart(figure, width="stretch")

    st.subheader("Volume diário de aberturas", anchor=False)
    daily_chart = px.line(
        result.daily_volume,
        x="opened_date",
        y="opened_tickets",
        markers=True,
        labels={"opened_date": "Data", "opened_tickets": "Chamados abertos"},
    )
    st.plotly_chart(daily_chart, width="stretch")

with sla_tab:
    left, right = st.columns([1, 1])
    with left:
        st.subheader("Cumprimento de SLA por categoria", anchor=False)
        sla_chart = px.bar(
            result.category_metrics,
            x="category",
            y="sla_compliance_rate",
            color="sla_compliance_rate",
            range_y=[0, 100],
            labels={
                "category": "Categoria",
                "sla_compliance_rate": "SLA cumprido (%)",
            },
            color_continuous_scale="RdYlGn",
        )
        sla_chart.update_layout(coloraxis_showscale=False)
        st.plotly_chart(sla_chart, width="stretch")
    with right:
        st.subheader("Chamados em atraso", anchor=False)
        overdue = result.tickets[result.tickets["is_overdue"]].copy()
        if overdue.empty:
            st.success("Nenhum chamado aberto está fora do prazo.")
        else:
            overdue_table = overdue[
                [
                    "ticket_id",
                    "priority",
                    "category",
                    "technician",
                    "sla_due_at",
                    "age_hours",
                ]
            ].sort_values("age_hours", ascending=False)

            overdue_table = overdue_table.copy()

            overdue_table["sla_due_at"] = overdue_table[
                "sla_due_at"
            ].dt.strftime("%d/%m/%Y %H:%M")

            def format_open_time(value):
                if pd.isna(value):
                    return "Não informado"

                total_minutes = round(float(value) * 60)
                days, remaining_minutes = divmod(total_minutes, 1440)
                hours, minutes = divmod(remaining_minutes, 60)

                if days > 0:
                    return f"{days}d {hours}h {minutes}min"

                if hours > 0:
                    return f"{hours}h {minutes}min"

                return f"{minutes}min"


            overdue_table["age_hours"] = overdue_table[
                "age_hours"
            ].apply(format_open_time)

            overdue_table = overdue_table.rename(
                columns={
                    "ticket_id": "ID do chamado",
                    "priority": "Prioridade",
                    "category": "Categoria",
                    "technician": "Técnico",
                    "sla_due_at": "Prazo do SLA",
                    "age_hours": "Tempo em aberto",
                }
            )

            st.dataframe(
                overdue_table,
                width="stretch",
                hide_index=True,
            )

with team_tab:
    st.subheader("Indicadores por técnico", anchor=False)

    technician_table = result.technician_metrics.copy()

    def format_sla(row):
        if row["resolved_tickets"] == 0:
            return "Não avaliado"

        return f'{row["sla_compliance_rate"]:.0f}%'

    def format_resolution_time(row):
        if row["resolved_tickets"] == 0:
            return "Não avaliado"

        value = row["avg_resolution_hours"]

        if pd.isna(value):
            return "Não avaliado"

        total_minutes = round(float(value) * 60)
        days, remaining_minutes = divmod(total_minutes, 1440)
        hours, minutes = divmod(remaining_minutes, 60)

        if days > 0:
            return f"{days}d {hours}h {minutes}min"

        if hours > 0:
            return f"{hours}h {minutes}min"

        return f"{minutes}min"

    technician_table["sla_compliance_rate"] = (
        technician_table.apply(format_sla, axis=1)
    )

    technician_table["avg_resolution_hours"] = (
        technician_table.apply(format_resolution_time, axis=1)
    )

    technician_table["avg_satisfaction"] = technician_table.apply(
        lambda row: (
            "Não avaliado"
            if row["resolved_tickets"] == 0
            else f'{row["avg_satisfaction"]:.2f}'.replace(".", ",")
        ),
        axis=1,
    )

    technician_table = technician_table.rename(
        columns={
            "technician": "Técnico",
            "assigned_tickets": "Chamados atribuídos",
            "resolved_tickets": "Chamados resolvidos",
            "open_tickets": "Chamados abertos",
            "overdue_tickets": "Chamados atrasados",
            "sla_compliance_rate": "SLA cumprido",
            "avg_resolution_hours": "Tempo médio de resolução",
            "avg_satisfaction": "Satisfação média",
        }
    )

    st.dataframe(
        technician_table,
        width="stretch",
        hide_index=True,
    )

    team_chart = px.scatter(
        result.technician_metrics,
        x="avg_resolution_hours",
        y="sla_compliance_rate",
        size="resolved_tickets",
        color="technician",
        hover_name="technician",
        labels={
            "avg_resolution_hours": "Tempo médio de resolução (h)",
            "sla_compliance_rate": "SLA cumprido (%)",
            "resolved_tickets": "Chamados resolvidos",
            "technician": "Técnico",
        },
    )

    st.plotly_chart(team_chart, width="stretch")


with data_tab:
    quality_tab, tickets_tab = st.tabs(
        ["Qualidade dos dados", "Chamados processados"]
    )

    with quality_tab:
        quality_table = result.quality_checks.copy()

        quality_table["check"] = quality_table["check"].replace(
            {
                "duplicate_ticket_id": "ID de chamado duplicado",
                "invalid_opened_at": "Data de abertura inválida",
                "resolved_without_date": "Resolvido sem data de solução",
                "response_before_opening": "Resposta anterior à abertura",
                "resolution_before_opening": "Solução anterior à abertura",
                "invalid_sla_target": "Meta de SLA inválida",
                "unknown_status": "Status não reconhecido",
                "invalid_satisfaction": "Satisfação inválida",
            }
        )

        quality_table = quality_table.rename(
            columns={
                "check": "Verificação",
                "issue_count": "Quantidade de problemas",
                "status": "Situação",
                "detail": "Descrição",
            }
        )

        st.dataframe(
            quality_table,
            width="stretch",
            hide_index=True,
        )

    with tickets_tab:
        display_columns = [
            "ticket_id",
            "opened_at",
            "status",
            "priority",
            "category",
            "technician",
            "sla_target_hours",
            "met_sla",
            "is_overdue",
        ]

        tickets_table = result.tickets[display_columns].copy()

        def format_sla_hours(value):
            if pd.isna(value):
                return "Não informado"

            total_minutes = round(float(value) * 60)
            hours, minutes = divmod(total_minutes, 60)

            if minutes == 0:
                return f"{hours}h"

            return f"{hours}h {minutes}min"


        tickets_table["sla_target_hours"] = tickets_table[
            "sla_target_hours"
        ].apply(format_sla_hours)

        tickets_table["met_sla"] = (
            tickets_table["met_sla"]
            .astype("string")
            .replace(
                {
                    "True": "Sim",
                    "False": "Não",
                    "<NA>": "Não avaliado",
                }
            )
        )

        tickets_table["is_overdue"] = (
            tickets_table["is_overdue"]
            .astype("string")
            .replace(
                {
                    "True": "Sim",
                    "False": "Não",
                    "<NA>": "Não avaliado",
                }
            )
        )

        tickets_table = tickets_table.rename(
            columns={
                "ticket_id": "ID do chamado",
                "opened_at": "Data de abertura",
                "status": "Status",
                "priority": "Prioridade",
                "category": "Categoria",
                "technician": "Técnico",
                "sla_target_hours": "Meta de SLA (horas)",
                "met_sla": "Cumpriu o SLA",
                "is_overdue": "Está atrasado",
            }
        )

        st.dataframe(
            tickets_table,
            width="stretch",
            hide_index=True,
        )



st.divider()
st.caption(
    "Projeto de portfólio com dados fictícios. Desenvolvido para demonstrar "
    "Python, Pandas, análise de SLA, visualização e automação de relatórios."
)
