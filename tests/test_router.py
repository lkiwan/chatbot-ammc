"""
Unit tests for retrieval.router — query type classification.
"""
import pytest
from retrieval.router import QueryType, classify_query


class TestSQLRouting:
    def test_metric_with_company_and_year(self):
        result = classify_query("Quel est le résultat net de Attijariwafa en 2022 ?")
        assert result.query_type == QueryType.SQL

    def test_ebitda_question(self):
        result = classify_query("Quel est l'EBITDA de OCP en 2021 ?")
        assert result.query_type == QueryType.SQL

    def test_comparison_request(self):
        result = classify_query("Compare le chiffre d'affaires de 2020 à 2023")
        assert result.query_type in (QueryType.SQL, QueryType.HYBRID)

    def test_evolution(self):
        result = classify_query("Quelle est l'évolution du résultat net entre 2018 et 2022 ?")
        assert result.query_type in (QueryType.SQL, QueryType.HYBRID)

    def test_shareholders(self):
        result = classify_query("Quels sont les actionnaires principaux ?")
        assert result.query_type == QueryType.SQL


class TestVectorRouting:
    def test_strategy_question(self):
        result = classify_query("Quelle est la stratégie de développement de l'entreprise ?")
        assert result.query_type == QueryType.VECTOR

    def test_risk_question(self):
        result = classify_query("Quels sont les risques opérationnels mentionnés ?")
        assert result.query_type == QueryType.VECTOR

    def test_governance(self):
        result = classify_query("Comment fonctionne la gouvernance de l'entreprise ?")
        assert result.query_type == QueryType.VECTOR

    def test_esg(self):
        result = classify_query("Quels engagements RSE l'entreprise a-t-elle pris ?")
        assert result.query_type == QueryType.VECTOR


class TestHybridRouting:
    def test_why_increase(self):
        result = classify_query("Pourquoi le résultat net a-t-il augmenté en 2022 ?")
        assert result.query_type == QueryType.HYBRID

    def test_impact(self):
        result = classify_query("Quel est l'impact de la crise sur le chiffre d'affaires ?")
        assert result.query_type == QueryType.HYBRID

    def test_factor(self):
        result = classify_query("Quels facteurs expliquent la hausse du chiffre d'affaires ?")
        assert result.query_type == QueryType.HYBRID


class TestHints:
    def test_year_extraction(self):
        result = classify_query("Résultat net en 2021")
        assert result.sql_hints["year"] == 2021

    def test_metric_extraction_net_income(self):
        result = classify_query("Quel est le résultat net ?")
        assert result.sql_hints["metric"] == "net_income"

    def test_metric_extraction_revenue(self):
        result = classify_query("Chiffre d'affaires de l'entreprise")
        assert result.sql_hints["metric"] == "revenue"

    def test_metric_extraction_ebitda(self):
        result = classify_query("Valeur de l'EBITDA")
        assert result.sql_hints["metric"] == "ebitda"

    def test_no_year(self):
        result = classify_query("Quels sont les actionnaires ?")
        assert result.sql_hints["year"] is None


class TestConfidence:
    def test_high_confidence_sql(self):
        result = classify_query(
            "Quel est le montant exact du résultat net en 2022 ?"
        )
        assert result.confidence >= 0.6

    def test_default_vector_low_confidence(self):
        result = classify_query("Bonjour")
        assert result.query_type == QueryType.VECTOR
        assert result.confidence <= 0.5
