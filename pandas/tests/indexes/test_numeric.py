from datetime import datetime, timedelta
import re

import numpy as np
import pytest

from pandas._libs.tslibs import Timestamp

import pandas as pd
from pandas import Float64Index, Index, Int64Index, Series, UInt64Index
from pandas.api.types import pandas_dtype
from pandas.tests.indexes.common import Base
import pandas.util.testing as tm


class Numeric(Base):
    def test_can_hold_identifiers(self):
        idx = self.create_index()
        key = idx[0]
        assert idx._can_hold_identifiers_and_holds_name(key) is False

    def test_numeric_compat(self):
        pass  # override Base method

    def test_explicit_conversions(self):

        # GH 8608
        # add/sub are overridden explicitly for Float/Int Index
        idx = self._holder(np.arange(5, dtype="int64"))

        # float conversions
        arr = np.arange(5, dtype="int64") * 3.2
        expected = Float64Index(arr)
        fidx = idx * 3.2
        tm.assert_index_equal(fidx, expected)
        fidx = 3.2 * idx
        tm.assert_index_equal(fidx, expected)

        # interops with numpy arrays
        expected = Float64Index(arr)
        a = np.zeros(5, dtype="float64")
        result = fidx - a
        tm.assert_index_equal(result, expected)

        expected = Float64Index(-arr)
        a = np.zeros(5, dtype="float64")
        result = a - fidx
        tm.assert_index_equal(result, expected)

    def test_index_groupby(self):
        int_idx = Index(range(6))
        float_idx = Index(np.arange(0, 0.6, 0.1))
        obj_idx = Index("A B C D E F".split())
        dt_idx = pd.date_range("2013-01-01", freq="M", periods=6)

        for idx in [int_idx, float_idx, obj_idx, dt_idx]:
            to_groupby = np.array([1, 2, np.nan, np.nan, 2, 1])
            tm.assert_dict_equal(
                idx.groupby(to_groupby), {1.0: idx[[0, 5]], 2.0: idx[[1, 4]]}
            )

            to_groupby = Index(
                [
                    datetime(2011, 11, 1),
                    datetime(2011, 12, 1),
                    pd.NaT,
                    pd.NaT,
                    datetime(2011, 12, 1),
                    datetime(2011, 11, 1),
                ],
                tz="UTC",
            ).values

            ex_keys = [Timestamp("2011-11-01"), Timestamp("2011-12-01")]
            expected = {ex_keys[0]: idx[[0, 5]], ex_keys[1]: idx[[1, 4]]}
            tm.assert_dict_equal(idx.groupby(to_groupby), expected)

    @pytest.mark.parametrize("klass", [list, tuple, np.array, Series])
    def test_where(self, klass):
        i = self.create_index()
        cond = [True] * len(i)
        expected = i
        result = i.where(klass(cond))

        cond = [False] + [True] * (len(i) - 1)
        expected = Float64Index([i._na_value] + i[1:].tolist())
        result = i.where(klass(cond))
        tm.assert_index_equal(result, expected)

    def test_insert(self, nulls_fixture):
        # GH 18295 (test missing)
        index = self.create_index()
        expected = Float64Index([index[0], np.nan] + list(index[1:]))
        result = index.insert(1, nulls_fixture)
        tm.assert_index_equal(result, expected)


class TestFloat64Index(Numeric):
    _holder = Float64Index

    @pytest.fixture(
        params=[
            [1.5, 2, 3, 4, 5],
            [0.0, 2.5, 5.0, 7.5, 10.0],
            [5, 4, 3, 2, 1.5],
            [10.0, 7.5, 5.0, 2.5, 0.0],
        ],
        ids=["mixed", "float", "mixed_dec", "float_dec"],
    )
    def indices(self, request):
        return Float64Index(request.param)

    @pytest.fixture
    def mixed_index(self):
        return Float64Index([1.5, 2, 3, 4, 5])

    @pytest.fixture
    def float_index(self):
        return Float64Index([0.0, 2.5, 5.0, 7.5, 10.0])

    def create_index(self):
        return Float64Index(np.arange(5, dtype="float64"))

    def test_repr_roundtrip(self, indices):
        tm.assert_index_equal(eval(repr(indices)), indices)

    def check_is_index(self, i):
        assert isinstance(i, Index)
        assert not isinstance(i, Float64Index)

    def check_coerce(self, a, b, is_float_index=True):
        assert a.equals(b)
        tm.assert_index_equal(a, b, exact=False)
        if is_float_index:
            assert isinstance(b, Float64Index)
        else:
            self.check_is_index(b)

    def test_constructor(self):

        # explicit construction
        index = Float64Index([1, 2, 3, 4, 5])
        assert isinstance(index, Float64Index)
        expected = np.array([1, 2, 3, 4, 5], dtype="float64")
        tm.assert_numpy_array_equal(index.values, expected)
        index = Float64Index(np.array([1, 2, 3, 4, 5]))
        assert isinstance(index, Float64Index)
        index = Float64Index([1.0, 2, 3, 4, 5])
        assert isinstance(index, Float64Index)
        index = Float64Index(np.array([1.0, 2, 3, 4, 5]))
        assert isinstance(index, Float64Index)
        assert index.dtype == float

        index = Float64Index(np.array([1.0, 2, 3, 4, 5]), dtype=np.float32)
        assert isinstance(index, Float64Index)
        assert index.dtype == np.float64

        index = Float64Index(np.array([1, 2, 3, 4, 5]), dtype=np.float32)
        assert isinstance(index, Float64Index)
        assert index.dtype == np.float64

        # nan handling
        result = Float64Index([np.nan, np.nan])
        assert pd.isna(result.values).all()
        result = Float64Index(np.array([np.nan]))
        assert pd.isna(result.values).all()
        result = Index(np.array([np.nan]))
        assert pd.isna(result.values).all()

    @pytest.mark.parametrize(
        "index, dtype",
        [
            (pd.Int64Index, "float64"),
            (pd.UInt64Index, "categorical"),
            (pd.Float64Index, "datetime64"),
            (pd.RangeIndex, "float64"),
        ],
    )
    def test_invalid_dtype(self, index, dtype):
        # GH 29539
        with pytest.raises(
            ValueError,
            match=rf"Incorrect `dtype` passed: expected \w+(?: \w+)?, received {dtype}",
        ):
            index([1, 2, 3], dtype=dtype)

    def test_constructor_invalid(self):

        # invalid
        msg = (
            r"Float64Index\(\.\.\.\) must be called with a collection of"
            r" some kind, 0\.0 was passed"
        )
        with pytest.raises(TypeError, match=msg):
            Float64Index(0.0)
        msg = (
            "String dtype not supported, you may need to explicitly cast to"
            " a numeric type"
        )
        with pytest.raises(TypeError, match=msg):
            Float64Index(["a", "b", 0.0])
        msg = r"float\(\) argument must be a string or a number, not 'Timestamp'"
        with pytest.raises(TypeError, match=msg):
            Float64Index([Timestamp("20130101")])

    def test_constructor_coerce(self, mixed_index, float_index):

        self.check_coerce(mixed_index, Index([1.5, 2, 3, 4, 5]))
        self.check_coerce(float_index, Index(np.arange(5) * 2.5))
        self.check_coerce(
            float_index, Index(np.array(np.arange(5) * 2.5, dtype=object))
        )

    def test_constructor_explicit(self, mixed_index, float_index):

        # these don't auto convert
        self.check_coerce(
            float_index, Index((np.arange(5) * 2.5), dtype=object), is_float_index=False
        )
        self.check_coerce(
            mixed_index, Index([1.5, 2, 3, 4, 5], dtype=object), is_float_index=False
        )

    def test_astype(self, mixed_index, float_index):

        result = float_index.astype(object)
        assert result.equals(float_index)
        assert float_index.equals(result)
        self.check_is_index(result)

        i = mixed_index.copy()
        i.name = "foo"
        result = i.astype(object)
        assert result.equals(i)
        assert i.equals(result)
        self.check_is_index(result)

        # GH 12881
        # a float astype int
        for dtype in ["int16", "int32", "int64"]:
            i = Float64Index([0, 1, 2])
            result = i.astype(dtype)
            expected = Int64Index([0, 1, 2])
            tm.assert_index_equal(result, expected)

            i = Float64Index([0, 1.1, 2])
            result = i.astype(dtype)
            expected = Int64Index([0, 1, 2])
            tm.assert_index_equal(result, expected)

        for dtype in ["float32", "float64"]:
            i = Float64Index([0, 1, 2])
            result = i.astype(dtype)
            expected = i
            tm.assert_index_equal(result, expected)

            i = Float64Index([0, 1.1, 2])
            result = i.astype(dtype)
            expected = Index(i.values.astype(dtype))
            tm.assert_index_equal(result, expected)

        # invalid
        for dtype in ["M8[ns]", "m8[ns]"]:
            msg = (
                f"Cannot convert Float64Index to dtype {pandas_dtype(dtype)}; "
                f"integer values are required for conversion"
            )
            with pytest.raises(TypeError, match=re.escape(msg)):
                i.astype(dtype)

        # GH 13149
        for dtype in ["int16", "int32", "int64"]:
            i = Float64Index([0, 1.1, np.NAN])
            msg = r"Cannot convert non-finite values \(NA or inf\) to integer"
            with pytest.raises(ValueError, match=msg):
                i.astype(dtype)

    def test_cannot_cast_inf_to_int(self):
        idx = pd.Float64Index([1, 2, np.inf])

        msg = r"Cannot convert non-finite values \(NA or inf\) to integer"
        with pytest.raises(ValueError, match=msg):
            idx.astype(int)

    def test_type_coercion_fail(self, any_int_dtype):
        # see gh-15832
        msg = "Trying to coerce float values to integers"
        with pytest.raises(ValueError, match=msg):
            Index([1, 2, 3.5], dtype=any_int_dtype)

    def test_type_coercion_valid(self, float_dtype):
        # There is no Float32Index, so we always
        # generate Float64Index.
        i = Index([1, 2, 3.5], dtype=float_dtype)
        tm.assert_index_equal(i, Index([1, 2, 3.5]))

    def test_equals_numeric(self):

        i = Float64Index([1.0, 2.0])
        assert i.equals(i)
        assert i.identical(i)

        i2 = Float64Index([1.0, 2.0])
        assert i.equals(i2)

        i = Float64Index([1.0, np.nan])
        assert i.equals(i)
        assert i.identical(i)

        i2 = Float64Index([1.0, np.nan])
        assert i.equals(i2)

    def test_get_indexer(self):
        idx = Float64Index([0.0, 1.0, 2.0])
        tm.assert_numpy_array_equal(
            idx.get_indexer(idx), np.array([0, 1, 2], dtype=np.intp)
        )

        target = [-0.1, 0.5, 1.1]
        tm.assert_numpy_array_equal(
            idx.get_indexer(target, "pad"), np.array([-1, 0, 1], dtype=np.intp)
        )
        tm.assert_numpy_array_equal(
            idx.get_indexer(target, "backfill"), np.array([0, 1, 2], dtype=np.intp)
        )
        tm.assert_numpy_array_equal(
            idx.get_indexer(target, "nearest"), np.array([0, 1, 1], dtype=np.intp)
        )

    def test_get_loc(self):
        idx = Float64Index([0.0, 1.0, 2.0])
        for method in [None, "pad", "backfill", "nearest"]:
            assert idx.get_loc(1, method) == 1
            if method is not None:
                assert idx.get_loc(1, method, tolerance=0) == 1

        for method, loc in [("pad", 1), ("backfill", 2), ("nearest", 1)]:
            assert idx.get_loc(1.1, method) == loc
            assert idx.get_loc(1.1, method, tolerance=0.9) == loc

        with pytest.raises(KeyError, match="^'foo'$"):
            idx.get_loc("foo")
        with pytest.raises(KeyError, match=r"^1\.5$"):
            idx.get_loc(1.5)
        with pytest.raises(KeyError, match=r"^1\.5$"):
            idx.get_loc(1.5, method="pad", tolerance=0.1)
        with pytest.raises(KeyError, match="^True$"):
            idx.get_loc(True)
        with pytest.raises(KeyError, match="^False$"):
            idx.get_loc(False)

        with pytest.raises(ValueError, match="must be numeric"):
            idx.get_loc(1.4, method="nearest", tolerance="foo")

        with pytest.raises(ValueError, match="must contain numeric elements"):
            idx.get_loc(1.4, method="nearest", tolerance=np.array(["foo"]))

        with pytest.raises(
            ValueError, match="tolerance size must match target index size"
        ):
            idx.get_loc(1.4, method="nearest", tolerance=np.array([1, 2]))

    def test_get_loc_na(self):
        idx = Float64Index([np.nan, 1, 2])
        assert idx.get_loc(1) == 1
        assert idx.get_loc(np.nan) == 0

        idx = Float64Index([np.nan, 1, np.nan])
        assert idx.get_loc(1) == 1

        # representable by slice [0:2:2]
        # pytest.raises(KeyError, idx.slice_locs, np.nan)
        sliced = idx.slice_locs(np.nan)
        assert isinstance(sliced, tuple)
        assert sliced == (0, 3)

        # not representable by slice
        idx = Float64Index([np.nan, 1, np.nan, np.nan])
        assert idx.get_loc(1) == 1
        msg = "'Cannot get left slice bound for non-unique label: nan"
        with pytest.raises(KeyError, match=msg):
            idx.slice_locs(np.nan)

    def test_get_loc_missing_nan(self):
        # GH 8569
        idx = Float64Index([1, 2])
        assert idx.get_loc(1) == 0
        with pytest.raises(KeyError, match=r"^3\.0$"):
            idx.get_loc(3)
        with pytest.raises(KeyError, match="^nan$"):
            idx.get_loc(np.nan)
        with pytest.raises(KeyError, match=r"^\[nan\]$"):
            idx.get_loc([np.nan])

    def test_contains_nans(self):
        i = Float64Index([1.0, 2.0, np.nan])
        assert np.nan in i

    def test_contains_not_nans(self):
        i = Float64Index([1.0, 2.0, np.nan])
        assert 1.0 in i

    def test_doesnt_contain_all_the_things(self):
        i = Float64Index([np.nan])
        assert not i.isin([0]).item()
        assert not i.isin([1]).item()
        assert i.isin([np.nan]).item()

    def test_nan_multiple_containment(self):
        i = Float64Index([1.0, np.nan])
        tm.assert_numpy_array_equal(i.isin([1.0]), np.array([True, False]))
        tm.assert_numpy_array_equal(i.isin([2.0, np.pi]), np.array([False, False]))
        tm.assert_numpy_array_equal(i.isin([np.nan]), np.array([False, True]))
        tm.assert_numpy_array_equal(i.isin([1.0, np.nan]), np.array([True, True]))
        i = Float64Index([1.0, 2.0])
        tm.assert_numpy_array_equal(i.isin([np.nan]), np.array([False, False]))

    def test_astype_from_object(self):
        index = Index([1.0, np.nan, 0.2], dtype="object")
        result = index.astype(float)
        expected = Float64Index([1.0, np.nan, 0.2])
        assert result.dtype == expected.dtype
        tm.assert_index_equal(result, expected)

    def test_fillna_float64(self):
        # GH 11343
        idx = Index([1.0, np.nan, 3.0], dtype=float, name="x")
        # can't downcast
        exp = Index([1.0, 0.1, 3.0], name="x")
        tm.assert_index_equal(idx.fillna(0.1), exp)

        # downcast
        exp = Float64Index([1.0, 2.0, 3.0], name="x")
        tm.assert_index_equal(idx.fillna(2), exp)

        # object
        exp = Index([1.0, "obj", 3.0], name="x")
        tm.assert_index_equal(idx.fillna("obj"), exp)

    def test_take_fill_value(self):
        # GH 12631
        idx = pd.Float64Index([1.0, 2.0, 3.0], name="xxx")
        result = idx.take(np.array([1, 0, -1]))
        expected = pd.Float64Index([2.0, 1.0, 3.0], name="xxx")
        tm.assert_index_equal(result, expected)

        # fill_value
        result = idx.take(np.array([1, 0, -1]), fill_value=True)
        expected = pd.Float64Index([2.0, 1.0, np.nan], name="xxx")
        tm.assert_index_equal(result, expected)

        # allow_fill=False
        result = idx.take(np.array([1, 0, -1]), allow_fill=False, fill_value=True)
        expected = pd.Float64Index([2.0, 1.0, 3.0], name="xxx")
        tm.assert_index_equal(result, expected)

        msg = (
            "When allow_fill=True and fill_value is not None, "
            "all indices must be >= -1"
        )
        with pytest.raises(ValueError, match=msg):
            idx.take(np.array([1, 0, -2]), fill_value=True)
        with pytest.raises(ValueError, match=msg):
            idx.take(np.array([1, 0, -5]), fill_value=True)

        with pytest.raises(IndexError):
            idx.take(np.array([1, -5]))


class NumericInt(Numeric):
    def test_view(self):
        i = self._holder([], name="Foo")
        i_view = i.view()
        assert i_view.name == "Foo"

        i_view = i.view(self._dtype)
        tm.assert_index_equal(i, self._holder(i_view, name="Foo"))

        i_view = i.view(self._holder)
        tm.assert_index_equal(i, self._holder(i_view, name="Foo"))

    def test_is_monotonic(self):
        index = self._holder([1, 2, 3, 4])
        assert index.is_monotonic is True
        assert index.is_monotonic_increasing is True
        assert index._is_strictly_monotonic_increasing is True
        assert index.is_monotonic_decreasing is False
        assert index._is_strictly_monotonic_decreasing is False

        index = self._holder([4, 3, 2, 1])
        assert index.is_monotonic is False
        assert index._is_strictly_monotonic_increasing is False
        assert index._is_strictly_monotonic_decreasing is True

        index = self._holder([1])
        assert index.is_monotonic is True
        assert index.is_monotonic_increasing is True
        assert index.is_monotonic_decreasing is True
        assert index._is_strictly_monotonic_increasing is True
        assert index._is_strictly_monotonic_decreasing is True

    def test_is_strictly_monotonic(self):
        index = self._holder([1, 1, 2, 3])
        assert index.is_monotonic_increasing is True
        assert index._is_strictly_monotonic_increasing is False

        index = self._holder([3, 2, 1, 1])
        assert index.is_monotonic_decreasing is True
        assert index._is_strictly_monotonic_decreasing is False

        index = self._holder([1, 1])
        assert index.is_monotonic_increasing
        assert index.is_monotonic_decreasing
        assert not index._is_strictly_monotonic_increasing
        assert not index._is_strictly_monotonic_decreasing

    def test_logical_compat(self):
        idx = self.create_index()
        assert idx.all() == idx.values.all()
        assert idx.any() == idx.values.any()

    def test_identical(self):
        index = self.create_index()
        i = Index(index.copy())
        assert i.identical(index)

        same_values_different_type = Index(i, dtype=object)
        assert not i.identical(same_values_different_type)

        i = index.copy(dtype=object)
        i = i.rename("foo")
        same_values = Index(i, dtype=object)
        assert same_values.identical(i)

        assert not i.identical(index)
        assert Index(same_values, name="foo", dtype=object).identical(i)

        assert not index.copy(dtype=object).identical(index.copy(dtype=self._dtype))

    def test_join_non_unique(self):
        left = Index([4, 4, 3, 3])

        joined, lidx, ridx = left.join(left, return_indexers=True)

        exp_joined = Index([3, 3, 3, 3, 4, 4, 4, 4])
        tm.assert_index_equal(joined, exp_joined)

        exp_lidx = np.array([2, 2, 3, 3, 0, 0, 1, 1], dtype=np.intp)
        tm.assert_numpy_array_equal(lidx, exp_lidx)

        exp_ridx = np.array([2, 3, 2, 3, 0, 1, 0, 1], dtype=np.intp)
        tm.assert_numpy_array_equal(ridx, exp_ridx)

    def test_join_self(self, join_type):
        index = self.create_index()
        joined = index.join(index, how=join_type)
        assert index is joined

    def test_union_noncomparable(self):
        # corner case, non-Int64Index
        index = self.create_index()
        other = Index([datetime.now() + timedelta(i) for i in range(4)], dtype=object)
        result = index.union(other)
        expected = Index(np.concatenate((index, other)))
        tm.assert_index_equal(result, expected)

        result = other.union(index)
        expected = Index(np.concatenate((other, index)))
        tm.assert_index_equal(result, expected)

    def test_cant_or_shouldnt_cast(self):
        msg = (
            "String dtype not supported, you may need to explicitly cast to"
            " a numeric type"
        )
        # can't
        data = ["foo", "bar", "baz"]
        with pytest.raises(TypeError, match=msg):
            self._holder(data)

        # shouldn't
        data = ["0", "1", "2"]
        with pytest.raises(TypeError, match=msg):
            self._holder(data)

    def test_view_index(self):
        index = self.create_index()
        index.view(Index)

    def test_prevent_casting(self):
        index = self.create_index()
        result = index.astype("O")
        assert result.dtype == np.object_

    def test_take_preserve_name(self):
        index = self._holder([1, 2, 3, 4], name="foo")
        taken = index.take([3, 0, 1])
        assert index.name == taken.name

    def test_take_fill_value(self):
        # see gh-12631
        idx = self._holder([1, 2, 3], name="xxx")
        result = idx.take(np.array([1, 0, -1]))
        expected = self._holder([2, 1, 3], name="xxx")
        tm.assert_index_equal(result, expected)

        name = self._holder.__name__
        msg = f"Unable to fill values because {name} cannot contain NA"

        # fill_value=True
        with pytest.raises(ValueError, match=msg):
            idx.take(np.array([1, 0, -1]), fill_value=True)

        # allow_fill=False
        result = idx.take(np.array([1, 0, -1]), allow_fill=False, fill_value=True)
        expected = self._holder([2, 1, 3], name="xxx")
        tm.assert_index_equal(result, expected)

        with pytest.raises(ValueError, match=msg):
            idx.take(np.array([1, 0, -2]), fill_value=True)
        with pytest.raises(ValueError, match=msg):
            idx.take(np.array([1, 0, -5]), fill_value=True)

        with pytest.raises(IndexError):
            idx.take(np.array([1, -5]))

    def test_slice_keep_name(self):
        idx = self._holder([1, 2], name="asdf")
        assert idx.name == idx[1:].name


class TestInt64Index(NumericInt):
    _dtype = "int64"
    _holder = Int64Index

    @pytest.fixture(
        params=[range(0, 20, 2), range(19, -1, -1)], ids=["index_inc", "index_dec"]
    )
    def indices(self, request):
        return Int64Index(request.param)

    def create_index(self):
        # return Int64Index(np.arange(5, dtype="int64"))
        return Int64Index(range(0, 20, 2))

    def test_constructor(self):
        # pass list, coerce fine
        index = Int64Index([-5, 0, 1, 2])
        expected = Index([-5, 0, 1, 2], dtype=np.int64)
        tm.assert_index_equal(index, expected)

        # from iterable
        index = Int64Index(iter([-5, 0, 1, 2]))
        tm.assert_index_equal(index, expected)

        # scalar raise Exception
        msg = (
            r"Int64Index\(\.\.\.\) must be called with a collection of some"
            " kind, 5 was passed"
        )
        with pytest.raises(TypeError, match=msg):
            Int64Index(5)

        # copy
        arr = index.values
        new_index = Int64Index(arr, copy=True)
        tm.assert_index_equal(new_index, index)
        val = arr[0] + 3000

        # this should not change index
        arr[0] = val
        assert new_index[0] != val

        # interpret list-like
        expected = Int64Index([5, 0])
        for cls in [Index, Int64Index]:
            for idx in [
                cls([5, 0], dtype="int64"),
                cls(np.array([5, 0]), dtype="int64"),
                cls(Series([5, 0]), dtype="int64"),
            ]:
                tm.assert_index_equal(idx, expected)

    def test_constructor_corner(self):
        arr = np.array([1, 2, 3, 4], dtype=object)
        index = Int64Index(arr)
        assert index.values.dtype == np.int64
        tm.assert_index_equal(index, Index(arr))

        # preventing casting
        arr = np.array([1, "2", 3, "4"], dtype=object)
        with pytest.raises(TypeError, match="casting"):
            Int64Index(arr)

        arr_with_floats = [0, 2, 3, 4, 5, 1.25, 3, -1]
        with pytest.raises(TypeError, match="casting"):
            Int64Index(arr_with_floats)

    def test_constructor_coercion_signed_to_unsigned(self, uint_dtype):

        # see gh-15832
        msg = "Trying to coerce negative values to unsigned integers"

        with pytest.raises(OverflowError, match=msg):
            Index([-1], dtype=uint_dtype)

    def test_constructor_unwraps_index(self):
        idx = pd.Index([1, 2])
        result = pd.Int64Index(idx)
        expected = np.array([1, 2], dtype="int64")
        tm.assert_numpy_array_equal(result._data, expected)

    def test_coerce_list(self):
        # coerce things
        arr = Index([1, 2, 3, 4])
        assert isinstance(arr, Int64Index)

        # but not if explicit dtype passed
        arr = Index([1, 2, 3, 4], dtype=object)
        assert isinstance(arr, Index)

    def test_get_indexer(self):
        index = self.create_index()
        target = Int64Index(np.arange(10))
        indexer = index.get_indexer(target)
        expected = np.array([0, -1, 1, -1, 2, -1, 3, -1, 4, -1], dtype=np.intp)
        tm.assert_numpy_array_equal(indexer, expected)

        target = Int64Index(np.arange(10))
        indexer = index.get_indexer(target, method="pad")
        expected = np.array([0, 0, 1, 1, 2, 2, 3, 3, 4, 4], dtype=np.intp)
        tm.assert_numpy_array_equal(indexer, expected)

        target = Int64Index(np.arange(10))
        indexer = index.get_indexer(target, method="backfill")
        expected = np.array([0, 1, 1, 2, 2, 3, 3, 4, 4, 5], dtype=np.intp)
        tm.assert_numpy_array_equal(indexer, expected)

    def test_get_indexer_nan(self):
        # GH 7820
        result = Index([1, 2, np.nan]).get_indexer([np.nan])
        expected = np.array([2], dtype=np.intp)
        tm.assert_numpy_array_equal(result, expected)

    def test_intersection(self):
        index = self.create_index()
        other = Index([1, 2, 3, 4, 5])
        result = index.intersection(other)
        expected = Index(np.sort(np.intersect1d(index.values, other.values)))
        tm.assert_index_equal(result, expected)

        result = other.intersection(index)
        expected = Index(
            np.sort(np.asarray(np.intersect1d(index.values, other.values)))
        )
        tm.assert_index_equal(result, expected)

    def test_join_inner(self):
        index = self.create_index()
        other = Int64Index([7, 12, 25, 1, 2, 5])
        other_mono = Int64Index([1, 2, 5, 7, 12, 25])

        # not monotonic
        res, lidx, ridx = index.join(other, how="inner", return_indexers=True)

        # no guarantee of sortedness, so sort for comparison purposes
        ind = res.argsort()
        res = res.take(ind)
        lidx = lidx.take(ind)
        ridx = ridx.take(ind)

        eres = Int64Index([2, 12])
        elidx = np.array([1, 6], dtype=np.intp)
        eridx = np.array([4, 1], dtype=np.intp)

        assert isinstance(res, Int64Index)
        tm.assert_index_equal(res, eres)
        tm.assert_numpy_array_equal(lidx, elidx)
        tm.assert_numpy_array_equal(ridx, eridx)

        # monotonic
        res, lidx, ridx = index.join(other_mono, how="inner", return_indexers=True)

        res2 = index.intersection(other_mono)
        tm.assert_index_equal(res, res2)

        elidx = np.array([1, 6], dtype=np.intp)
        eridx = np.array([1, 4], dtype=np.intp)
        assert isinstance(res, Int64Index)
        tm.assert_index_equal(res, eres)
        tm.assert_numpy_array_equal(lidx, elidx)
        tm.assert_numpy_array_equal(ridx, eridx)

    def test_join_left(self):
        index = self.create_index()
        other = Int64Index([7, 12, 25, 1, 2, 5])
        other_mono = Int64Index([1, 2, 5, 7, 12, 25])

        # not monotonic
        res, lidx, ridx = index.join(other, how="left", return_indexers=True)
        eres = index
        eridx = np.array([-1, 4, -1, -1, -1, -1, 1, -1, -1, -1], dtype=np.intp)

        assert isinstance(res, Int64Index)
        tm.assert_index_equal(res, eres)
        assert lidx is None
        tm.assert_numpy_array_equal(ridx, eridx)

        # monotonic
        res, lidx, ridx = index.join(other_mono, how="left", return_indexers=True)
        eridx = np.array([-1, 1, -1, -1, -1, -1, 4, -1, -1, -1], dtype=np.intp)
        assert isinstance(res, Int64Index)
        tm.assert_index_equal(res, eres)
        assert lidx is None
        tm.assert_numpy_array_equal(ridx, eridx)

        # non-unique
        idx = Index([1, 1, 2, 5])
        idx2 = Index([1, 2, 5, 7, 9])
        res, lidx, ridx = idx2.join(idx, how="left", return_indexers=True)
        eres = Index([1, 1, 2, 5, 7, 9])  # 1 is in idx2, so it should be x2
        eridx = np.array([0, 1, 2, 3, -1, -1], dtype=np.intp)
        elidx = np.array([0, 0, 1, 2, 3, 4], dtype=np.intp)
        tm.assert_index_equal(res, eres)
        tm.assert_numpy_array_equal(lidx, elidx)
        tm.assert_numpy_array_equal(ridx, eridx)

    def test_join_right(self):
        index = self.create_index()
        other = Int64Index([7, 12, 25, 1, 2, 5])
        other_mono = Int64Index([1, 2, 5, 7, 12, 25])

        # not monotonic
        res, lidx, ridx = index.join(other, how="right", return_indexers=True)
        eres = other
        elidx = np.array([-1, 6, -1, -1, 1, -1], dtype=np.intp)

        assert isinstance(other, Int64Index)
        tm.assert_index_equal(res, eres)
        tm.assert_numpy_array_equal(lidx, elidx)
        assert ridx is None

        # monotonic
        res, lidx, ridx = index.join(other_mono, how="right", return_indexers=True)
        eres = other_mono
        elidx = np.array([-1, 1, -1, -1, 6, -1], dtype=np.intp)
        assert isinstance(other, Int64Index)
        tm.assert_index_equal(res, eres)
        tm.assert_numpy_array_equal(lidx, elidx)
        assert ridx is None

        # non-unique
        idx = Index([1, 1, 2, 5])
        idx2 = Index([1, 2, 5, 7, 9])
        res, lidx, ridx = idx.join(idx2, how="right", return_indexers=True)
        eres = Index([1, 1, 2, 5, 7, 9])  # 1 is in idx2, so it should be x2
        elidx = np.array([0, 1, 2, 3, -1, -1], dtype=np.intp)
        eridx = np.array([0, 0, 1, 2, 3, 4], dtype=np.intp)
        tm.assert_index_equal(res, eres)
        tm.assert_numpy_array_equal(lidx, elidx)
        tm.assert_numpy_array_equal(ridx, eridx)

    def test_join_non_int_index(self):
        index = self.create_index()
        other = Index([3, 6, 7, 8, 10], dtype=object)

        outer = index.join(other, how="outer")
        outer2 = other.join(index, how="outer")
        expected = Index([0, 2, 3, 4, 6, 7, 8, 10, 12, 14, 16, 18])
        tm.assert_index_equal(outer, outer2)
        tm.assert_index_equal(outer, expected)

        inner = index.join(other, how="inner")
        inner2 = other.join(index, how="inner")
        expected = Index([6, 8, 10])
        tm.assert_index_equal(inner, inner2)
        tm.assert_index_equal(inner, expected)

        left = index.join(other, how="left")
        tm.assert_index_equal(left, index.astype(object))

        left2 = other.join(index, how="left")
        tm.assert_index_equal(left2, other)

        right = index.join(other, how="right")
        tm.assert_index_equal(right, other)

        right2 = other.join(index, how="right")
        tm.assert_index_equal(right2, index.astype(object))

    def test_join_outer(self):
        index = self.create_index()
        other = Int64Index([7, 12, 25, 1, 2, 5])
        other_mono = Int64Index([1, 2, 5, 7, 12, 25])

        # not monotonic
        # guarantee of sortedness
        res, lidx, ridx = index.join(other, how="outer", return_indexers=True)
        noidx_res = index.join(other, how="outer")
        tm.assert_index_equal(res, noidx_res)

        eres = Int64Index([0, 1, 2, 4, 5, 6, 7, 8, 10, 12, 14, 16, 18, 25])
        elidx = np.array([0, -1, 1, 2, -1, 3, -1, 4, 5, 6, 7, 8, 9, -1], dtype=np.intp)
        eridx = np.array(
            [-1, 3, 4, -1, 5, -1, 0, -1, -1, 1, -1, -1, -1, 2], dtype=np.intp
        )

        assert isinstance(res, Int64Index)
        tm.assert_index_equal(res, eres)
        tm.assert_numpy_array_equal(lidx, elidx)
        tm.assert_numpy_array_equal(ridx, eridx)

        # monotonic
        res, lidx, ridx = index.join(other_mono, how="outer", return_indexers=True)
        noidx_res = index.join(other_mono, how="outer")
        tm.assert_index_equal(res, noidx_res)

        elidx = np.array([0, -1, 1, 2, -1, 3, -1, 4, 5, 6, 7, 8, 9, -1], dtype=np.intp)
        eridx = np.array(
            [-1, 0, 1, -1, 2, -1, 3, -1, -1, 4, -1, -1, -1, 5], dtype=np.intp
        )
        assert isinstance(res, Int64Index)
        tm.assert_index_equal(res, eres)
        tm.assert_numpy_array_equal(lidx, elidx)
        tm.assert_numpy_array_equal(ridx, eridx)


class TestUInt64Index(NumericInt):

    _dtype = "uint64"
    _holder = UInt64Index

    @pytest.fixture(
        params=[
            [2 ** 63, 2 ** 63 + 10, 2 ** 63 + 15, 2 ** 63 + 20, 2 ** 63 + 25],
            [2 ** 63 + 25, 2 ** 63 + 20, 2 ** 63 + 15, 2 ** 63 + 10, 2 ** 63],
        ],
        ids=["index_inc", "index_dec"],
    )
    def indices(self, request):
        return UInt64Index(request.param)

    @pytest.fixture
    def index_large(self):
        # large values used in TestUInt64Index where no compat needed with Int64/Float64
        large = [2 ** 63, 2 ** 63 + 10, 2 ** 63 + 15, 2 ** 63 + 20, 2 ** 63 + 25]
        return UInt64Index(large)

    def create_index(self):
        # compat with shared Int64/Float64 tests; use index_large for UInt64 only tests
        return UInt64Index(np.arange(5, dtype="uint64"))

    def test_constructor(self):
        idx = UInt64Index([1, 2, 3])
        res = Index([1, 2, 3], dtype=np.uint64)
        tm.assert_index_equal(res, idx)

        idx = UInt64Index([1, 2 ** 63])
        res = Index([1, 2 ** 63], dtype=np.uint64)
        tm.assert_index_equal(res, idx)

        idx = UInt64Index([1, 2 ** 63])
        res = Index([1, 2 ** 63])
        tm.assert_index_equal(res, idx)

        idx = Index([-1, 2 ** 63], dtype=object)
        res = Index(np.array([-1, 2 ** 63], dtype=object))
        tm.assert_index_equal(res, idx)

        # https://github.com/pandas-dev/pandas/issues/29526
        idx = UInt64Index([1, 2 ** 63 + 1], dtype=np.uint64)
        res = Index([1, 2 ** 63 + 1], dtype=np.uint64)
        tm.assert_index_equal(res, idx)

    def test_get_indexer(self, index_large):
        target = UInt64Index(np.arange(10).astype("uint64") * 5 + 2 ** 63)
        indexer = index_large.get_indexer(target)
        expected = np.array([0, -1, 1, 2, 3, 4, -1, -1, -1, -1], dtype=np.intp)
        tm.assert_numpy_array_equal(indexer, expected)

        target = UInt64Index(np.arange(10).astype("uint64") * 5 + 2 ** 63)
        indexer = index_large.get_indexer(target, method="pad")
        expected = np.array([0, 0, 1, 2, 3, 4, 4, 4, 4, 4], dtype=np.intp)
        tm.assert_numpy_array_equal(indexer, expected)

        target = UInt64Index(np.arange(10).astype("uint64") * 5 + 2 ** 63)
        indexer = index_large.get_indexer(target, method="backfill")
        expected = np.array([0, 1, 1, 2, 3, 4, -1, -1, -1, -1], dtype=np.intp)
        tm.assert_numpy_array_equal(indexer, expected)

    def test_intersection(self, index_large):
        other = Index([2 ** 63, 2 ** 63 + 5, 2 ** 63 + 10, 2 ** 63 + 15, 2 ** 63 + 20])
        result = index_large.intersection(other)
        expected = Index(np.sort(np.intersect1d(index_large.values, other.values)))
        tm.assert_index_equal(result, expected)

        result = other.intersection(index_large)
        expected = Index(
            np.sort(np.asarray(np.intersect1d(index_large.values, other.values)))
        )
        tm.assert_index_equal(result, expected)

    def test_join_inner(self, index_large):
        other = UInt64Index(2 ** 63 + np.array([7, 12, 25, 1, 2, 10], dtype="uint64"))
        other_mono = UInt64Index(
            2 ** 63 + np.array([1, 2, 7, 10, 12, 25], dtype="uint64")
        )

        # not monotonic
        res, lidx, ridx = index_large.join(other, how="inner", return_indexers=True)

        # no guarantee of sortedness, so sort for comparison purposes
        ind = res.argsort()
        res = res.take(ind)
        lidx = lidx.take(ind)
        ridx = ridx.take(ind)

        eres = UInt64Index(2 ** 63 + np.array([10, 25], dtype="uint64"))
        elidx = np.array([1, 4], dtype=np.intp)
        eridx = np.array([5, 2], dtype=np.intp)

        assert isinstance(res, UInt64Index)
        tm.assert_index_equal(res, eres)
        tm.assert_numpy_array_equal(lidx, elidx)
        tm.assert_numpy_array_equal(ridx, eridx)

        # monotonic
        res, lidx, ridx = index_large.join(
            other_mono, how="inner", return_indexers=True
        )

        res2 = index_large.intersection(other_mono)
        tm.assert_index_equal(res, res2)

        elidx = np.array([1, 4], dtype=np.intp)
        eridx = np.array([3, 5], dtype=np.intp)

        assert isinstance(res, UInt64Index)
        tm.assert_index_equal(res, eres)
        tm.assert_numpy_array_equal(lidx, elidx)
        tm.assert_numpy_array_equal(ridx, eridx)

    def test_join_left(self, index_large):
        other = UInt64Index(2 ** 63 + np.array([7, 12, 25, 1, 2, 10], dtype="uint64"))
        other_mono = UInt64Index(
            2 ** 63 + np.array([1, 2, 7, 10, 12, 25], dtype="uint64")
        )

        # not monotonic
        res, lidx, ridx = index_large.join(other, how="left", return_indexers=True)
        eres = index_large
        eridx = np.array([-1, 5, -1, -1, 2], dtype=np.intp)

        assert isinstance(res, UInt64Index)
        tm.assert_index_equal(res, eres)
        assert lidx is None
        tm.assert_numpy_array_equal(ridx, eridx)

        # monotonic
        res, lidx, ridx = index_large.join(other_mono, how="left", return_indexers=True)
        eridx = np.array([-1, 3, -1, -1, 5], dtype=np.intp)

        assert isinstance(res, UInt64Index)
        tm.assert_index_equal(res, eres)
        assert lidx is None
        tm.assert_numpy_array_equal(ridx, eridx)

        # non-unique
        idx = UInt64Index(2 ** 63 + np.array([1, 1, 2, 5], dtype="uint64"))
        idx2 = UInt64Index(2 ** 63 + np.array([1, 2, 5, 7, 9], dtype="uint64"))
        res, lidx, ridx = idx2.join(idx, how="left", return_indexers=True)

        # 1 is in idx2, so it should be x2
        eres = UInt64Index(2 ** 63 + np.array([1, 1, 2, 5, 7, 9], dtype="uint64"))
        eridx = np.array([0, 1, 2, 3, -1, -1], dtype=np.intp)
        elidx = np.array([0, 0, 1, 2, 3, 4], dtype=np.intp)

        tm.assert_index_equal(res, eres)
        tm.assert_numpy_array_equal(lidx, elidx)
        tm.assert_numpy_array_equal(ridx, eridx)

    def test_join_right(self, index_large):
        other = UInt64Index(2 ** 63 + np.array([7, 12, 25, 1, 2, 10], dtype="uint64"))
        other_mono = UInt64Index(
            2 ** 63 + np.array([1, 2, 7, 10, 12, 25], dtype="uint64")
        )

        # not monotonic
        res, lidx, ridx = index_large.join(other, how="right", return_indexers=True)
        eres = other
        elidx = np.array([-1, -1, 4, -1, -1, 1], dtype=np.intp)

        tm.assert_numpy_array_equal(lidx, elidx)
        assert isinstance(other, UInt64Index)
        tm.assert_index_equal(res, eres)
        assert ridx is None

        # monotonic
        res, lidx, ridx = index_large.join(
            other_mono, how="right", return_indexers=True
        )
        eres = other_mono
        elidx = np.array([-1, -1, -1, 1, -1, 4], dtype=np.intp)

        assert isinstance(other, UInt64Index)
        tm.assert_numpy_array_equal(lidx, elidx)
        tm.assert_index_equal(res, eres)
        assert ridx is None

        # non-unique
        idx = UInt64Index(2 ** 63 + np.array([1, 1, 2, 5], dtype="uint64"))
        idx2 = UInt64Index(2 ** 63 + np.array([1, 2, 5, 7, 9], dtype="uint64"))
        res, lidx, ridx = idx.join(idx2, how="right", return_indexers=True)

        # 1 is in idx2, so it should be x2
        eres = UInt64Index(2 ** 63 + np.array([1, 1, 2, 5, 7, 9], dtype="uint64"))
        elidx = np.array([0, 1, 2, 3, -1, -1], dtype=np.intp)
        eridx = np.array([0, 0, 1, 2, 3, 4], dtype=np.intp)

        tm.assert_index_equal(res, eres)
        tm.assert_numpy_array_equal(lidx, elidx)
        tm.assert_numpy_array_equal(ridx, eridx)

    def test_join_non_int_index(self, index_large):
        other = Index(
            2 ** 63 + np.array([1, 5, 7, 10, 20], dtype="uint64"), dtype=object
        )

        outer = index_large.join(other, how="outer")
        outer2 = other.join(index_large, how="outer")
        expected = Index(
            2 ** 63 + np.array([0, 1, 5, 7, 10, 15, 20, 25], dtype="uint64")
        )
        tm.assert_index_equal(outer, outer2)
        tm.assert_index_equal(outer, expected)

        inner = index_large.join(other, how="inner")
        inner2 = other.join(index_large, how="inner")
        expected = Index(2 ** 63 + np.array([10, 20], dtype="uint64"))
        tm.assert_index_equal(inner, inner2)
        tm.assert_index_equal(inner, expected)

        left = index_large.join(other, how="left")
        tm.assert_index_equal(left, index_large.astype(object))

        left2 = other.join(index_large, how="left")
        tm.assert_index_equal(left2, other)

        right = index_large.join(other, how="right")
        tm.assert_index_equal(right, other)

        right2 = other.join(index_large, how="right")
        tm.assert_index_equal(right2, index_large.astype(object))

    def test_join_outer(self, index_large):
        other = UInt64Index(2 ** 63 + np.array([7, 12, 25, 1, 2, 10], dtype="uint64"))
        other_mono = UInt64Index(
            2 ** 63 + np.array([1, 2, 7, 10, 12, 25], dtype="uint64")
        )

        # not monotonic
        # guarantee of sortedness
        res, lidx, ridx = index_large.join(other, how="outer", return_indexers=True)
        noidx_res = index_large.join(other, how="outer")
        tm.assert_index_equal(res, noidx_res)

        eres = UInt64Index(
            2 ** 63 + np.array([0, 1, 2, 7, 10, 12, 15, 20, 25], dtype="uint64")
        )
        elidx = np.array([0, -1, -1, -1, 1, -1, 2, 3, 4], dtype=np.intp)
        eridx = np.array([-1, 3, 4, 0, 5, 1, -1, -1, 2], dtype=np.intp)

        assert isinstance(res, UInt64Index)
        tm.assert_index_equal(res, eres)
        tm.assert_numpy_array_equal(lidx, elidx)
        tm.assert_numpy_array_equal(ridx, eridx)

        # monotonic
        res, lidx, ridx = index_large.join(
            other_mono, how="outer", return_indexers=True
        )
        noidx_res = index_large.join(other_mono, how="outer")
        tm.assert_index_equal(res, noidx_res)

        elidx = np.array([0, -1, -1, -1, 1, -1, 2, 3, 4], dtype=np.intp)
        eridx = np.array([-1, 0, 1, 2, 3, 4, -1, -1, 5], dtype=np.intp)

        assert isinstance(res, UInt64Index)
        tm.assert_index_equal(res, eres)
        tm.assert_numpy_array_equal(lidx, elidx)
        tm.assert_numpy_array_equal(ridx, eridx)


@pytest.mark.parametrize("dtype", ["int64", "uint64"])
def test_int_float_union_dtype(dtype):
    # https://github.com/pandas-dev/pandas/issues/26778
    # [u]int | float -> float
    index = pd.Index([0, 2, 3], dtype=dtype)
    other = pd.Float64Index([0.5, 1.5])
    expected = pd.Float64Index([0.0, 0.5, 1.5, 2.0, 3.0])
    result = index.union(other)
    tm.assert_index_equal(result, expected)

    result = other.union(index)
    tm.assert_index_equal(result, expected)


def test_range_float_union_dtype():
    # https://github.com/pandas-dev/pandas/issues/26778
    index = pd.RangeIndex(start=0, stop=3)
    other = pd.Float64Index([0.5, 1.5])
    result = index.union(other)
    expected = pd.Float64Index([0.0, 0.5, 1, 1.5, 2.0])
    tm.assert_index_equal(result, expected)

    result = other.union(index)
    tm.assert_index_equal(result, expected)


def test_uint_index_does_not_convert_to_float64():
    # https://github.com/pandas-dev/pandas/issues/28279
    # https://github.com/pandas-dev/pandas/issues/28023
    series = pd.Series(
        [0, 1, 2, 3, 4, 5],
        index=[
            7606741985629028552,
            17876870360202815256,
            17876870360202815256,
            13106359306506049338,
            8991270399732411471,
            8991270399732411472,
        ],
    )

    result = series.loc[[7606741985629028552, 17876870360202815256]]

    expected = UInt64Index(
        [7606741985629028552, 17876870360202815256, 17876870360202815256],
        dtype="uint64",
    )
    tm.assert_index_equal(result.index, expected)

    tm.assert_equal(result, series[:3])
