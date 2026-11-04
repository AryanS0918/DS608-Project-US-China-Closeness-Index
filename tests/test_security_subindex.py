import importlib.util
from pathlib import Path
import pandas as pd
import pytest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("builder", ROOT/"src/data/build_security_subindex.py")
b=importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
@pytest.fixture(scope="module")
def inputs():
    return (pd.read_csv(ROOT/"data/processed/security_institutional_ties_country_anchor_year.csv"), pd.read_csv(ROOT/"data/processed/sipri_arms_country_year.csv"))
@pytest.fixture(scope="module")
def out(inputs): return b.build_security_subindex(*inputs)
def test_expected_shape(out): assert out.shape == (4205, 8)
def test_expected_universe(out): assert out.iso3.nunique()==192 and out.year.min()==2004 and out.year.max()==2025
def test_unique_keys(out): assert not out.duplicated(["iso3","year"]).any()
def test_complete_bounded_scores(out): assert out.security_score.notna().all() and out.security_score.between(-1,1).all()
def test_status_counts(out): assert out.arms_observation_status.value_counts().to_dict()=={"available":2329,"no_observed_arms_imports":943,"no_observed_anchor_transfers":933}
def test_missing_arms_renormalises(out):
    x=out[out.arms_observation_status.eq("no_observed_arms_imports")]
    assert x.arms_transfer_score.isna().all() and (x.security_score==x.institutional_signed_score).all()
def test_observed_zero_retains_half_weight(out):
    x=out[out.arms_observation_status.eq("no_observed_anchor_transfers")]
    assert x.arms_transfer_score.eq(0).all() and (x.security_score==0.5*x.institutional_signed_score).all()
def test_observed_components_equal_weighted(out):
    x=out[out.arms_observation_status.eq("available")]
    expected=0.5*x.institutional_signed_score+0.5*x.arms_transfer_score
    assert (x.security_score-expected).abs().max()<1e-12
def test_name_mismatch_rejected(inputs):
    i,a=inputs; bad=a.copy(); bad.loc[0,"preferred_country_name"]="Mismatch"
    with pytest.raises(ValueError, match="names disagree"): b.build_security_subindex(i,bad)
def test_duplicate_arms_key_rejected(inputs):
    i,a=inputs; bad=pd.concat([a,a.iloc[[0]]],ignore_index=True)
    with pytest.raises(ValueError, match="Duplicate arms"): b.build_security_subindex(i,bad)
