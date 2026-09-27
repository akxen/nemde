"""Solver-free tests for casefile normalisation and case construction.

Runs against the two casefiles that are force-added past the data/input gitignore
(see .gitignore), so this module works in a clean checkout with no solver. Everything
here is parsing -- no LP is built.
"""

import json
from pathlib import Path
from xml.parsers.expat import ExpatError

import pytest

from nemde.casefile_io import normalize_casefile
from nemde.inputs import construct_case

REPO = Path(__file__).resolve().parent.parent

# The two committed fixtures. 2021 predates bidirectional units; 2024 has the
# modern trader mix. Between them they cover both sides of the BDU-specific code.
FIXTURES = {
    "2021": REPO / "data/input/NemSpdOutputs_20210101_loaded/NEMSPDOutputs_2021010100100.loaded",
    "2024": REPO / "data/input/NemSpdOutputs_20240701_loaded/NEMSPDOutputs_2024070100100.loaded",
}


@pytest.fixture(scope="session", params=sorted(FIXTURES), ids=sorted(FIXTURES))
def case_file(request) -> dict:
    """The normalised (xmltodict-shaped) casefile, parsed once per fixture."""
    return normalize_casefile(FIXTURES[request.param].read_text())


@pytest.fixture(scope="session")
def case(case_file) -> dict:
    """A fully-constructed case dict -- the contract between inputs.py and model.py."""
    return construct_case(data=case_file, mode="pricing")


class TestNormalizeCasefile:
    def test_str_input_is_parsed(self):
        xml = "<Root><Item><Trade a='1'/></Item></Root>"
        assert normalize_casefile(xml) == {"Root": {"Item": {"Trade": [{"@a": "1"}]}}}

    def test_bytes_input_is_parsed(self):
        assert normalize_casefile(b"<Root><A>1</A></Root>") == {"Root": {"A": "1"}}

    def test_dict_input_passes_through_unchanged(self):
        data = {"NEMSPDCaseFile": {"x": 1}}
        assert normalize_casefile(data) is data

    def test_force_list_elements_are_always_lists(self):
        # xmltodict collapses a one-element collection to a bare dict, which would
        # make every downstream `for trade in ...` iterate over attribute names.
        parsed = normalize_casefile(
            "<Root><TradeCollection><Trade a='1'/></TradeCollection></Root>"
        )
        assert parsed["Root"]["TradeCollection"]["Trade"] == [{"@a": "1"}]

    @pytest.mark.parametrize("bad", [None, 42, 3.5, ["<Root/>"], object()])
    def test_unsupported_types_raise_typeerror(self, bad):
        with pytest.raises(TypeError, match="Unsupported casefile input type"):
            normalize_casefile(bad)

    def test_malformed_xml_raises(self):
        with pytest.raises(ExpatError):
            normalize_casefile("<Root><unclosed>")


class TestConstructCase:
    def test_casefile_survives_the_json_round_trip_run_model_does(self, case_file):
        # run_model() does json.loads(json.dumps(casefile)) to get a private copy
        # before mutating it; anything not JSON-representable is lost silently there.
        # (The case dict itself is *not* JSON-serialisable -- it is keyed by tuples.)
        assert json.loads(json.dumps(case_file)) == case_file

    def test_trader_offers_and_total_offers_agree(self, case):
        # S_TRADER_TOTAL_OFFERS is S_TRADER_OFFERS with the direction dropped;
        # if the two ever disagree, a whole family of E_TRADER_TARGET lookups is wrong.
        assert {(i, j) for i, j, _ in case["S_TRADER_OFFERS"]} == set(case["S_TRADER_TOTAL_OFFERS"])

    def test_energy_offers_are_a_subset_of_all_offers(self, case):
        assert set(case["S_TRADER_ENERGY_OFFERS"]) <= set(case["S_TRADER_OFFERS"])

    def test_fcas_offers_are_a_subset_of_all_offers(self, case):
        assert set(case["S_TRADER_FCAS_OFFERS"]) <= set(case["S_TRADER_OFFERS"])

    def test_energy_and_fcas_offers_partition_all_offers(self, case):
        energy, fcas = set(case["S_TRADER_ENERGY_OFFERS"]), set(case["S_TRADER_FCAS_OFFERS"])
        assert not energy & fcas
        assert energy | fcas == set(case["S_TRADER_OFFERS"])


class TestAuditParserAgreesWithInputs:
    """audit_objective.py parses casefiles independently of inputs.py.

    That duplication is deliberate: the audit tool adjudicates the objective gap,
    so if it shared a parser with the model it is checking, a parsing bug would be
    invisible to it. But an *unnoticed* divergence between the two is a wrong answer
    in the investigation, which is what these tests rule out -- they pin the two
    implementations together without collapsing them into one.
    """

    @staticmethod
    def _flatten(nested: dict) -> dict:
        # audit keys by (trader, trade_type, direction) -> {band: value};
        # inputs keys by (trader, trade_type, direction, band) -> value.
        return {(*key, band): v for key, bands in nested.items() for band, v in bands.items()}

    @pytest.mark.parametrize("name", sorted(FIXTURES))
    def test_price_bands_match(self, name):
        audit = pytest.importorskip("internal.audit_objective")
        from nemde.inputs import get_trader_price_bands

        raw = audit.load_casefile(FIXTURES[name])
        normalised = normalize_casefile(FIXTURES[name].read_text())
        assert self._flatten(audit.get_trader_price_bands(raw)) == get_trader_price_bands(
            normalised
        )

    @pytest.mark.parametrize("name", sorted(FIXTURES))
    def test_quantity_bands_match(self, name):
        audit = pytest.importorskip("internal.audit_objective")
        from nemde.inputs import get_trader_quantity_bands

        raw = audit.load_casefile(FIXTURES[name])
        normalised = normalize_casefile(FIXTURES[name].read_text())
        assert self._flatten(audit.get_trader_quantity_bands(raw)) == get_trader_quantity_bands(
            normalised
        )
