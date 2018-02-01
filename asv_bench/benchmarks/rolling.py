import pandas as pd
import numpy as np

from .pandas_vb_common import setup  # noqa


class Methods(object):

    sample_time = 0.2
    params = (['DataFrame', 'Series'],
              [10, 1000],
              ['int', 'float'],
              ['median', 'mean', 'max', 'min', 'std', 'count', 'skew', 'kurt',
               'sum'])
    param_names = ['contructor', 'window', 'dtype', 'method']

    def setup(self, constructor, window, dtype, method):
        N = 10**5
        arr = np.random.random(N).astype(dtype)
        self.roll = getattr(pd, constructor)(arr).rolling(window)

    def time_rolling(self, constructor, window, dtype, method):
        getattr(self.roll, method)()


class Pairwise(object):

    sample_time = 0.2
    params = ([10, 1000, None],
              ['corr', 'cov'],
              [True, False])
    param_names = ['window', 'method', 'pairwise']

    def setup(self, window, method, pairwise):
        N = 10**4
        arr = np.random.random(N)
        self.df = pd.DataFrame(arr)

    def time_pairwise(self, window, method, pairwise):
        if window is None:
            r = self.df.expanding()
        else:
            r = self.df.rolling(window=window)
        getattr(r, method)(self.df, pairwise=pairwise)


class Quantile(object):

    sample_time = 0.2
    params = (['DataFrame', 'Series'],
              [10, 1000],
              ['int', 'float'],
              [0, 0.5, 1])
    param_names = ['constructor', 'window', 'dtype', 'percentile']

    def setup(self, constructor, window, dtype, percentile):
        N = 10**5
        arr = np.random.random(N).astype(dtype)
        self.roll = getattr(pd, constructor)(arr).rolling(window)

    def time_quantile(self, constructor, window, dtype, percentile):
        self.roll.quantile(percentile)
