"""
Test casefile conversion
"""

import pytest

import context
from nemde.core.casefile import lookup
from nemde.io.casefile import load_base_case
from nemde.config.setup_variables import setup_environment_variables

setup_environment_variables(online=False)


@pytest.fixture(scope='module')
def casefile():
    return load_base_case('20201101001')


def test_get_case_attribute(casefile):
    assert (lookup.get_case_attribute(
        data=casefile, attribute='@EnergySurplusPrice', func=str) == "2250000")


def test_get_region_collection_attribute(casefile):
    assert (lookup.get_region_collection_attribute(
        data=casefile, region_id='SA1', attribute='@RegionID',
        func=str) == 'SA1')


def test_get_region_collection_initial_condition_attribute(casefile):
    assert (lookup.get_region_collection_initial_condition_attribute(
        data=casefile, region_id="SA1", attribute="ADE", func=str) == "0")


def test_get_region_period_collection_attribute(casefile):
    assert (lookup.get_region_period_collection_attribute(
        data=casefile, region_id="NSW1", attribute="@RegionID",
        func=str) == 'NSW1')


def test_get_region_solution_attribute(casefile):
    assert (lookup.get_region_solution_attribute(
        data=casefile, region_id="NSW1", attribute="@RegionID",
        intervention="0", func=str) == 'NSW1')


def test_get_trader_collection_attribute(casefile):
    assert (lookup.get_trader_collection_attribute(
        data=casefile, trader_id='AGLHAL', attribute='@TraderID',
        func=str) == 'AGLHAL')


def test_get_trader_collection_initial_condition_attribute(casefile):
    assert (lookup.get_trader_collection_initial_condition_attribute(
        data=casefile, trader_id='AGLHAL', attribute='AGCStatus',
        func=str) == "0")


def test_get_trader_period_collection_attribute(casefile):
    assert (lookup.get_trader_period_collection_attribute(
        data=casefile, trader_id='AGLHAL', attribute='@RegionID',
        func=str) == "SA1")


def test_get_trader_quantity_band_attribute(casefile):
    assert (lookup.get_trader_quantity_band_attribute(
        data=casefile, trader_id='AGLHAL', trade_type='ENOF',
        attribute='@BandAvail1', func=str) == "0")


def test_get_trader_price_band_attribute(casefile):
    assert (lookup.get_trader_price_band_attribute(
        data=casefile, trader_id='AGLHAL', trade_type='ENOF',
        attribute="@TradeType", func=str) == 'ENOF')


def test_get_trader_solution_attribute(casefile):
    assert (lookup.get_trader_solution_attribute(
        data=casefile, trader_id='AGLHAL', attribute='@TraderID', func=str,
        intervention='0') == 'AGLHAL')


def test_get_interconnector_collection_attribute(casefile):
    assert (lookup.get_interconnector_collection_attribute(
        data=casefile, interconnector_id='N-Q-MNSP1',
        attribute='@InterconnectorID', func=str) == 'N-Q-MNSP1')


def test_get_interconnector_collection_initial_condition_attribute(casefile):
    assert (lookup.get_interconnector_collection_initial_condition_attribute(
        data=casefile, interconnector_id='N-Q-MNSP1', attribute='InitialMW',
        func=str) == "-32.7999992370605")


def test_get_interconnector_period_collection_attribute(casefile):
    assert (lookup.get_interconnector_period_collection_attribute(
        data=casefile, interconnector_id='N-Q-MNSP1',
        attribute='@InterconnectorID', func=str) == 'N-Q-MNSP1')


def test_get_interconnector_loss_model_segments(casefile):
    segments = lookup.get_interconnector_loss_model_segments(
        data=casefile, interconnector_id='V-SA')
    
    assert isinstance(segments, list)
    assert len(segments) > 0


def test_get_interconnector_loss_model_attribute(casefile):
    assert (lookup.get_interconnector_loss_model_attribute(
        data=casefile, interconnector_id='N-Q-MNSP1', attribute='@NPLRange',
        func=str) == '10000')


def test_get_interconnector_solution_attribute(casefile):
    assert (lookup.get_interconnector_solution_attribute(
        data=casefile, interconnector_id='N-Q-MNSP1',
        attribute='@InterconnectorID', func=str,
        intervention='0') == 'N-Q-MNSP1')


def test_get_generic_constraint_solution_attribute(casefile):
    assert (lookup.get_generic_constraint_solution_attribute(
        data=casefile, constraint_id='#BBTHREE3_E', attribute='@ConstraintID',
        func=str, intervention='0') == '#BBTHREE3_E')


def test_get_period_solution_attribute(casefile):
    assert (lookup.get_period_solution_attribute(
        data=casefile, attribute='@SolverStatus', func=str,
        intervention='0') == '0')


def test_get_trader_index(casefile):
    traders = lookup.get_trader_index(casefile)
    assert isinstance(traders, list)
    assert len(traders) > 0
    assert len(traders) == len(set(traders))


def test_get_interconnector_index(casefile):
    interconnectors = lookup.get_interconnector_index(casefile)
    assert isinstance(interconnectors, list)
    assert len(interconnectors) > 0
    assert len(interconnectors) == len(set(interconnectors))


def test_get_mnsp_index(casefile):
    mnsps = lookup.get_mnsp_index(casefile)
    assert isinstance(mnsps, list)
    assert len(mnsps) > 0
    assert len(mnsps) == len(set(mnsps))


def test_get_region_index(casefile):
    regions = lookup.get_region_index(casefile)
    assert isinstance(regions, list)
    assert len(regions) > 0
    assert len(regions) == len(set(regions))


def test_get_intervention_status(casefile):
    assert lookup.get_intervention_status(data=casefile, mode='physical') == '0'
