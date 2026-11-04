import pandas as pd
import pytest
from src.data.build_technology_trade import expected_counts, orientation


def test_orientation_direction_and_bounds():
    score=orientation(pd.Series([75.0]),pd.Series([25.0])).iloc[0]
    assert score==pytest.approx(.5)
    assert -1<=score<=1


def test_orientation_missing_and_zero_denominator():
    out=orientation(pd.Series([None,0.0,1.0]),pd.Series([1.0,0.0,None]))
    assert out.isna().all()


def test_orientation_endpoints():
    out=orientation(pd.Series([1.0,0.0]),pd.Series([0.0,1.0]))
    assert out.tolist()==pytest.approx([1.0,-1.0])


def test_expected_counts_come_from_reference_not_observed_rows():
    reference=pd.DataFrame({"hs_revision":["HS2022"]*3,"hs6_code":["111111","222222","333333"],"ict_category_code":["ICT01","ICT01","ICT02"],"include_baseline":[True,True,True]})
    out=expected_counts(reference,"include_baseline").iloc[0]
    assert out.expected_hs6==3
    assert out.expected_categories==2
