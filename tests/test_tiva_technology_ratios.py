import pandas as pd
import pytest
from src.data.collect_tiva_technology_ratios import build_ratios

def test_build_ratios_and_carry_forward():
    raw=pd.DataFrame({"REF_AREA":["CHN","CHN","USA","USA"],"ACTIVITY":["C26"]*4,"MEASURE":["EXGR","EXGR_DVA"]*2,"TIME_PERIOD":[2022]*4,"OBS_VALUE":[100,70,200,180]})
    out=build_ratios(raw,2024)
    observed=out[(out.year==2022)&(out.tiva_activity_code=="C26")].set_index("anchor_iso3")
    assert observed.loc["CHN","dva_ratio"]==pytest.approx(.7)
    assert observed.loc["USA","dva_ratio"]==pytest.approx(.9)
    carried=out[(out.year==2024)&(out.tiva_activity_code=="C26")]
    assert set(carried.ratio_source_status)=={"carried_forward"}
    assert set(carried.ratio_source_year)=={2022}

def test_out_of_bounds_ratio_is_flagged():
    raw=pd.DataFrame({"REF_AREA":["CHN","CHN"],"ACTIVITY":["C26"]*2,"MEASURE":["EXGR","EXGR_DVA"],"TIME_PERIOD":[2022]*2,"OBS_VALUE":[100,110]})
    assert build_ratios(raw,2022).iloc[0].validation_status=="ratio_out_of_bounds"
