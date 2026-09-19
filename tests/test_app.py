from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_dashboard_starts_with_sample_data() -> None:
    app_file = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(app_file).run(timeout=20)

    assert not app.exception
    assert [tab.label for tab in app.tabs] == [
        "Visão geral",
        "SLA e atrasos",
        "Equipe",
        "Dados e qualidade",
    ]

    dashboard_markup = "\n".join(markdown.value for markdown in app.markdown)
    for indicator in [
        "Total de chamados",
        "Em aberto",
        "Resolvidos",
        "Atrasados",
        "Cumprimento geral do SLA",
        "Tempo médio de resolução",
        "Primeira resposta",
        "Satisfação média",
    ]:
        assert indicator in dashboard_markup
