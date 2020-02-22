import numpy as np
import pytest

import pandas.util._test_decorators as td

import pandas as pd
from pandas import Index, MultiIndex, Series, date_range, isna
import pandas._testing as tm


@pytest.fixture(
    params=[
        "linear",
        "index",
        "values",
        "nearest",
        "slinear",
        "zero",
        "quadratic",
        "cubic",
        "barycentric",
        "krogh",
        "polynomial",
        "spline",
        "piecewise_polynomial",
        "from_derivatives",
        "pchip",
        "akima",
    ]
)
def nontemporal_method(request):
    """ Fixture that returns an (method name, required kwargs) pair.

    This fixture does not include method 'time' as a parameterization; that
    method requires a Series with a DatetimeIndex, and is generally tested
    separately from these non-temporal methods.
    """
    method = request.param
    kwargs = dict(order=1) if method in ("spline", "polynomial") else dict()
    return method, kwargs


@pytest.fixture(
    params=[
        "linear",
        "slinear",
        "zero",
        "quadratic",
        "cubic",
        "barycentric",
        "krogh",
        "polynomial",
        "spline",
        "piecewise_polynomial",
        "from_derivatives",
        "pchip",
        "akima",
    ]
)
def interp_methods_ind(request):
    """ Fixture that returns a (method name, required kwargs) pair to
    be tested for various Index types.

    This fixture does not include methods - 'time', 'index', 'nearest',
    'values' as a parameterization
    """
    method = request.param
    kwargs = dict(order=1) if method in ("spline", "polynomial") else dict()
    return method, kwargs


class TestSeriesInterpolateData:
    def test_interpolate(self, datetime_series, string_series):
        ts = Series(np.arange(len(datetime_series), dtype=float), datetime_series.index)

        ts_copy = ts.copy()
        ts_copy[5:10] = np.NaN

        linear_interp = ts_copy.interpolate(method="linear")
        tm.assert_series_equal(linear_interp, ts)

        ord_ts = Series(
            [d.toordinal() for d in datetime_series.index], index=datetime_series.index
        ).astype(float)

        ord_ts_copy = ord_ts.copy()
        ord_ts_copy[5:10] = np.NaN

        time_interp = ord_ts_copy.interpolate(method="time")
        tm.assert_series_equal(time_interp, ord_ts)

    def test_interpolate_time_raises_for_non_timeseries(self):
        # When method='time' is used on a non-TimeSeries that contains a null
        # value, a ValueError should be raised.
        non_ts = Series([0, 1, 2, np.NaN])
        msg = "time-weighted interpolation only works on Series.* with a DatetimeIndex"
        with pytest.raises(ValueError, match=msg):
            non_ts.interpolate(method="time")

    @td.skip_if_no_scipy
    def test_interpolate_pchip(self):

        ser = Series(np.sort(np.random.uniform(size=100)))

        # interpolate at new_index
        new_index = ser.index.union(
            Index([49.25, 49.5, 49.75, 50.25, 50.5, 50.75])
        ).astype(float)
        interp_s = ser.reindex(new_index).interpolate(method="pchip")
        # does not blow up, GH5977
        interp_s[49:51]

    @td.skip_if_no_scipy
    def test_interpolate_akima(self):

        ser = Series([10, 11, 12, 13])

        expected = Series(
            [11.00, 11.25, 11.50, 11.75, 12.00, 12.25, 12.50, 12.75, 13.00],
            index=Index([1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0]),
        )
        # interpolate at new_index
        new_index = ser.index.union(Index([1.25, 1.5, 1.75, 2.25, 2.5, 2.75])).astype(
            float
        )
        interp_s = ser.reindex(new_index).interpolate(method="akima")
        tm.assert_series_equal(interp_s[1:3], expected)

    @td.skip_if_no_scipy
    def test_interpolate_piecewise_polynomial(self):
        ser = Series([10, 11, 12, 13])

        expected = Series(
            [11.00, 11.25, 11.50, 11.75, 12.00, 12.25, 12.50, 12.75, 13.00],
            index=Index([1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0]),
        )
        # interpolate at new_index
        new_index = ser.index.union(Index([1.25, 1.5, 1.75, 2.25, 2.5, 2.75])).astype(
            float
        )
        interp_s = ser.reindex(new_index).interpolate(method="piecewise_polynomial")
        tm.assert_series_equal(interp_s[1:3], expected)

    @td.skip_if_no_scipy
    def test_interpolate_from_derivatives(self):
        ser = Series([10, 11, 12, 13])

        expected = Series(
            [11.00, 11.25, 11.50, 11.75, 12.00, 12.25, 12.50, 12.75, 13.00],
            index=Index([1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0]),
        )
        # interpolate at new_index
        new_index = ser.index.union(Index([1.25, 1.5, 1.75, 2.25, 2.5, 2.75])).astype(
            float
        )
        interp_s = ser.reindex(new_index).interpolate(method="from_derivatives")
        tm.assert_series_equal(interp_s[1:3], expected)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {},
            pytest.param(
                {"method": "polynomial", "order": 1}, marks=td.skip_if_no_scipy
            ),
        ],
    )
    def test_interpolate_corners(self, kwargs):
        s = Series([np.nan, np.nan])
        tm.assert_series_equal(s.interpolate(**kwargs), s)

        s = Series([], dtype=object).interpolate()
        tm.assert_series_equal(s.interpolate(**kwargs), s)

    def test_interpolate_index_values(self):
        s = Series(np.nan, index=np.sort(np.random.rand(30)))
        s[::3] = np.random.randn(10)

        vals = s.index.values.astype(float)

        result = s.interpolate(method="index")

        expected = s.copy()
        bad = isna(expected.values)
        good = ~bad
        expected = Series(
            np.interp(vals[bad], vals[good], s.values[good]), index=s.index[bad]
        )

        tm.assert_series_equal(result[bad], expected)

        # 'values' is synonymous with 'index' for the method kwarg
        other_result = s.interpolate(method="values")

        tm.assert_series_equal(other_result, result)
        tm.assert_series_equal(other_result[bad], expected)

    def test_interpolate_non_ts(self):
        s = Series([1, 3, np.nan, np.nan, np.nan, 11])
        msg = (
            "time-weighted interpolation only works on Series or DataFrames "
            "with a DatetimeIndex"
        )
        with pytest.raises(ValueError, match=msg):
            s.interpolate(method="time")

    @pytest.mark.parametrize(
        "kwargs",
        [
            {},
            pytest.param(
                {"method": "polynomial", "order": 1}, marks=td.skip_if_no_scipy
            ),
        ],
    )
    def test_nan_interpolate(self, kwargs):
        s = Series([0, 1, np.nan, 3])
        result = s.interpolate(**kwargs)
        expected = Series([0.0, 1.0, 2.0, 3.0])
        tm.assert_series_equal(result, expected)

    def test_nan_irregular_index(self):
        s = Series([1, 2, np.nan, 4], index=[1, 3, 5, 9])
        result = s.interpolate()
        expected = Series([1.0, 2.0, 3.0, 4.0], index=[1, 3, 5, 9])
        tm.assert_series_equal(result, expected)

    def test_nan_str_index(self):
        s = Series([0, 1, 2, np.nan], index=list("abcd"))
        result = s.interpolate()
        expected = Series([0.0, 1.0, 2.0, 2.0], index=list("abcd"))
        tm.assert_series_equal(result, expected)

    @td.skip_if_no_scipy
    def test_interp_quad(self):
        sq = Series([1, 4, np.nan, 16], index=[1, 2, 3, 4])
        result = sq.interpolate(method="quadratic")
        expected = Series([1.0, 4.0, 9.0, 16.0], index=[1, 2, 3, 4])
        tm.assert_series_equal(result, expected)

    @td.skip_if_no_scipy
    def test_interp_scipy_basic(self):
        s = Series([1, 3, np.nan, 12, np.nan, 25])
        # slinear
        expected = Series([1.0, 3.0, 7.5, 12.0, 18.5, 25.0])
        result = s.interpolate(method="slinear")
        tm.assert_series_equal(result, expected)

        result = s.interpolate(method="slinear", downcast="infer")
        tm.assert_series_equal(result, expected)
        # nearest
        expected = Series([1, 3, 3, 12, 12, 25])
        result = s.interpolate(method="nearest")
        tm.assert_series_equal(result, expected.astype("float"))

        result = s.interpolate(method="nearest", downcast="infer")
        tm.assert_series_equal(result, expected)
        # zero
        expected = Series([1, 3, 3, 12, 12, 25])
        result = s.interpolate(method="zero")
        tm.assert_series_equal(result, expected.astype("float"))

        result = s.interpolate(method="zero", downcast="infer")
        tm.assert_series_equal(result, expected)
        # quadratic
        # GH #15662.
        expected = Series([1, 3.0, 6.823529, 12.0, 18.058824, 25.0])
        result = s.interpolate(method="quadratic")
        tm.assert_series_equal(result, expected)

        result = s.interpolate(method="quadratic", downcast="infer")
        tm.assert_series_equal(result, expected)
        # cubic
        expected = Series([1.0, 3.0, 6.8, 12.0, 18.2, 25.0])
        result = s.interpolate(method="cubic")
        tm.assert_series_equal(result, expected)

    def test_interp_limit(self):
        s = Series([1, 3, np.nan, np.nan, np.nan, 11])

        expected = Series([1.0, 3.0, 5.0, 7.0, np.nan, 11.0])
        result = s.interpolate(method="linear", limit=2)
        tm.assert_series_equal(result, expected)

    @pytest.mark.parametrize("limit", [-1, 0])
    def test_interpolate_invalid_nonpositive_limit(self, nontemporal_method, limit):
        # GH 9217: make sure limit is greater than zero.
        s = pd.Series([1, 2, np.nan, 4])
        method, kwargs = nontemporal_method
        with pytest.raises(ValueError, match="Limit must be greater than 0"):
            s.interpolate(limit=limit, method=method, **kwargs)

    def test_interpolate_invalid_float_limit(self, nontemporal_method):
        # GH 9217: make sure limit is an integer.
        s = pd.Series([1, 2, np.nan, 4])
        method, kwargs = nontemporal_method
        limit = 2.0
        with pytest.raises(ValueError, match="Limit must be an integer"):
            s.interpolate(limit=limit, method=method, **kwargs)

    @pytest.mark.parametrize("invalid_method", [None, "nonexistent_method"])
    def test_interp_invalid_method(self, invalid_method):
        s = Series([1, 3, np.nan, 12, np.nan, 25])

        msg = f"method must be one of.* Got '{invalid_method}' instead"
        with pytest.raises(ValueError, match=msg):
            s.interpolate(method=invalid_method)

        # When an invalid method and invalid limit (such as -1) are
        # provided, the error message reflects the invalid method.
        with pytest.raises(ValueError, match=msg):
            s.interpolate(method=invalid_method, limit=-1)

    def test_interp_limit_forward(self):
        s = Series([1, 3, np.nan, np.nan, np.nan, 11])

        # Provide 'forward' (the default) explicitly here.
        expected = Series([1.0, 3.0, 5.0, 7.0, np.nan, 11.0])

        result = s.interpolate(method="linear", limit=2, limit_direction="forward")
        tm.assert_series_equal(result, expected)

        result = s.interpolate(method="linear", limit=2, limit_direction="FORWARD")
        tm.assert_series_equal(result, expected)

    def test_interp_unlimited(self):
        # these test are for issue #16282 default Limit=None is unlimited
        s = Series([np.nan, 1.0, 3.0, np.nan, np.nan, np.nan, 11.0, np.nan])
        expected = Series([1.0, 1.0, 3.0, 5.0, 7.0, 9.0, 11.0, 11.0])
        result = s.interpolate(method="linear", limit_direction="both")
        tm.assert_series_equal(result, expected)

        expected = Series([np.nan, 1.0, 3.0, 5.0, 7.0, 9.0, 11.0, 11.0])
        result = s.interpolate(method="linear", limit_direction="forward")
        tm.assert_series_equal(result, expected)

        expected = Series([1.0, 1.0, 3.0, 5.0, 7.0, 9.0, 11.0, np.nan])
        result = s.interpolate(method="linear", limit_direction="backward")
        tm.assert_series_equal(result, expected)

    def test_interp_limit_bad_direction(self):
        s = Series([1, 3, np.nan, np.nan, np.nan, 11])

        msg = (
            r"Invalid limit_direction: expecting one of \['forward', "
            r"'backward', 'both'\], got 'abc'"
        )
        with pytest.raises(ValueError, match=msg):
            s.interpolate(method="linear", limit=2, limit_direction="abc")

        # raises an error even if no limit is specified.
        with pytest.raises(ValueError, match=msg):
            s.interpolate(method="linear", limit_direction="abc")

    # limit_area introduced GH #16284
    def test_interp_limit_area(self):
        # These tests are for issue #9218 -- fill NaNs in both directions.
        s = Series([np.nan, np.nan, 3, np.nan, np.nan, np.nan, 7, np.nan, np.nan])

        expected = Series([np.nan, np.nan, 3.0, 4.0, 5.0, 6.0, 7.0, np.nan, np.nan])
        result = s.interpolate(method="linear", limit_area="inside")
        tm.assert_series_equal(result, expected)

        expected = Series(
            [np.nan, np.nan, 3.0, 4.0, np.nan, np.nan, 7.0, np.nan, np.nan]
        )
        result = s.interpolate(method="linear", limit_area="inside", limit=1)
        tm.assert_series_equal(result, expected)

        expected = Series([np.nan, np.nan, 3.0, 4.0, np.nan, 6.0, 7.0, np.nan, np.nan])
        result = s.interpolate(
            method="linear", limit_area="inside", limit_direction="both", limit=1
        )
        tm.assert_series_equal(result, expected)

        expected = Series([np.nan, np.nan, 3.0, np.nan, np.nan, np.nan, 7.0, 7.0, 7.0])
        result = s.interpolate(method="linear", limit_area="outside")
        tm.assert_series_equal(result, expected)

        expected = Series(
            [np.nan, np.nan, 3.0, np.nan, np.nan, np.nan, 7.0, 7.0, np.nan]
        )
        result = s.interpolate(method="linear", limit_area="outside", limit=1)
        tm.assert_series_equal(result, expected)

        expected = Series([np.nan, 3.0, 3.0, np.nan, np.nan, np.nan, 7.0, 7.0, np.nan])
        result = s.interpolate(
            method="linear", limit_area="outside", limit_direction="both", limit=1
        )
        tm.assert_series_equal(result, expected)

        expected = Series([3.0, 3.0, 3.0, np.nan, np.nan, np.nan, 7.0, np.nan, np.nan])
        result = s.interpolate(
            method="linear", limit_area="outside", limit_direction="backward"
        )
        tm.assert_series_equal(result, expected)

        # raises an error even if limit type is wrong.
        msg = r"Invalid limit_area: expecting one of \['inside', 'outside'\], got abc"
        with pytest.raises(ValueError, match=msg):
            s.interpolate(method="linear", limit_area="abc")

    def test_interp_limit_direction(self):
        # These tests are for issue #9218 -- fill NaNs in both directions.
        s = Series([1, 3, np.nan, np.nan, np.nan, 11])

        expected = Series([1.0, 3.0, np.nan, 7.0, 9.0, 11.0])
        result = s.interpolate(method="linear", limit=2, limit_direction="backward")
        tm.assert_series_equal(result, expected)

        expected = Series([1.0, 3.0, 5.0, np.nan, 9.0, 11.0])
        result = s.interpolate(method="linear", limit=1, limit_direction="both")
        tm.assert_series_equal(result, expected)

        # Check that this works on a longer series of nans.
        s = Series([1, 3, np.nan, np.nan, np.nan, 7, 9, np.nan, np.nan, 12, np.nan])

        expected = Series([1.0, 3.0, 4.0, 5.0, 6.0, 7.0, 9.0, 10.0, 11.0, 12.0, 12.0])
        result = s.interpolate(method="linear", limit=2, limit_direction="both")
        tm.assert_series_equal(result, expected)

        expected = Series(
            [1.0, 3.0, 4.0, np.nan, 6.0, 7.0, 9.0, 10.0, 11.0, 12.0, 12.0]
        )
        result = s.interpolate(method="linear", limit=1, limit_direction="both")
        tm.assert_series_equal(result, expected)

    def test_interp_limit_to_ends(self):
        # These test are for issue #10420 -- flow back to beginning.
        s = Series([np.nan, np.nan, 5, 7, 9, np.nan])

        expected = Series([5.0, 5.0, 5.0, 7.0, 9.0, np.nan])
        result = s.interpolate(method="linear", limit=2, limit_direction="backward")
        tm.assert_series_equal(result, expected)

        expected = Series([5.0, 5.0, 5.0, 7.0, 9.0, 9.0])
        result = s.interpolate(method="linear", limit=2, limit_direction="both")
        tm.assert_series_equal(result, expected)

    def test_interp_limit_before_ends(self):
        # These test are for issue #11115 -- limit ends properly.
        s = Series([np.nan, np.nan, 5, 7, np.nan, np.nan])

        expected = Series([np.nan, np.nan, 5.0, 7.0, 7.0, np.nan])
        result = s.interpolate(method="linear", limit=1, limit_direction="forward")
        tm.assert_series_equal(result, expected)

        expected = Series([np.nan, 5.0, 5.0, 7.0, np.nan, np.nan])
        result = s.interpolate(method="linear", limit=1, limit_direction="backward")
        tm.assert_series_equal(result, expected)

        expected = Series([np.nan, 5.0, 5.0, 7.0, 7.0, np.nan])
        result = s.interpolate(method="linear", limit=1, limit_direction="both")
        tm.assert_series_equal(result, expected)

    @td.skip_if_no_scipy
    def test_interp_all_good(self):
        s = Series([1, 2, 3])
        result = s.interpolate(method="polynomial", order=1)
        tm.assert_series_equal(result, s)

        # non-scipy
        result = s.interpolate()
        tm.assert_series_equal(result, s)

    @pytest.mark.parametrize(
        "check_scipy", [False, pytest.param(True, marks=td.skip_if_no_scipy)]
    )
    def test_interp_multiIndex(self, check_scipy):
        idx = MultiIndex.from_tuples([(0, "a"), (1, "b"), (2, "c")])
        s = Series([1, 2, np.nan], index=idx)

        expected = s.copy()
        expected.loc[2] = 2
        result = s.interpolate()
        tm.assert_series_equal(result, expected)

        msg = "Only `method=linear` interpolation is supported on MultiIndexes"
        if check_scipy:
            with pytest.raises(ValueError, match=msg):
                s.interpolate(method="polynomial", order=1)

    @td.skip_if_no_scipy
    def test_interp_nonmono_raise(self):
        s = Series([1, np.nan, 3], index=[0, 2, 1])
        msg = "krogh interpolation requires that the index be monotonic"
        with pytest.raises(ValueError, match=msg):
            s.interpolate(method="krogh")

    @td.skip_if_no_scipy
    @pytest.mark.parametrize("method", ["nearest", "pad"])
    def test_interp_datetime64(self, method, tz_naive_fixture):
        df = Series(
            [1, np.nan, 3], index=date_range("1/1/2000", periods=3, tz=tz_naive_fixture)
        )
        result = df.interpolate(method=method)
        expected = Series(
            [1.0, 1.0, 3.0],
            index=date_range("1/1/2000", periods=3, tz=tz_naive_fixture),
        )
        tm.assert_series_equal(result, expected)

    def test_interp_pad_datetime64tz_values(self):
        # GH#27628 missing.interpolate_2d should handle datetimetz values
        dti = pd.date_range("2015-04-05", periods=3, tz="US/Central")
        ser = pd.Series(dti)
        ser[1] = pd.NaT
        result = ser.interpolate(method="pad")

        expected = pd.Series(dti)
        expected[1] = expected[0]
        tm.assert_series_equal(result, expected)

    def test_interp_limit_no_nans(self):
        # GH 7173
        s = pd.Series([1.0, 2.0, 3.0])
        result = s.interpolate(limit=1)
        expected = s
        tm.assert_series_equal(result, expected)

    @td.skip_if_no_scipy
    @pytest.mark.parametrize("method", ["polynomial", "spline"])
    def test_no_order(self, method):
        # see GH-10633, GH-24014
        s = Series([0, 1, np.nan, 3])
        msg = "You must specify the order of the spline or polynomial"
        with pytest.raises(ValueError, match=msg):
            s.interpolate(method=method)

    @td.skip_if_no_scipy
    @pytest.mark.parametrize("order", [-1, -1.0, 0, 0.0, np.nan])
    def test_interpolate_spline_invalid_order(self, order):
        s = Series([0, 1, np.nan, 3])
        msg = "order needs to be specified and greater than 0"
        with pytest.raises(ValueError, match=msg):
            s.interpolate(method="spline", order=order)

    @td.skip_if_no_scipy
    def test_spline(self):
        s = Series([1, 2, np.nan, 4, 5, np.nan, 7])
        result = s.interpolate(method="spline", order=1)
        expected = Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
        tm.assert_series_equal(result, expected)

    @td.skip_if_no_scipy
    def test_spline_extrapolate(self):
        s = Series([1, 2, 3, 4, np.nan, 6, np.nan])
        result3 = s.interpolate(method="spline", order=1, ext=3)
        expected3 = Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 6.0])
        tm.assert_series_equal(result3, expected3)

        result1 = s.interpolate(method="spline", order=1, ext=0)
        expected1 = Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
        tm.assert_series_equal(result1, expected1)

    @td.skip_if_no_scipy
    def test_spline_smooth(self):
        s = Series([1, 2, np.nan, 4, 5.1, np.nan, 7])
        assert (
            s.interpolate(method="spline", order=3, s=0)[5]
            != s.interpolate(method="spline", order=3)[5]
        )

    @td.skip_if_no_scipy
    def test_spline_interpolation(self):
        s = Series(np.arange(10) ** 2)
        s[np.random.randint(0, 9, 3)] = np.nan
        result1 = s.interpolate(method="spline", order=1)
        expected1 = s.interpolate(method="spline", order=1)
        tm.assert_series_equal(result1, expected1)

    def test_interp_timedelta64(self):
        # GH 6424
        df = Series([1, np.nan, 3], index=pd.to_timedelta([1, 2, 3]))
        result = df.interpolate(method="time")
        expected = Series([1.0, 2.0, 3.0], index=pd.to_timedelta([1, 2, 3]))
        tm.assert_series_equal(result, expected)

        # test for non uniform spacing
        df = Series([1, np.nan, 3], index=pd.to_timedelta([1, 2, 4]))
        result = df.interpolate(method="time")
        expected = Series([1.0, 1.666667, 3.0], index=pd.to_timedelta([1, 2, 4]))
        tm.assert_series_equal(result, expected)

    def test_series_interpolate_method_values(self):
        # GH#1646
        rng = date_range("1/1/2000", "1/20/2000", freq="D")
        ts = Series(np.random.randn(len(rng)), index=rng)

        ts[::2] = np.nan

        result = ts.interpolate(method="values")
        exp = ts.interpolate()
        tm.assert_series_equal(result, exp)

    def test_series_interpolate_intraday(self):
        # #1698
        index = pd.date_range("1/1/2012", periods=4, freq="12D")
        ts = pd.Series([0, 12, 24, 36], index)
        new_index = index.append(index + pd.DateOffset(days=1)).sort_values()

        exp = ts.reindex(new_index).interpolate(method="time")

        index = pd.date_range("1/1/2012", periods=4, freq="12H")
        ts = pd.Series([0, 12, 24, 36], index)
        new_index = index.append(index + pd.DateOffset(hours=1)).sort_values()
        result = ts.reindex(new_index).interpolate(method="time")

        tm.assert_numpy_array_equal(result.values, exp.values)

    @pytest.mark.parametrize(
        "ind",
        [
            ["a", "b", "c", "d"],
            pd.period_range(start="2019-01-01", periods=4),
            pd.interval_range(start=0, end=4),
        ],
    )
    def test_interp_non_timedelta_index(self, interp_methods_ind, ind):
        # gh 21662
        df = pd.DataFrame([0, 1, np.nan, 3], index=ind)

        method, kwargs = interp_methods_ind
        if method == "pchip":
            pytest.importorskip("scipy")

        if method == "linear":
            result = df[0].interpolate(**kwargs)
            expected = pd.Series([0.0, 1.0, 2.0, 3.0], name=0, index=ind)
            tm.assert_series_equal(result, expected)
        else:
            expected_error = (
                "Index column must be numeric or datetime type when "
                f"using {method} method other than linear. "
                "Try setting a numeric or datetime index column before "
                "interpolating."
            )
            with pytest.raises(ValueError, match=expected_error):
                df[0].interpolate(method=method, **kwargs)

    def test_interpolate_timedelta_index(self, interp_methods_ind):
        """
        Tests for non numerical index types  - object, period, timedelta
        Note that all methods except time, index, nearest and values
        are tested here.
        """
        # gh 21662
        ind = pd.timedelta_range(start=1, periods=4)
        df = pd.DataFrame([0, 1, np.nan, 3], index=ind)

        method, kwargs = interp_methods_ind
        if method == "pchip":
            pytest.importorskip("scipy")

        if method in {"linear", "pchip"}:
            result = df[0].interpolate(method=method, **kwargs)
            expected = pd.Series([0.0, 1.0, 2.0, 3.0], name=0, index=ind)
            tm.assert_series_equal(result, expected)
        else:
            pytest.skip(
                "This interpolation method is not supported for Timedelta Index yet."
            )

    @pytest.mark.parametrize(
        "ascending, expected_values",
        [(True, [1, 2, 3, 9, 10]), (False, [10, 9, 3, 2, 1])],
    )
    def test_interpolate_unsorted_index(self, ascending, expected_values):
        # GH 21037
        ts = pd.Series(data=[10, 9, np.nan, 2, 1], index=[10, 9, 3, 2, 1])
        result = ts.sort_index(ascending=ascending).interpolate(method="index")
        expected = pd.Series(data=expected_values, index=expected_values, dtype=float)
        tm.assert_series_equal(result, expected)
