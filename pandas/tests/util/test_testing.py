# -*- coding: utf-8 -*-
import os
import sys
import textwrap

import numpy as np
import pytest

from pandas.compat import raise_with_traceback
import pandas.util._test_decorators as td

import pandas as pd
from pandas import DataFrame, Series, compat
import pandas.util.testing as tm
from pandas.util.testing import (
    RNGContext, assert_almost_equal, assert_frame_equal, assert_index_equal,
    assert_numpy_array_equal, assert_series_equal)


class TestAssertAlmostEqual(object):

    def _assert_almost_equal_both(self, a, b, **kwargs):
        assert_almost_equal(a, b, **kwargs)
        assert_almost_equal(b, a, **kwargs)

    def _assert_not_almost_equal_both(self, a, b, **kwargs):
        pytest.raises(AssertionError, assert_almost_equal, a, b, **kwargs)
        pytest.raises(AssertionError, assert_almost_equal, b, a, **kwargs)

    def test_assert_almost_equal_numbers(self):
        self._assert_almost_equal_both(1.1, 1.1)
        self._assert_almost_equal_both(1.1, 1.100001)
        self._assert_almost_equal_both(np.int16(1), 1.000001)
        self._assert_almost_equal_both(np.float64(1.1), 1.1)
        self._assert_almost_equal_both(np.uint32(5), 5)

        self._assert_not_almost_equal_both(1.1, 1)
        self._assert_not_almost_equal_both(1.1, True)
        self._assert_not_almost_equal_both(1, 2)
        self._assert_not_almost_equal_both(1.0001, np.int16(1))

    def test_assert_almost_equal_numbers_with_zeros(self):
        self._assert_almost_equal_both(0, 0)
        self._assert_almost_equal_both(0, 0.0)
        self._assert_almost_equal_both(0, np.float64(0))
        self._assert_almost_equal_both(0.000001, 0)

        self._assert_not_almost_equal_both(0.001, 0)
        self._assert_not_almost_equal_both(1, 0)

    def test_assert_almost_equal_numbers_with_mixed(self):
        self._assert_not_almost_equal_both(1, 'abc')
        self._assert_not_almost_equal_both(1, [1, ])
        self._assert_not_almost_equal_both(1, object())

    @pytest.mark.parametrize(
        "left_dtype",
        ['M8[ns]', 'm8[ns]', 'float64', 'int64', 'object'])
    @pytest.mark.parametrize(
        "right_dtype",
        ['M8[ns]', 'm8[ns]', 'float64', 'int64', 'object'])
    def test_assert_almost_equal_edge_case_ndarrays(
            self, left_dtype, right_dtype):

        # empty compare
        self._assert_almost_equal_both(np.array([], dtype=left_dtype),
                                       np.array([], dtype=right_dtype),
                                       check_dtype=False)

    def test_assert_almost_equal_dicts(self):
        self._assert_almost_equal_both({'a': 1, 'b': 2}, {'a': 1, 'b': 2})

        self._assert_not_almost_equal_both({'a': 1, 'b': 2}, {'a': 1, 'b': 3})
        self._assert_not_almost_equal_both({'a': 1, 'b': 2},
                                           {'a': 1, 'b': 2, 'c': 3})
        self._assert_not_almost_equal_both({'a': 1}, 1)
        self._assert_not_almost_equal_both({'a': 1}, 'abc')
        self._assert_not_almost_equal_both({'a': 1}, [1, ])

    def test_assert_almost_equal_dict_like_object(self):
        class DictLikeObj(object):

            def keys(self):
                return ('a', )

            def __getitem__(self, item):
                if item == 'a':
                    return 1

        self._assert_almost_equal_both({'a': 1}, DictLikeObj(),
                                       check_dtype=False)

        self._assert_not_almost_equal_both({'a': 2}, DictLikeObj(),
                                           check_dtype=False)

    def test_assert_almost_equal_strings(self):
        self._assert_almost_equal_both('abc', 'abc')

        self._assert_not_almost_equal_both('abc', 'abcd')
        self._assert_not_almost_equal_both('abc', 'abd')
        self._assert_not_almost_equal_both('abc', 1)
        self._assert_not_almost_equal_both('abc', [1, ])

    def test_assert_almost_equal_iterables(self):
        self._assert_almost_equal_both([1, 2, 3], [1, 2, 3])
        self._assert_almost_equal_both(np.array([1, 2, 3]),
                                       np.array([1, 2, 3]))

        # class / dtype are different
        self._assert_not_almost_equal_both(np.array([1, 2, 3]), [1, 2, 3])
        self._assert_not_almost_equal_both(np.array([1, 2, 3]),
                                           np.array([1., 2., 3.]))

        # Can't compare generators
        self._assert_not_almost_equal_both(iter([1, 2, 3]), [1, 2, 3])

        self._assert_not_almost_equal_both([1, 2, 3], [1, 2, 4])
        self._assert_not_almost_equal_both([1, 2, 3], [1, 2, 3, 4])
        self._assert_not_almost_equal_both([1, 2, 3], 1)

    def test_assert_almost_equal_null(self):
        self._assert_almost_equal_both(None, None)

        self._assert_not_almost_equal_both(None, np.NaN)
        self._assert_not_almost_equal_both(None, 0)
        self._assert_not_almost_equal_both(np.NaN, 0)

    def test_assert_almost_equal_inf(self):
        self._assert_almost_equal_both(np.inf, np.inf)
        self._assert_almost_equal_both(np.inf, float("inf"))
        self._assert_not_almost_equal_both(np.inf, 0)
        self._assert_almost_equal_both(np.array([np.inf, np.nan, -np.inf]),
                                       np.array([np.inf, np.nan, -np.inf]))
        self._assert_almost_equal_both(np.array([np.inf, None, -np.inf],
                                                dtype=np.object_),
                                       np.array([np.inf, np.nan, -np.inf],
                                                dtype=np.object_))

    def test_assert_almost_equal_pandas(self):
        tm.assert_almost_equal(pd.Index([1., 1.1]),
                               pd.Index([1., 1.100001]))
        tm.assert_almost_equal(pd.Series([1., 1.1]),
                               pd.Series([1., 1.100001]))
        tm.assert_almost_equal(pd.DataFrame({'a': [1., 1.1]}),
                               pd.DataFrame({'a': [1., 1.100001]}))

    def test_assert_almost_equal_object(self):
        a = [pd.Timestamp('2011-01-01'), pd.Timestamp('2011-01-01')]
        b = [pd.Timestamp('2011-01-01'), pd.Timestamp('2011-01-01')]
        self._assert_almost_equal_both(a, b)


class TestUtilTesting(object):

    def test_raise_with_traceback(self):
        with pytest.raises(LookupError, match="error_text"):
            try:
                raise ValueError("THIS IS AN ERROR")
            except ValueError as e:
                e = LookupError("error_text")
                raise_with_traceback(e)
        with pytest.raises(LookupError, match="error_text"):
            try:
                raise ValueError("This is another error")
            except ValueError:
                e = LookupError("error_text")
                _, _, traceback = sys.exc_info()
                raise_with_traceback(e, traceback)

    def test_convert_rows_list_to_csv_str(self):
        rows_list = ["aaa", "bbb", "ccc"]
        ret = tm.convert_rows_list_to_csv_str(rows_list)

        if compat.is_platform_windows():
            expected = "aaa\r\nbbb\r\nccc\r\n"
        else:
            expected = "aaa\nbbb\nccc\n"

        assert ret == expected


class TestAssertNumpyArrayEqual(object):

    @td.skip_if_windows
    def test_numpy_array_equal_message(self):

        expected = """numpy array are different

numpy array shapes are different
\\[left\\]:  \\(2,\\)
\\[right\\]: \\(3,\\)"""

        with pytest.raises(AssertionError, match=expected):
            assert_numpy_array_equal(np.array([1, 2]), np.array([3, 4, 5]))

        with pytest.raises(AssertionError, match=expected):
            assert_almost_equal(np.array([1, 2]), np.array([3, 4, 5]))

        # scalar comparison
        expected = """Expected type """
        with pytest.raises(AssertionError, match=expected):
            assert_numpy_array_equal(1, 2)
        expected = """expected 2\\.00000 but got 1\\.00000, with decimal 5"""
        with pytest.raises(AssertionError, match=expected):
            assert_almost_equal(1, 2)

        # array / scalar array comparison
        expected = """numpy array are different

numpy array classes are different
\\[left\\]:  ndarray
\\[right\\]: int"""

        with pytest.raises(AssertionError, match=expected):
            # numpy_array_equal only accepts np.ndarray
            assert_numpy_array_equal(np.array([1]), 1)
        with pytest.raises(AssertionError, match=expected):
            assert_almost_equal(np.array([1]), 1)

        # scalar / array comparison
        expected = """numpy array are different

numpy array classes are different
\\[left\\]:  int
\\[right\\]: ndarray"""

        with pytest.raises(AssertionError, match=expected):
            assert_numpy_array_equal(1, np.array([1]))
        with pytest.raises(AssertionError, match=expected):
            assert_almost_equal(1, np.array([1]))

        expected = """numpy array are different

numpy array values are different \\(66\\.66667 %\\)
\\[left\\]:  \\[nan, 2\\.0, 3\\.0\\]
\\[right\\]: \\[1\\.0, nan, 3\\.0\\]"""

        with pytest.raises(AssertionError, match=expected):
            assert_numpy_array_equal(np.array([np.nan, 2, 3]),
                                     np.array([1, np.nan, 3]))
        with pytest.raises(AssertionError, match=expected):
            assert_almost_equal(np.array([np.nan, 2, 3]),
                                np.array([1, np.nan, 3]))

        expected = """numpy array are different

numpy array values are different \\(50\\.0 %\\)
\\[left\\]:  \\[1, 2\\]
\\[right\\]: \\[1, 3\\]"""

        with pytest.raises(AssertionError, match=expected):
            assert_numpy_array_equal(np.array([1, 2]), np.array([1, 3]))
        with pytest.raises(AssertionError, match=expected):
            assert_almost_equal(np.array([1, 2]), np.array([1, 3]))

        expected = """numpy array are different

numpy array values are different \\(50\\.0 %\\)
\\[left\\]:  \\[1\\.1, 2\\.000001\\]
\\[right\\]: \\[1\\.1, 2.0\\]"""

        with pytest.raises(AssertionError, match=expected):
            assert_numpy_array_equal(
                np.array([1.1, 2.000001]), np.array([1.1, 2.0]))

        # must pass
        assert_almost_equal(np.array([1.1, 2.000001]), np.array([1.1, 2.0]))

        expected = """numpy array are different

numpy array values are different \\(16\\.66667 %\\)
\\[left\\]:  \\[\\[1, 2\\], \\[3, 4\\], \\[5, 6\\]\\]
\\[right\\]: \\[\\[1, 3\\], \\[3, 4\\], \\[5, 6\\]\\]"""

        with pytest.raises(AssertionError, match=expected):
            assert_numpy_array_equal(np.array([[1, 2], [3, 4], [5, 6]]),
                                     np.array([[1, 3], [3, 4], [5, 6]]))
        with pytest.raises(AssertionError, match=expected):
            assert_almost_equal(np.array([[1, 2], [3, 4], [5, 6]]),
                                np.array([[1, 3], [3, 4], [5, 6]]))

        expected = """numpy array are different

numpy array values are different \\(25\\.0 %\\)
\\[left\\]:  \\[\\[1, 2\\], \\[3, 4\\]\\]
\\[right\\]: \\[\\[1, 3\\], \\[3, 4\\]\\]"""

        with pytest.raises(AssertionError, match=expected):
            assert_numpy_array_equal(np.array([[1, 2], [3, 4]]),
                                     np.array([[1, 3], [3, 4]]))
        with pytest.raises(AssertionError, match=expected):
            assert_almost_equal(np.array([[1, 2], [3, 4]]),
                                np.array([[1, 3], [3, 4]]))

        # allow to overwrite message
        expected = """Index are different

Index shapes are different
\\[left\\]:  \\(2,\\)
\\[right\\]: \\(3,\\)"""

        with pytest.raises(AssertionError, match=expected):
            assert_numpy_array_equal(np.array([1, 2]), np.array([3, 4, 5]),
                                     obj='Index')
        with pytest.raises(AssertionError, match=expected):
            assert_almost_equal(np.array([1, 2]), np.array([3, 4, 5]),
                                obj='Index')

    def test_numpy_array_equal_unicode_message(self):
        # Test ensures that `assert_numpy_array_equals` raises the right
        # exception when comparing np.arrays containing differing
        # unicode objects (#20503)

        expected = """numpy array are different

numpy array values are different \\(33\\.33333 %\\)
\\[left\\]:  \\[á, à, ä\\]
\\[right\\]: \\[á, à, å\\]"""

        with pytest.raises(AssertionError, match=expected):
            assert_numpy_array_equal(np.array([u'á', u'à', u'ä']),
                                     np.array([u'á', u'à', u'å']))
        with pytest.raises(AssertionError, match=expected):
            assert_almost_equal(np.array([u'á', u'à', u'ä']),
                                np.array([u'á', u'à', u'å']))

    @td.skip_if_windows
    def test_numpy_array_equal_object_message(self):

        a = np.array([pd.Timestamp('2011-01-01'), pd.Timestamp('2011-01-01')])
        b = np.array([pd.Timestamp('2011-01-01'), pd.Timestamp('2011-01-02')])

        expected = """numpy array are different

numpy array values are different \\(50\\.0 %\\)
\\[left\\]:  \\[2011-01-01 00:00:00, 2011-01-01 00:00:00\\]
\\[right\\]: \\[2011-01-01 00:00:00, 2011-01-02 00:00:00\\]"""

        with pytest.raises(AssertionError, match=expected):
            assert_numpy_array_equal(a, b)
        with pytest.raises(AssertionError, match=expected):
            assert_almost_equal(a, b)

    def test_numpy_array_equal_copy_flag(self):
        a = np.array([1, 2, 3])
        b = a.copy()
        c = a.view()
        expected = r'array\(\[1, 2, 3\]\) is not array\(\[1, 2, 3\]\)'
        with pytest.raises(AssertionError, match=expected):
            assert_numpy_array_equal(a, b, check_same='same')
        expected = r'array\(\[1, 2, 3\]\) is array\(\[1, 2, 3\]\)'
        with pytest.raises(AssertionError, match=expected):
            assert_numpy_array_equal(a, c, check_same='copy')

    def test_assert_almost_equal_iterable_message(self):

        expected = """Iterable are different

Iterable length are different
\\[left\\]:  2
\\[right\\]: 3"""

        with pytest.raises(AssertionError, match=expected):
            assert_almost_equal([1, 2], [3, 4, 5])

        expected = """Iterable are different

Iterable values are different \\(50\\.0 %\\)
\\[left\\]:  \\[1, 2\\]
\\[right\\]: \\[1, 3\\]"""

        with pytest.raises(AssertionError, match=expected):
            assert_almost_equal([1, 2], [1, 3])


class TestAssertIndexEqual(object):

    def test_index_equal_message(self):

        expected = """Index are different

Index levels are different
\\[left\\]:  1, Int64Index\\(\\[1, 2, 3\\], dtype='int64'\\)
\\[right\\]: 2, MultiIndex\\(levels=\\[\\[u?'A', u?'B'\\], \\[1, 2, 3, 4\\]\\],
           labels=\\[\\[0, 0, 1, 1\\], \\[0, 1, 2, 3\\]\\]\\)"""

        idx1 = pd.Index([1, 2, 3])
        idx2 = pd.MultiIndex.from_tuples([('A', 1), ('A', 2),
                                          ('B', 3), ('B', 4)])
        with pytest.raises(AssertionError, match=expected):
            assert_index_equal(idx1, idx2, exact=False)

        expected = """MultiIndex level \\[1\\] are different

MultiIndex level \\[1\\] values are different \\(25\\.0 %\\)
\\[left\\]:  Int64Index\\(\\[2, 2, 3, 4\\], dtype='int64'\\)
\\[right\\]: Int64Index\\(\\[1, 2, 3, 4\\], dtype='int64'\\)"""

        idx1 = pd.MultiIndex.from_tuples([('A', 2), ('A', 2),
                                          ('B', 3), ('B', 4)])
        idx2 = pd.MultiIndex.from_tuples([('A', 1), ('A', 2),
                                          ('B', 3), ('B', 4)])
        with pytest.raises(AssertionError, match=expected):
            assert_index_equal(idx1, idx2)
        with pytest.raises(AssertionError, match=expected):
            assert_index_equal(idx1, idx2, check_exact=False)

        expected = """Index are different

Index length are different
\\[left\\]:  3, Int64Index\\(\\[1, 2, 3\\], dtype='int64'\\)
\\[right\\]: 4, Int64Index\\(\\[1, 2, 3, 4\\], dtype='int64'\\)"""

        idx1 = pd.Index([1, 2, 3])
        idx2 = pd.Index([1, 2, 3, 4])
        with pytest.raises(AssertionError, match=expected):
            assert_index_equal(idx1, idx2)
        with pytest.raises(AssertionError, match=expected):
            assert_index_equal(idx1, idx2, check_exact=False)

        expected = """Index are different

Index classes are different
\\[left\\]:  Int64Index\\(\\[1, 2, 3\\], dtype='int64'\\)
\\[right\\]: Float64Index\\(\\[1\\.0, 2\\.0, 3\\.0\\], dtype='float64'\\)"""

        idx1 = pd.Index([1, 2, 3])
        idx2 = pd.Index([1, 2, 3.0])
        with pytest.raises(AssertionError, match=expected):
            assert_index_equal(idx1, idx2, exact=True)
        with pytest.raises(AssertionError, match=expected):
            assert_index_equal(idx1, idx2, exact=True, check_exact=False)

        expected = """Index are different

Index values are different \\(33\\.33333 %\\)
\\[left\\]:  Float64Index\\(\\[1.0, 2.0, 3.0], dtype='float64'\\)
\\[right\\]: Float64Index\\(\\[1.0, 2.0, 3.0000000001\\], dtype='float64'\\)"""

        idx1 = pd.Index([1, 2, 3.])
        idx2 = pd.Index([1, 2, 3.0000000001])
        with pytest.raises(AssertionError, match=expected):
            assert_index_equal(idx1, idx2)

        # must success
        assert_index_equal(idx1, idx2, check_exact=False)

        expected = """Index are different

Index values are different \\(33\\.33333 %\\)
\\[left\\]:  Float64Index\\(\\[1.0, 2.0, 3.0], dtype='float64'\\)
\\[right\\]: Float64Index\\(\\[1.0, 2.0, 3.0001\\], dtype='float64'\\)"""

        idx1 = pd.Index([1, 2, 3.])
        idx2 = pd.Index([1, 2, 3.0001])
        with pytest.raises(AssertionError, match=expected):
            assert_index_equal(idx1, idx2)
        with pytest.raises(AssertionError, match=expected):
            assert_index_equal(idx1, idx2, check_exact=False)
        # must success
        assert_index_equal(idx1, idx2, check_exact=False,
                           check_less_precise=True)

        expected = """Index are different

Index values are different \\(33\\.33333 %\\)
\\[left\\]:  Int64Index\\(\\[1, 2, 3\\], dtype='int64'\\)
\\[right\\]: Int64Index\\(\\[1, 2, 4\\], dtype='int64'\\)"""

        idx1 = pd.Index([1, 2, 3])
        idx2 = pd.Index([1, 2, 4])
        with pytest.raises(AssertionError, match=expected):
            assert_index_equal(idx1, idx2)
        with pytest.raises(AssertionError, match=expected):
            assert_index_equal(idx1, idx2, check_less_precise=True)

        expected = """MultiIndex level \\[1\\] are different

MultiIndex level \\[1\\] values are different \\(25\\.0 %\\)
\\[left\\]:  Int64Index\\(\\[2, 2, 3, 4\\], dtype='int64'\\)
\\[right\\]: Int64Index\\(\\[1, 2, 3, 4\\], dtype='int64'\\)"""

        idx1 = pd.MultiIndex.from_tuples([('A', 2), ('A', 2),
                                          ('B', 3), ('B', 4)])
        idx2 = pd.MultiIndex.from_tuples([('A', 1), ('A', 2),
                                          ('B', 3), ('B', 4)])
        with pytest.raises(AssertionError, match=expected):
            assert_index_equal(idx1, idx2)
        with pytest.raises(AssertionError, match=expected):
            assert_index_equal(idx1, idx2, check_exact=False)

    def test_index_equal_metadata_message(self):

        expected = """Index are different

Attribute "names" are different
\\[left\\]:  \\[None\\]
\\[right\\]: \\[u?'x'\\]"""

        idx1 = pd.Index([1, 2, 3])
        idx2 = pd.Index([1, 2, 3], name='x')
        with pytest.raises(AssertionError, match=expected):
            assert_index_equal(idx1, idx2)

        # same name, should pass
        assert_index_equal(pd.Index([1, 2, 3], name=np.nan),
                           pd.Index([1, 2, 3], name=np.nan))
        assert_index_equal(pd.Index([1, 2, 3], name=pd.NaT),
                           pd.Index([1, 2, 3], name=pd.NaT))

        expected = """Index are different

Attribute "names" are different
\\[left\\]:  \\[nan\\]
\\[right\\]: \\[NaT\\]"""

        idx1 = pd.Index([1, 2, 3], name=np.nan)
        idx2 = pd.Index([1, 2, 3], name=pd.NaT)
        with pytest.raises(AssertionError, match=expected):
            assert_index_equal(idx1, idx2)

    def test_categorical_index_equality(self):
        expected = """Index are different

Attribute "dtype" are different
\\[left\\]:  CategoricalDtype\\(categories=\\[u?'a', u?'b'\\], ordered=False\\)
\\[right\\]: CategoricalDtype\\(categories=\\[u?'a', u?'b', u?'c'\\], \
ordered=False\\)"""

        with pytest.raises(AssertionError, match=expected):
            assert_index_equal(pd.Index(pd.Categorical(['a', 'b'])),
                               pd.Index(pd.Categorical(['a', 'b'],
                                        categories=['a', 'b', 'c'])))

    def test_categorical_index_equality_relax_categories_check(self):
        assert_index_equal(pd.Index(pd.Categorical(['a', 'b'])),
                           pd.Index(pd.Categorical(['a', 'b'],
                                    categories=['a', 'b', 'c'])),
                           check_categorical=False)


class TestAssertSeriesEqual(object):

    def _assert_equal(self, x, y, **kwargs):
        assert_series_equal(x, y, **kwargs)
        assert_series_equal(y, x, **kwargs)

    def _assert_not_equal(self, a, b, **kwargs):
        pytest.raises(AssertionError, assert_series_equal, a, b, **kwargs)
        pytest.raises(AssertionError, assert_series_equal, b, a, **kwargs)

    def test_equal(self):
        self._assert_equal(Series(range(3)), Series(range(3)))
        self._assert_equal(Series(list('abc')), Series(list('abc')))
        self._assert_equal(Series(list(u'áàä')), Series(list(u'áàä')))

    def test_not_equal(self):
        self._assert_not_equal(Series(range(3)), Series(range(3)) + 1)
        self._assert_not_equal(Series(list('abc')), Series(list('xyz')))
        self._assert_not_equal(Series(list(u'áàä')), Series(list(u'éèë')))
        self._assert_not_equal(Series(list(u'áàä')), Series(list(b'aaa')))
        self._assert_not_equal(Series(range(3)), Series(range(4)))
        self._assert_not_equal(
            Series(range(3)), Series(
                range(3), dtype='float64'))
        self._assert_not_equal(
            Series(range(3)), Series(
                range(3), index=[1, 2, 4]))

        # ATM meta data is not checked in assert_series_equal
        # self._assert_not_equal(Series(range(3)),Series(range(3),name='foo'),check_names=True)

    def test_less_precise(self):
        s1 = Series([0.12345], dtype='float64')
        s2 = Series([0.12346], dtype='float64')

        pytest.raises(AssertionError, assert_series_equal, s1, s2)
        self._assert_equal(s1, s2, check_less_precise=True)
        for i in range(4):
            self._assert_equal(s1, s2, check_less_precise=i)
        pytest.raises(AssertionError, assert_series_equal, s1, s2, 10)

        s1 = Series([0.12345], dtype='float32')
        s2 = Series([0.12346], dtype='float32')

        pytest.raises(AssertionError, assert_series_equal, s1, s2)
        self._assert_equal(s1, s2, check_less_precise=True)
        for i in range(4):
            self._assert_equal(s1, s2, check_less_precise=i)
        pytest.raises(AssertionError, assert_series_equal, s1, s2, 10)

        # even less than less precise
        s1 = Series([0.1235], dtype='float32')
        s2 = Series([0.1236], dtype='float32')

        pytest.raises(AssertionError, assert_series_equal, s1, s2)
        pytest.raises(AssertionError, assert_series_equal, s1, s2, True)

    def test_index_dtype(self):
        df1 = DataFrame.from_records(
            {'a': [1, 2], 'c': ['l1', 'l2']}, index=['a'])
        df2 = DataFrame.from_records(
            {'a': [1.0, 2.0], 'c': ['l1', 'l2']}, index=['a'])
        self._assert_not_equal(df1.c, df2.c, check_index_type=True)

    def test_multiindex_dtype(self):
        df1 = DataFrame.from_records(
            {'a': [1, 2], 'b': [2.1, 1.5],
             'c': ['l1', 'l2']}, index=['a', 'b'])
        df2 = DataFrame.from_records(
            {'a': [1.0, 2.0], 'b': [2.1, 1.5],
             'c': ['l1', 'l2']}, index=['a', 'b'])
        self._assert_not_equal(df1.c, df2.c, check_index_type=True)

    def test_series_equal_message(self):

        expected = """Series are different

Series length are different
\\[left\\]:  3, RangeIndex\\(start=0, stop=3, step=1\\)
\\[right\\]: 4, RangeIndex\\(start=0, stop=4, step=1\\)"""

        with pytest.raises(AssertionError, match=expected):
            assert_series_equal(pd.Series([1, 2, 3]), pd.Series([1, 2, 3, 4]))

        expected = """Series are different

Series values are different \\(33\\.33333 %\\)
\\[left\\]:  \\[1, 2, 3\\]
\\[right\\]: \\[1, 2, 4\\]"""

        with pytest.raises(AssertionError, match=expected):
            assert_series_equal(pd.Series([1, 2, 3]), pd.Series([1, 2, 4]))
        with pytest.raises(AssertionError, match=expected):
            assert_series_equal(pd.Series([1, 2, 3]), pd.Series([1, 2, 4]),
                                check_less_precise=True)

    def test_categorical_series_equality(self):
        expected = """Attributes are different

Attribute "dtype" are different
\\[left\\]:  CategoricalDtype\\(categories=\\[u?'a', u?'b'\\], ordered=False\\)
\\[right\\]: CategoricalDtype\\(categories=\\[u?'a', u?'b', u?'c'\\], \
ordered=False\\)"""

        with pytest.raises(AssertionError, match=expected):
            assert_series_equal(pd.Series(pd.Categorical(['a', 'b'])),
                                pd.Series(pd.Categorical(['a', 'b'],
                                          categories=['a', 'b', 'c'])))

    def test_categorical_series_equality_relax_categories_check(self):
        assert_series_equal(pd.Series(pd.Categorical(['a', 'b'])),
                            pd.Series(pd.Categorical(['a', 'b'],
                                      categories=['a', 'b', 'c'])),
                            check_categorical=False)


class TestAssertFrameEqual(object):

    def _assert_equal(self, x, y, **kwargs):
        assert_frame_equal(x, y, **kwargs)
        assert_frame_equal(y, x, **kwargs)

    def _assert_not_equal(self, a, b, **kwargs):
        pytest.raises(AssertionError, assert_frame_equal, a, b, **kwargs)
        pytest.raises(AssertionError, assert_frame_equal, b, a, **kwargs)

    def test_equal_with_different_row_order(self):
        # check_like=True ignores row-column orderings
        df1 = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]},
                           index=['a', 'b', 'c'])
        df2 = pd.DataFrame({'A': [3, 2, 1], 'B': [6, 5, 4]},
                           index=['c', 'b', 'a'])

        self._assert_equal(df1, df2, check_like=True)
        self._assert_not_equal(df1, df2)

    def test_not_equal_with_different_shape(self):
        self._assert_not_equal(pd.DataFrame({'A': [1, 2, 3]}),
                               pd.DataFrame({'A': [1, 2, 3, 4]}))

    def test_index_dtype(self):
        df1 = DataFrame.from_records(
            {'a': [1, 2], 'c': ['l1', 'l2']}, index=['a'])
        df2 = DataFrame.from_records(
            {'a': [1.0, 2.0], 'c': ['l1', 'l2']}, index=['a'])
        self._assert_not_equal(df1, df2, check_index_type=True)

    def test_multiindex_dtype(self):
        df1 = DataFrame.from_records(
            {'a': [1, 2], 'b': [2.1, 1.5],
             'c': ['l1', 'l2']}, index=['a', 'b'])
        df2 = DataFrame.from_records(
            {'a': [1.0, 2.0], 'b': [2.1, 1.5],
             'c': ['l1', 'l2']}, index=['a', 'b'])
        self._assert_not_equal(df1, df2, check_index_type=True)

    def test_empty_dtypes(self):
        df1 = pd.DataFrame(columns=["col1", "col2"])
        df1["col1"] = df1["col1"].astype('int64')
        df2 = pd.DataFrame(columns=["col1", "col2"])
        self._assert_equal(df1, df2, check_dtype=False)
        self._assert_not_equal(df1, df2, check_dtype=True)

    def test_frame_equal_message(self):

        expected = """DataFrame are different

DataFrame shape mismatch
\\[left\\]:  \\(3, 2\\)
\\[right\\]: \\(3, 1\\)"""

        with pytest.raises(AssertionError, match=expected):
            assert_frame_equal(pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]}),
                               pd.DataFrame({'A': [1, 2, 3]}))

        expected = """DataFrame\\.index are different

DataFrame\\.index values are different \\(33\\.33333 %\\)
\\[left\\]:  Index\\(\\[u?'a', u?'b', u?'c'\\], dtype='object'\\)
\\[right\\]: Index\\(\\[u?'a', u?'b', u?'d'\\], dtype='object'\\)"""

        with pytest.raises(AssertionError, match=expected):
            assert_frame_equal(pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]},
                                            index=['a', 'b', 'c']),
                               pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]},
                                            index=['a', 'b', 'd']))

        expected = """DataFrame\\.columns are different

DataFrame\\.columns values are different \\(50\\.0 %\\)
\\[left\\]:  Index\\(\\[u?'A', u?'B'\\], dtype='object'\\)
\\[right\\]: Index\\(\\[u?'A', u?'b'\\], dtype='object'\\)"""

        with pytest.raises(AssertionError, match=expected):
            assert_frame_equal(pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]},
                                            index=['a', 'b', 'c']),
                               pd.DataFrame({'A': [1, 2, 3], 'b': [4, 5, 6]},
                                            index=['a', 'b', 'c']))

        expected = """DataFrame\\.iloc\\[:, 1\\] are different

DataFrame\\.iloc\\[:, 1\\] values are different \\(33\\.33333 %\\)
\\[left\\]:  \\[4, 5, 6\\]
\\[right\\]: \\[4, 5, 7\\]"""

        with pytest.raises(AssertionError, match=expected):
            assert_frame_equal(pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]}),
                               pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 7]}))

        with pytest.raises(AssertionError, match=expected):
            assert_frame_equal(pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]}),
                               pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 7]}),
                               by_blocks=True)

    def test_frame_equal_message_unicode(self):
        # Test ensures that `assert_frame_equals` raises the right
        # exception when comparing DataFrames containing differing
        # unicode objects (#20503)

        expected = """DataFrame\\.iloc\\[:, 1\\] are different

DataFrame\\.iloc\\[:, 1\\] values are different \\(33\\.33333 %\\)
\\[left\\]:  \\[é, è, ë\\]
\\[right\\]: \\[é, è, e̊\\]"""

        with pytest.raises(AssertionError, match=expected):
            assert_frame_equal(pd.DataFrame({'A': [u'á', u'à', u'ä'],
                                             'E': [u'é', u'è', u'ë']}),
                               pd.DataFrame({'A': [u'á', u'à', u'ä'],
                                             'E': [u'é', u'è', u'e̊']}))

        with pytest.raises(AssertionError, match=expected):
            assert_frame_equal(pd.DataFrame({'A': [u'á', u'à', u'ä'],
                                             'E': [u'é', u'è', u'ë']}),
                               pd.DataFrame({'A': [u'á', u'à', u'ä'],
                                             'E': [u'é', u'è', u'e̊']}),
                               by_blocks=True)

        expected = """DataFrame\\.iloc\\[:, 0\\] are different

DataFrame\\.iloc\\[:, 0\\] values are different \\(100\\.0 %\\)
\\[left\\]:  \\[á, à, ä\\]
\\[right\\]: \\[a, a, a\\]"""

        with pytest.raises(AssertionError, match=expected):
            assert_frame_equal(pd.DataFrame({'A': [u'á', u'à', u'ä'],
                                             'E': [u'é', u'è', u'ë']}),
                               pd.DataFrame({'A': ['a', 'a', 'a'],
                                             'E': ['e', 'e', 'e']}))

        with pytest.raises(AssertionError, match=expected):
            assert_frame_equal(pd.DataFrame({'A': [u'á', u'à', u'ä'],
                                             'E': [u'é', u'è', u'ë']}),
                               pd.DataFrame({'A': ['a', 'a', 'a'],
                                             'E': ['e', 'e', 'e']}),
                               by_blocks=True)


class TestAssertCategoricalEqual(object):

    def test_categorical_equal_message(self):

        expected = """Categorical\\.categories are different

Categorical\\.categories values are different \\(25\\.0 %\\)
\\[left\\]:  Int64Index\\(\\[1, 2, 3, 4\\], dtype='int64'\\)
\\[right\\]: Int64Index\\(\\[1, 2, 3, 5\\], dtype='int64'\\)"""

        a = pd.Categorical([1, 2, 3, 4])
        b = pd.Categorical([1, 2, 3, 5])
        with pytest.raises(AssertionError, match=expected):
            tm.assert_categorical_equal(a, b)

        expected = """Categorical\\.codes are different

Categorical\\.codes values are different \\(50\\.0 %\\)
\\[left\\]:  \\[0, 1, 3, 2\\]
\\[right\\]: \\[0, 1, 2, 3\\]"""

        a = pd.Categorical([1, 2, 4, 3], categories=[1, 2, 3, 4])
        b = pd.Categorical([1, 2, 3, 4], categories=[1, 2, 3, 4])
        with pytest.raises(AssertionError, match=expected):
            tm.assert_categorical_equal(a, b)

        expected = """Categorical are different

Attribute "ordered" are different
\\[left\\]:  False
\\[right\\]: True"""

        a = pd.Categorical([1, 2, 3, 4], ordered=False)
        b = pd.Categorical([1, 2, 3, 4], ordered=True)
        with pytest.raises(AssertionError, match=expected):
            tm.assert_categorical_equal(a, b)


class TestAssertIntervalArrayEqual(object):
    def test_interval_array_equal_message(self):
        a = pd.interval_range(0, periods=4).values
        b = pd.interval_range(1, periods=4).values

        msg = textwrap.dedent("""\
            IntervalArray.left are different

            IntervalArray.left values are different \\(100.0 %\\)
            \\[left\\]:  Int64Index\\(\\[0, 1, 2, 3\\], dtype='int64'\\)
            \\[right\\]: Int64Index\\(\\[1, 2, 3, 4\\], dtype='int64'\\)""")
        with pytest.raises(AssertionError, match=msg):
            tm.assert_interval_array_equal(a, b)


class TestRNGContext(object):

    def test_RNGContext(self):
        expected0 = 1.764052345967664
        expected1 = 1.6243453636632417

        with RNGContext(0):
            with RNGContext(1):
                assert np.random.randn() == expected1
            assert np.random.randn() == expected0


def test_datapath_missing(datapath, request):
    if not request.config.getoption("--strict-data-files"):
        pytest.skip("Need to set '--strict-data-files'")

    with pytest.raises(ValueError):
        datapath('not_a_file')

    result = datapath('data', 'iris.csv')
    expected = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'data',
        'iris.csv'
    )

    assert result == expected


def test_create_temp_directory():
    with tm.ensure_clean_dir() as path:
        assert os.path.exists(path)
        assert os.path.isdir(path)
    assert not os.path.exists(path)


def test_assert_raises_regex_deprecated():
    # see gh-23592

    with tm.assert_produces_warning(FutureWarning):
        msg = "Not equal!"

        with tm.assert_raises_regex(AssertionError, msg):
            assert 1 == 2, msg
