# pylint: disable-msg=E1101,W0612

from unittest import TestCase
import operator

from numpy import nan
import numpy as np

from pandas.util.testing import (assert_almost_equal, assert_series_equal,
                                 assert_frame_equal)
from numpy.testing import assert_equal

from pandas import DataFrame, DateRange
from pandas.core.datetools import BDay
from pandas.core.series import remove_na
from pandas.core.sparse import (IntIndex, BlockIndex,
                                SparseSeries, SparseDataFrame)
import pandas.core.sparse as spm
import pandas.util.testing as testing

"""
Testing TODO


"""
def _test_data1():
    # nan-based
    arr = np.arange(20, dtype=float)
    index = np.arange(20)
    arr[:2] = nan
    arr[5:10] = nan
    arr[-3:] = nan

    return arr, index

def _test_data2():
    # nan-based
    arr = np.arange(15, dtype=float)
    index = np.arange(15)
    arr[7:12] = nan
    arr[-1:] = nan
    return arr, index

def _test_data1_zero():
    # zero-based
    arr, index = _test_data1()
    arr[np.isnan(arr)] = 0
    return arr, index

def _test_data2_zero():
    # zero-based
    arr, index = _test_data2()
    arr[np.isnan(arr)] = 0
    return arr, index

def assert_sp_series_equal(a, b):
    assert_equal(a.sp_values, b.sp_values)
    assert(a.sp_index.equals(b.sp_index))
    if np.isnan(a.fill_value):
        assert(np.isnan(b.fill_value))
    else:
        assert(a.fill_value == b.fill_value)

def assert_sp_frame_equal(left, right, exact_indices=True):
    """
    exact: Series SparseIndex objects must be exactly the same, otherwise just
    compare dense representations
    """
    for col, series in left.iteritems():
        assert(col in right)
        # trade-off?

        if exact_indices:
            assert_sp_series_equal(series, right[col])
        else:
            assert_series_equal(series.to_dense(), right[col].to_dense())

    for col in right:
        assert(col in left)

class TestSparseSeries(TestCase):

    def setUp(self):
        arr, index = _test_data1()

        date_index = DateRange('1/1/2011', periods=len(index))

        self.bseries = SparseSeries(arr, index=index, kind='block')
        self.btseries = SparseSeries(arr, index=date_index, kind='block')

        self.iseries = SparseSeries(arr, index=index, kind='integer')

        arr, index = _test_data2()
        self.bseries2 = SparseSeries(arr, index=index, kind='block')
        self.iseries2 = SparseSeries(arr, index=index, kind='integer')

        arr, index = _test_data1_zero()
        self.zbseries = SparseSeries(arr, index=index, kind='block',
                                     fill_value=0)
        self.ziseries = SparseSeries(arr, index=index, kind='integer',
                                     fill_value=0)

        arr, index = _test_data2_zero()
        self.zbseries2 = SparseSeries(arr, index=index, kind='block',
                                      fill_value=0)
        self.ziseries2 = SparseSeries(arr, index=index, kind='integer',
                                      fill_value=0)

    def test_sparse_to_dense(self):
        arr, index = _test_data1()
        series = self.bseries.to_dense()
        assert_equal(series, arr)

        series = self.bseries.to_dense(sparse_only=True)
        assert_equal(series, arr[np.isfinite(arr)])

        series = self.iseries.to_dense()
        assert_equal(series, arr)

        arr, index = _test_data1_zero()
        series = self.zbseries.to_dense()
        assert_equal(series, arr)

        series = self.ziseries.to_dense()
        assert_equal(series, arr)

    def test_dense_to_sparse(self):
        series = self.bseries.to_dense()
        bseries = series.to_sparse(kind='block')
        iseries = series.to_sparse(kind='integer')
        assert_sp_series_equal(bseries, self.bseries)
        assert_sp_series_equal(iseries, self.iseries)

        # non-NaN fill value
        series = self.zbseries.to_dense()
        zbseries = series.to_sparse(kind='block', fill_value=0)
        ziseries = series.to_sparse(kind='integer', fill_value=0)
        assert_sp_series_equal(zbseries, self.zbseries)
        assert_sp_series_equal(ziseries, self.ziseries)

    def test_constructor(self):
        # test setup guys
        self.assert_(np.isnan(self.bseries.fill_value))
        self.assert_(isinstance(self.bseries.sp_index, BlockIndex))
        self.assert_(np.isnan(self.iseries.fill_value))
        self.assert_(isinstance(self.iseries.sp_index, IntIndex))

        self.assertEquals(self.zbseries.fill_value, 0)
        assert_equal(self.zbseries.values, self.bseries.to_dense().fillna(0))

        # pass SparseSeries
        s2 = SparseSeries(self.bseries)
        s3 = SparseSeries(self.iseries)
        s4 = SparseSeries(self.zbseries)
        assert_sp_series_equal(s2, self.bseries)
        assert_sp_series_equal(s3, self.iseries)
        assert_sp_series_equal(s4, self.zbseries)

        # Sparse time series works
        date_index = DateRange('1/1/2000', periods=len(self.bseries))
        s5 = SparseSeries(self.bseries, index=date_index)
        self.assert_(isinstance(s5, spm.SparseTimeSeries))

        # pass Series
        bseries2 = SparseSeries(self.bseries.to_dense())
        assert_equal(self.bseries.sp_values, bseries2.sp_values)

        # pass dict

        # don't copy the data by default
        values = np.ones(len(self.bseries.sp_values))
        sp = SparseSeries(values, sparse_index=self.bseries.sp_index)
        sp.sp_values[:5] = 97
        self.assert_(values[0] == 97)

        # but can make it copy!
        sp = SparseSeries(values, sparse_index=self.bseries.sp_index,
                          copy=True)
        sp.sp_values[:5] = 100
        self.assert_(values[0] == 97)

    def test_constructor_nonnan(self):
        arr = [0, 0, 0, nan, nan]
        sp_series = SparseSeries(arr, fill_value=0)
        assert_equal(sp_series.values, arr)

    def test_copy_astype(self):
        cop = self.bseries.astype(np.int32)
        self.assert_(cop is not self.bseries)
        self.assert_(cop.sp_index is self.bseries.sp_index)
        self.assert_(cop.dtype == np.float64)

        cop2 = self.iseries.copy()

        assert_sp_series_equal(cop, self.bseries)
        assert_sp_series_equal(cop2, self.iseries)

        # test that data is copied
        cop.sp_values[:5] = 97
        self.assert_(cop.sp_values[0] == 97)
        self.assert_(self.bseries.sp_values[0] != 97)

    def test_kind(self):
        self.assertEquals(self.bseries.kind, 'block')
        self.assertEquals(self.iseries.kind, 'integer')

    def test_pickle(self):
        import pickle

        def _test_roundtrip(series):
            pickled = pickle.dumps(series)
            unpickled = pickle.loads(pickled)
            assert_sp_series_equal(series, unpickled)
            assert_series_equal(series.to_dense(), unpickled.to_dense())

        _test_roundtrip(self.bseries)
        _test_roundtrip(self.iseries)
        _test_roundtrip(self.zbseries)
        _test_roundtrip(self.ziseries)

    def test_getitem(self):
        def _check_getitem(sp, dense):
            for idx, val in dense.iteritems():
                assert_almost_equal(val, sp[idx])

            for i in xrange(len(dense)):
                assert_almost_equal(sp[i], dense[i])

            # negative getitem works
            for i in xrange(len(dense)):
                assert_almost_equal(sp[-i], dense[-i])

        _check_getitem(self.bseries, self.bseries.to_dense())
        _check_getitem(self.btseries, self.btseries.to_dense())

        _check_getitem(self.zbseries, self.zbseries.to_dense())
        _check_getitem(self.iseries, self.iseries.to_dense())
        _check_getitem(self.ziseries, self.ziseries.to_dense())

        # exception handling
        self.assertRaises(Exception, self.bseries.__getitem__,
                          len(self.bseries) + 1)

        # index not contained
        self.assertRaises(Exception, self.btseries.__getitem__,
                          self.btseries.index[-1] + BDay())

    def test_get(self):
        assert_almost_equal(self.bseries.get(10), self.bseries[10])
        self.assert_(self.bseries.get(len(self.bseries) + 1) is None)

    def test_getitem_fancy_index(self):
        idx = self.bseries.index
        res = self.bseries[::2]
        self.assert_(isinstance(res, SparseSeries))
        assert_sp_series_equal(res, self.bseries.reindex(idx[::2]))

        res = self.bseries[:5]
        self.assert_(isinstance(res, SparseSeries))
        assert_sp_series_equal(res, self.bseries.reindex(idx[:5]))

        res = self.bseries[5:]
        assert_sp_series_equal(res, self.bseries.reindex(idx[5:]))

    def test_getslice(self):
        pass

    def test_setitem(self):
        self.assertRaises(Exception, self.bseries.__setitem__, 5, 7.)
        self.assertRaises(Exception, self.iseries.__setitem__, 5, 7.)

    def test_setslice(self):
        self.assertRaises(Exception, lambda: eval('self.bseries[5:10] = 10'))

    def test_operators(self):
        def _check_op(a, b, op):
            sp_result = op(a, b)
            adense = a.to_dense() if isinstance(a, SparseSeries) else a
            bdense = b.to_dense() if isinstance(b, SparseSeries) else b
            dense_result = op(adense, bdense)
            assert_almost_equal(sp_result.to_dense(), dense_result)

        def check(a, b):
            _check_op(a, b, operator.add)
            _check_op(a, b, operator.sub)
            _check_op(a, b, operator.div)
            _check_op(a, b, operator.mul)

            _check_op(a, b, lambda x, y: operator.add(y, x))
            _check_op(a, b, lambda x, y: operator.sub(y, x))
            _check_op(a, b, lambda x, y: operator.div(y, x))
            _check_op(a, b, lambda x, y: operator.mul(y, x))

            # NaN ** 0 = 1 in C?
            # _check_op(a, b, operator.pow)
            # _check_op(a, b, lambda x, y: operator.pow(y, x))

        check(self.bseries, self.bseries)
        check(self.iseries, self.iseries)
        check(self.bseries, self.iseries)

        check(self.bseries, self.bseries2)
        check(self.bseries, self.iseries2)
        check(self.iseries, self.iseries2)

        # scalar value
        check(self.bseries, 5)

        # zero-based
        check(self.zbseries, self.zbseries * 2)
        check(self.zbseries, self.zbseries2)
        check(self.ziseries, self.ziseries2)

    def test_reindex(self):
        def _compare_with_series(sps, new_index):
            spsre = sps.reindex(new_index)

            series = sps.to_dense()
            seriesre = series.reindex(new_index)
            seriesre = seriesre.to_sparse(fill_value=sps.fill_value)

            assert_sp_series_equal(spsre, seriesre)
            assert_series_equal(spsre.to_dense(), seriesre.to_dense())

        _compare_with_series(self.bseries, self.bseries.index[::2])
        _compare_with_series(self.bseries, list(self.bseries.index[::2]))
        _compare_with_series(self.bseries, self.bseries.index[:10])
        _compare_with_series(self.bseries, self.bseries.index[5:])

        _compare_with_series(self.zbseries, self.zbseries.index[::2])
        _compare_with_series(self.zbseries, self.zbseries.index[:10])
        _compare_with_series(self.zbseries, self.zbseries.index[5:])

        # special cases
        same_index = self.bseries.reindex(self.bseries.index)
        assert_sp_series_equal(self.bseries, same_index)
        self.assert_(same_index is not self.bseries)

        # corner cases
        sp = SparseSeries([], index=[])
        sp_zero = SparseSeries([], index=[], fill_value=0)
        _compare_with_series(sp, np.arange(10))

    def test_repr(self):
        pass

    def test_iter(self):
        pass

    def test_truncate(self):
        pass

    def test_fillna(self):
        pass

    def test_groupby(self):
        pass

    def test_reductions(self):
        def _compare_with_series(obj, op):
            sparse_result = getattr(obj, op)()
            series = obj.to_dense()
            dense_result = getattr(series, op)()
            self.assertEquals(sparse_result, dense_result)

        to_compare = ['count', 'sum', 'mean', 'std', 'var', 'skew']
        def _compare_all(obj):
            for op in to_compare:
                _compare_with_series(obj, op)

        _compare_all(self.bseries)
        self.bseries.sp_values[5:10] = np.NaN
        _compare_all(self.bseries)

        _compare_all(self.zbseries)
        self.zbseries.sp_values[5:10] = np.NaN
        _compare_all(self.zbseries)

        series = self.zbseries.copy()
        series.fill_value = 2
        _compare_all(series)

    def test_mean(self):
        pass

    def test_valid(self):
        pass

class TestSparseTimeSeries(TestCase):
    pass

class TestSparseDataFrame(TestCase):
    klass = SparseDataFrame

    def setUp(self):
        self.data = {'A' : [nan, nan, nan, 0, 1, 2, 3, 4, 5, 6],
                     'B' : [0, 1, 2, nan, nan, nan, 3, 4, 5, 6],
                     'C' : np.arange(10),
                     'D' : [0, 1, 2, 3, 4, 5, nan, nan, nan, nan]}

        self.dates = DateRange('1/1/2011', periods=10)

        self.frame = SparseDataFrame(self.data, index=self.dates)
        self.iframe = SparseDataFrame(self.data, index=self.dates,
                                      kind='integer')

        values = self.frame.values.copy()
        values[np.isnan(values)] = 0

        self.zframe = SparseDataFrame(values, columns=['A', 'B', 'C', 'D'],
                                      default_fill_value=0,
                                      index=self.dates)

        values = self.frame.values.copy()
        values[np.isnan(values)] = 2
        self.fill_frame = SparseDataFrame(values, columns=['A', 'B', 'C', 'D'],
                                          default_fill_value=2,
                                          index=self.dates)

    def test_copy(self):
        cp = self.frame.copy()
        self.assert_(isinstance(cp, SparseDataFrame))
        assert_sp_frame_equal(cp, self.frame)
        self.assert_(cp.index is self.frame.index)

        # TODO: Test that DATA is copied!

    def test_constructor(self):
        for col, series in self.frame.iteritems():
            self.assert_(isinstance(series, SparseSeries))

        self.assert_(isinstance(self.iframe['A'].sp_index, IntIndex))

        # construct from nested dict
        data = {}
        for c, s in self.frame.iteritems():
            data[c] = s.toDict()

        sdf = SparseDataFrame(data)
        assert_sp_frame_equal(sdf, self.frame)

    def test_array_interface(self):
        res = np.sqrt(self.frame)
        dres = np.sqrt(self.frame.to_dense())
        assert_frame_equal(res.to_dense(), dres)

    def test_dense_to_sparse(self):
        df = DataFrame({'A' : [nan, nan, nan, 1, 2],
                        'B' : [1, 2, nan, nan, nan]})
        sdf = df.to_sparse()
        self.assert_(isinstance(sdf, SparseDataFrame))
        self.assert_(np.isnan(sdf.default_fill_value))
        self.assert_(isinstance(sdf['A'].sp_index, BlockIndex))
        testing.assert_frame_equal(sdf.to_dense(), df)

        sdf = df.to_sparse(kind='integer')
        self.assert_(isinstance(sdf['A'].sp_index, IntIndex))

        df = DataFrame({'A' : [0, 0, 0, 1, 2],
                        'B' : [1, 2, 0, 0, 0]})
        sdf = df.to_sparse(fill_value=0)
        self.assertEquals(sdf.default_fill_value, 0)
        testing.assert_frame_equal(sdf.to_dense(), df)

    def test_sparse_to_dense(self):
        pass

    def test_sparse_series_ops(self):
        self._check_frame_ops(self.frame)
        self._check_frame_ops(self.iframe)

        self._check_frame_ops(self.zframe)
        self._check_frame_ops(self.fill_frame)

    def _check_frame_ops(self, frame):
        def _compare_to_dense(a, b, da, db, op, fill=np.NaN):
            sparse_result = op(a, b)
            dense_result = op(da, db)
            dense_result = dense_result.to_sparse(fill_value=fill)
            assert_sp_frame_equal(sparse_result, dense_result,
                                  exact_indices=False)

        opnames = ['add', 'sub', 'mul', 'div']
        ops = [getattr(operator, name) for name in opnames]

        fidx = frame.index

        # time series operations

        series = [frame['A'], frame['B'],
                  frame['C'], frame['D'],
                  frame['A'].reindex(fidx[:7]),
                  frame['A'].reindex(fidx[::2]),
                  SparseSeries([], index=[])]

        for op in ops:
            for s in series:
                _compare_to_dense(frame, s, frame.to_dense(),
                                  s.to_dense(), op)
                _compare_to_dense(s, frame, s.to_dense(),
                                  frame.to_dense(), op)

        # cross-sectional operations
        series = [frame.xs(fidx[0]),
                  frame.xs(fidx[3]),
                  frame.xs(fidx[5]),
                  frame.xs(fidx[7]),
                  frame.xs(fidx[5])[:2]]

        for op in ops:
            for s in series:
                _compare_to_dense(frame, s, frame.to_dense(),
                                  s, op)
                _compare_to_dense(s, frame, s,
                                  frame.to_dense(), op)

    def test_scalar_ops(self):
        pass

    def test_insert_col(self):
        sdf = self.frame.copy()

        # insert SparseSeries
        sdf['E'] = sdf['A']
        self.assert_(isinstance(sdf['E'], SparseSeries))
        assert_sp_series_equal(sdf['E'], sdf['A'])

        # TODO insert SparseSeries differently-indexed
        sdf['E'] = sdf['A'][::2]

        # insert Series
        sdf['F'] = sdf['A'].to_dense()
        self.assert_(isinstance(sdf['F'], SparseSeries))
        assert_sp_series_equal(sdf['F'], sdf['A'])

        # insert Series differently-indexed

        # insert ndarray

        # insert ndarray wrong size


    def test_corr(self):
        res = self.frame.corr()
        self.assert_(isinstance(res, SparseDataFrame))
        assert_frame_equal(res.to_dense(), self.frame.to_dense().corr())

    def test_reindex(self):
        # propagate CORRECT fill value

        pass

class TestSparseWidePanel(TestCase):
    pass

if __name__ == '__main__':
    import nose
    nose.runmodule(argv=[__file__,'-vvs','-x','--pdb', '--pdb-failure'],
                   exit=False)

    # nose.runmodule(argv=[__file__,'-vvs','-x','--pdb', '--pdb-failure',
    #                      '--with-profile'],
    #                exit=False)
