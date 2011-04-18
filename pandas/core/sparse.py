import numpy as np

import operator

from pandas.core.index import Index, NULL_INDEX
from pandas.core.series import Series, TimeSeries
from pandas.core.frame import DataFrame

from pandas.lib.sparse import BlockIndex, IntIndex, SparseVector
import pandas.lib.sparse as splib

def make_sparse(series, kind='block', sparse_value=np.NaN):
    """

    kind : {'block', 'integer'}
    """
    assert(isinstance(series, Series))

    if kind == 'block':
        pass
    elif kind == 'integer':
        pass
    else:
        raise ValueError('must be block or integer type')

class SparseSeries(Series):
    """
    Data structure for labeled, sparse floating point data

    Parameters
    ----------

    """

    def __new__(cls, data, index=None, copy=False, kind='block',
                sparse_value=np.NaN):

        if isinstance(data, SparseVector):
            if index is not None:
                assert(len(index) == data.length)
        elif isinstance(data, (Series, dict)):
            data = Series(data)

            if index is None:
                index = data.index

            data = make_sparse(data, kind=kind)

        if index is None:
            index = Index(np.arange(data.length))

        # Create array, do *not* copy data by default, infer type
        subarr = np.array(data.values, dtype=np.float64, copy=False)

        if index is None:
            raise Exception('Index cannot be None!')

        # This is to prevent mixed-type Series getting all casted to
        # NumPy string type, e.g. NaN --> '-1#IND'.
        if issubclass(subarr.dtype.type, basestring):
            subarr = np.array(data, dtype=object, copy=copy)

        if subarr.index._allDates:
            cls = SparseTimeSeries

        # Change the class of the array to be the subclass type.
        subarr = subarr.view(cls)
        subarr.index = index
        subarr._vector = data
        subarr._sparse_value = sparse_value
        return subarr

    def __hash__(self):
        raise TypeError('unhashable type')

    def __setslice__(self, i, j, value):
        """Set slice equal to given value(s)"""
        ndarray.__setslice__(self, i, j, value)

    def __repr__(self):
        """Clean string representation of a Series"""
        vals = self.values
        index = self.index

        if len(index) > 500:
            head = _seriesRepr(index[:50], vals[:50])
            tail = _seriesRepr(index[-50:], vals[-50:])
            return head + '\n...\n' + tail + '\nlength: %d' % len(vals)
        elif len(index) > 0:
            return _seriesRepr(index, vals)
        else:
            return '%s' % ndarray.__repr__(self)

    def __contains__(self, key):
        return key in self.index

    def __len__(self):
        return self._vector.length

    def __str__(self):
        return repr(self)

    def __iter__(self):
        return iter(self.values)

    def __array_finalize__(self, obj):
        """
        Gets called after any ufunc or other array operations, necessary
        to pass on the index.
        """
        self._index = getattr(obj, '_index', None)
        self._vector = getattr(obj, '_vector', None)
        self._sparse_value = getattr(obj, '_sparse_value', None)

    def toDict(self):
        return dict(self.iteritems())

    @classmethod
    def fromValue(cls, value=np.NaN, index=None, dtype=None): # pragma: no cover
        warnings.warn("'fromValue', can call Series(value, index=index) now",
                      FutureWarning)

        return Series(value, index=index, dtype=dtype)

    def __getitem__(self, key):
        """
        Returns item(s) for requested index/sequence, overrides default behavior
        for series[key].

        Logic is as follows:
            - If key is in the index, return the value corresponding
              to that index
            - Otherwise, use key (presumably one integer or a sequence
              of integers) to obtain values from the series. In the case
              of a sequence, a 'slice' of the series (with corresponding dates)
              will be returned, otherwise a single value.
        """
        values = self.values

        try:
            # Check that we can even look for this in the index
            return values[self.index.indexMap[key]]
        except KeyError:
            if isinstance(key, (int, np.integer)):
                return values[key]
            raise Exception('Requested index not in this series!')
        except TypeError:
            # Could not hash item
            pass

        # is there a case where this would NOT be an ndarray?
        # need to find an example, I took out the case for now

        dataSlice = values[key]
        indices = Index(self.index.view(ndarray)[key])
        return Series(dataSlice, index=indices)

    def get(self, key, default=None):
        """
        Returns value occupying requested index, default to specified
        missing value if not present

        Parameters
        ----------
        key : object
            Index value looking for
        default : object, optional
            Value to return if key not in index

        Returns
        -------
        y : scalar
        """
        if key in self.index:
            return ndarray.__getitem__(self, self.index.indexMap[key])
        else:
            return default

    @property
    def values(self):
        return self._vector.to_ndarray()

    def to_dense(self):
        """
        Convert SparseSeries to (dense) Series
        """
        return Series(self.values, index=self.index)

    def copy(self):
        vec_copy = self._vector.copy()
        return SparseSeries(vec_copy, index=self.index)

class SparseTimeSeries(SparseSeries, TimeSeries):
    pass

class SparseDataFrame(DataFrame):
    _columns = None

    def __init__(self, data=None, index=None, columns=None, dtype=None):
        if isinstance(data, dict):
            sdict, columns, index = self._init_dict(data, index, columns, dtype)
        elif isinstance(data, (np.ndarray, list)):
            sdict, columns, index = self._init_matrix(data, index, columns,
                                                      dtype)
        elif isinstance(data, DataFrame):
            sdict = data._series.copy()

            if dtype is not None:
                sdict = dict((k, v.astype(dtype)) for k, v in data.iteritems())
            index = data.index
            columns = data.columns
        elif data is None:
            sdict = {}

            if index is None:
                index = NULL_INDEX

            if columns is None:
                columns = NULL_INDEX
            else:
                for c in columns:
                    sdict[c] = Series(np.NaN, index=index)

        self._series = sdict
        self.columns = columns
        self.index = index

    def _init_dict(self, data, index, columns, dtype):
        # pre-filter out columns if we passed it
        if columns is not None:
            if not isinstance(columns, Index):
                columns = Index(columns)

            data = dict((k, v) for k, v in data.iteritems() if k in columns)
        else:
            columns = Index(_try_sort(data.keys()))

        index = _extract_index(data, index)

        sdict = {}
        for k, v in data.iteritems():
            if isinstance(v, Series):
                # Forces alignment and copies data
                sdict[k] = v.reindex(index)
            else:
                if isinstance(v, dict):
                    v = [v.get(i, NaN) for i in index]

                try:
                    v = Series(v, dtype=dtype, index=index)
                except Exception:
                    v = Series(v, index=index)

                sdict[k] = v.copy()

        # add in any other columns we want to have (completeness)
        for c in columns:
            if c not in sdict:
                sdict[c] = Series(np.NaN, index=index)

        return sdict, columns, index

    def _init_matrix(self, data, index, columns, dtype):
        if not isinstance(data, np.ndarray):
            arr = np.array(data)
            if issubclass(arr.dtype.type, basestring):
                arr = np.array(data, dtype=object, copy=True)

            data = arr

        if data.ndim == 1:
            data = data.reshape((len(data), 1))
        elif data.ndim != 2:
            raise Exception('Must pass 2-d input!')

        N, K = data.shape

        if index is None:
            index = _default_index(N)

        if columns is None:
            columns = _default_index(K)

        if len(columns) != K:
            raise Exception('Column length mismatch: %d vs. %d' %
                            (len(columns), K))

        data = dict([(idx, data[:, i]) for i, idx in enumerate(columns)])
        return self._init_dict(data, index, columns, dtype)
