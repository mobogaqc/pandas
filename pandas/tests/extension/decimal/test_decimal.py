import decimal

import numpy as np
import pandas as pd
import pandas.util.testing as tm
import pytest

from pandas.tests.extension import base

from .array import DecimalDtype, DecimalArray, make_data


@pytest.fixture
def dtype():
    return DecimalDtype()


@pytest.fixture
def data():
    return DecimalArray(make_data())


@pytest.fixture
def data_missing():
    return DecimalArray([decimal.Decimal('NaN'), decimal.Decimal(1)])


@pytest.fixture
def na_cmp():
    return lambda x, y: x.is_nan() and y.is_nan()


@pytest.fixture
def na_value():
    return decimal.Decimal("NaN")


class BaseDecimal(object):
    @staticmethod
    def assert_series_equal(left, right, *args, **kwargs):
        # tm.assert_series_equal doesn't handle Decimal('NaN').
        # We will ensure that the NA values match, and then
        # drop those values before moving on.

        left_na = left.isna()
        right_na = right.isna()

        tm.assert_series_equal(left_na, right_na)
        tm.assert_series_equal(left[~left_na], right[~right_na],
                               *args, **kwargs)

    @staticmethod
    def assert_frame_equal(left, right, *args, **kwargs):
        # TODO(EA): select_dtypes
        decimals = (left.dtypes == 'decimal').index

        for col in decimals:
            BaseDecimal.assert_series_equal(left[col], right[col],
                                            *args, **kwargs)

        left = left.drop(columns=decimals)
        right = right.drop(columns=decimals)
        tm.assert_frame_equal(left, right, *args, **kwargs)


class TestDtype(BaseDecimal, base.BaseDtypeTests):
    pass


class TestInterface(BaseDecimal, base.BaseInterfaceTests):
    pass


class TestConstructors(BaseDecimal, base.BaseConstructorsTests):
    pass


class TestReshaping(BaseDecimal, base.BaseReshapingTests):
    pass


class TestGetitem(BaseDecimal, base.BaseGetitemTests):
    pass


class TestMissing(BaseDecimal, base.BaseMissingTests):
    pass


class TestMethods(BaseDecimal, base.BaseMethodsTests):
    @pytest.mark.parametrize('dropna', [True, False])
    @pytest.mark.xfail(reason="value_counts not implemented yet.")
    def test_value_counts(self, all_data, dropna):
        all_data = all_data[:10]
        if dropna:
            other = np.array(all_data[~all_data.isna()])
        else:
            other = all_data

        result = pd.Series(all_data).value_counts(dropna=dropna).sort_index()
        expected = pd.Series(other).value_counts(dropna=dropna).sort_index()

        tm.assert_series_equal(result, expected)


class TestCasting(BaseDecimal, base.BaseCastingTests):
    pass


def test_series_constructor_coerce_data_to_extension_dtype_raises():
    xpr = ("Cannot cast data to extension dtype 'decimal'. Pass the "
           "extension array directly.")
    with tm.assert_raises_regex(ValueError, xpr):
        pd.Series([0, 1, 2], dtype=DecimalDtype())


def test_series_constructor_with_same_dtype_ok():
    arr = DecimalArray([decimal.Decimal('10.0')])
    result = pd.Series(arr, dtype=DecimalDtype())
    expected = pd.Series(arr)
    tm.assert_series_equal(result, expected)


def test_series_constructor_coerce_extension_array_to_dtype_raises():
    arr = DecimalArray([decimal.Decimal('10.0')])
    xpr = "Cannot specify a dtype 'int64' .* \('decimal'\)."

    with tm.assert_raises_regex(ValueError, xpr):
        pd.Series(arr, dtype='int64')


def test_dataframe_constructor_with_same_dtype_ok():
    arr = DecimalArray([decimal.Decimal('10.0')])

    result = pd.DataFrame({"A": arr}, dtype=DecimalDtype())
    expected = pd.DataFrame({"A": arr})
    tm.assert_frame_equal(result, expected)


def test_dataframe_constructor_with_different_dtype_raises():
    arr = DecimalArray([decimal.Decimal('10.0')])

    xpr = "Cannot coerce extension array to dtype 'int64'. "
    with tm.assert_raises_regex(ValueError, xpr):
        pd.DataFrame({"A": arr}, dtype='int64')
