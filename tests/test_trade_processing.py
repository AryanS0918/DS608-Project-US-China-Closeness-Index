"""Unit tests for total merchandise-trade processing."""

import pandas as pd
import pytest

from src.data.collect_trade import (
    apply_mirror_values,
    calculate_trade_measures,
)


def make_trade_row(
    reporter_iso="TST",
    imports_from_china=60.0,
    exports_to_china=40.0,
    imports_from_us=30.0,
    exports_to_us=50.0,
):
    """Create one synthetic country-year trade observation."""

    return pd.DataFrame(
        {
            "year": [2023],
            "reporter_code": [999],
            "reporter_iso": [reporter_iso],
            "reporter_name": ["Test economy"],
            "imports_from_china": [
                imports_from_china
            ],
            "exports_to_china": [
                exports_to_china
            ],
            "imports_from_us": [
                imports_from_us
            ],
            "exports_to_us": [
                exports_to_us
            ],
        }
    )


def test_trade_orientation_score():
    """The score should equal the US-China balance ratio."""

    dataframe = make_trade_row()

    result = calculate_trade_measures(dataframe)

    china_total = 60.0 + 40.0
    us_total = 30.0 + 50.0

    expected_score = (
        us_total - china_total
    ) / (
        us_total + china_total
    )

    assert result.loc[
        0,
        "china_total_trade_usd",
    ] == pytest.approx(china_total)

    assert result.loc[
        0,
        "us_total_trade_usd",
    ] == pytest.approx(us_total)

    assert result.loc[
        0,
        "trade_orientation_score",
    ] == pytest.approx(expected_score)


def test_trade_score_is_bounded():
    """A valid directional score must lie within -1 and 1."""

    dataframe = make_trade_row(
        imports_from_china=1.0,
        exports_to_china=0.0,
        imports_from_us=100.0,
        exports_to_us=0.0,
    )

    result = calculate_trade_measures(dataframe)

    score = result.loc[
        0,
        "trade_orientation_score",
    ]

    assert -1 <= score <= 1


def test_incomplete_record_has_no_score():
    """A missing required flow must prevent score calculation."""

    dataframe = make_trade_row(
        exports_to_china=pd.NA,
    )

    result = calculate_trade_measures(dataframe)

    assert result.loc[
        0,
        "available_flow_count",
    ] == 3

    assert not result.loc[
        0,
        "complete_four_flow_record",
    ]

    assert pd.isna(
        result.loc[
            0,
            "trade_orientation_score",
        ]
    )


def test_zero_denominator_has_no_score():
    """No bilateral activity with either anchor must not yield 0/0."""

    dataframe = make_trade_row(
        imports_from_china=0.0,
        exports_to_china=0.0,
        imports_from_us=0.0,
        exports_to_us=0.0,
    )

    result = calculate_trade_measures(dataframe)

    assert pd.isna(
        result.loc[
            0,
            "trade_orientation_score",
        ]
    )


def test_mirror_value_fills_missing_export():
    """A mirror observation should fill the correct missing flow."""

    wide_dataframe = make_trade_row(
        reporter_iso="ABW",
        exports_to_china=pd.NA,
    )

    wide_dataframe.loc[
        0,
        "reporter_code",
    ] = 533

    mirror_dataframe = pd.DataFrame(
        {
            "year": [2023],
            "reporter_code": [533],
            "missing_relationship": [
                "exports_to_china"
            ],
            "mirror_value_usd": [10.0],
        }
    )

    result = apply_mirror_values(
        wide_dataframe=wide_dataframe,
        mirror_dataframe=mirror_dataframe,
    )

    assert result.loc[
        0,
        "exports_to_china",
    ] == pytest.approx(10.0)

    assert result.loc[
        0,
        "exports_to_china_source",
    ] == "mirror"

    assert result.loc[
        0,
        "imports_from_china_source",
    ] == "reporter"


def test_missing_mirror_remains_missing():
    """A missing mirror must not be converted silently to zero."""

    wide_dataframe = make_trade_row(
        exports_to_china=pd.NA,
    )

    mirror_dataframe = pd.DataFrame(
        {
            "year": [2023],
            "reporter_code": [999],
            "missing_relationship": [
                "exports_to_china"
            ],
            "mirror_value_usd": [pd.NA],
        }
    )

    result = apply_mirror_values(
        wide_dataframe=wide_dataframe,
        mirror_dataframe=mirror_dataframe,
    )

    assert pd.isna(
        result.loc[
            0,
            "exports_to_china",
        ]
    )

    assert result.loc[
        0,
        "exports_to_china_source",
    ] == "missing"


@pytest.mark.parametrize(
    "anchor_iso",
    [
        "USA",
        "CHN",
    ],
)
def test_anchor_countries_have_no_score(anchor_iso):
    """The two anchor countries must not receive index scores."""

    dataframe = make_trade_row(
        reporter_iso=anchor_iso,
    )

    result = calculate_trade_measures(dataframe)

    assert result.loc[
        0,
        "is_anchor_country",
    ]

    assert pd.isna(
        result.loc[
            0,
            "trade_orientation_score",
        ]
    )

    assert pd.isna(
        result.loc[
            0,
            "complete_four_flow_record",
        ]
    )