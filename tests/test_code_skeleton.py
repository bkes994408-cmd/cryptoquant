from pathlib import Path


def test_multi_strategy_engine_contains_required_types() -> None:
    file_path = Path(
        "CryptoQuant_ALL_Documents_v1.0/"
        "CryptoQuant_All_Next_Step_Package/code_skeleton/"
        "multi_strategy_engine/MultiStrategyEngine.cs"
    )
    content = file_path.read_text(encoding="utf-8")

    assert "class MultiStrategyEngine" in content
    assert "OnMainBar" in content


def test_portfolio_risk_controller_contains_guard_method() -> None:
    file_path = Path(
        "CryptoQuant_ALL_Documents_v1.0/"
        "CryptoQuant_All_Next_Step_Package/code_skeleton/"
        "portfolio_risk/PortfolioRiskController.cs"
    )
    content = file_path.read_text(encoding="utf-8")

    assert "class PortfolioRiskController" in content
    assert "RiskMultiplier" in content
