import bottleneck as nb
import pandas as pd
import numpy as np

from trtools.monkey import patch

def bn_topn(arr, N, ascending=None):
    """
    Return the top N results. Negative N will give N lowest results

    Paramters
    ---------
    arr : Series
        one dimension array
    N : int
        number of elements to return. Negative numbers will return smallest
    ascending : bool
        Ordering of the return values. Default behavior is greatest absolute
        magnitude.

    Note
    ----
    Default ascending order depends on N and whether you are looking for the
    top and bottom results. If you are looking for the top results, the 
    most positive results will come first. If you are looking for the bottom
    results, then the most negative results comes first
    """
    if arr.ndim > 1:
        raise Exception("Only works on ndim=1")
    if ascending is None:
        ascending = not N > 0

    arr = arr[~np.isnan(arr)]
    if N > 0: # nlargest
        N = min(abs(N), len(arr))
        N = len(arr) - abs(N)
        sl = slice(N, None)
    else: # nsmallest
        N = min(abs(N), len(arr))
        sl = slice(None, N)

    if N == 0:
        bn_res = arr
    else:
        out = nb.partsort(arr, N)
        bn_res = out[sl]

    bn_res = np.sort(bn_res) # sort output
    if not ascending:
        bn_res = bn_res[::-1]
    return bn_res

def bn_topargn(arr, N, ascending=None):
    """
    Return the indices of the top N results. 
    The following should be equivalent

    >>> res1 = arr[bn_topargn(arr, 10)] 
    >>> res2 = bn_topn(arr, 10)
    >>> np.all(res1 == res2)
        True
    """
    if arr.ndim > 1:
        raise Exception("Only works on ndim=1")
    if ascending is None:
        ascending = not N > 0

    na_mask = np.isnan(arr)
    has_na = na_mask.sum()
    if has_na:
        # store the old indices for translating back later
        old_index_map = np.where(~na_mask)[0]
        arr = arr[~na_mask]

    if N > 0: # nlargest
        N = len(arr) - abs(N)
        sl = slice(N, None)
    else: # nsmallest
        N = abs(N)
        sl = slice(None, N)
    out = nb.argpartsort(arr, N)
    index = out[sl]
    # sort the index by their values
    index_sort = np.argsort(arr[index])
    if not ascending:
        index_sort = index_sort[::-1]
    index = index[index_sort]

    # index is only correct with arr without nans. 
    # Map back to old_index if needed
    if has_na:
        index = old_index_map[index]
    return index

topn = bn_topn
topargn = bn_topargn

@patch(pd.Series, 'topn')
def _topn_series(self, N, ascending=None):
    return pd.Series(topn(self, N, ascending=ascending))

@patch(pd.Series, 'topargn')
def _topargn_series(self, N, ascending=None):
    return pd.Series(topargn(self, N, ascending=ascending))

# bn.partsort works on matrix, but i dunno how to handle nans in that case
# i suppose I could min/max and then set Nan to sentinal values?
@patch(pd.DataFrame, 'topn', override=True)
def topn_df(self, N, ascending=None, wrap=True):
    vals = self.values
    rows = vals.shape[0]
    # don't make the return have more columns than the dataframes
    cols = min(len(self.columns), abs(N))
    ret = np.ndarray((rows, cols))
    ret[:] = np.nan
    for i in range(rows):
        r = topn(vals[i], N=N, ascending=ascending)
        ret[i][:len(r)] = r
    if wrap:
        return pd.DataFrame(ret, index=self.index)
    return np.array(ret)

@patch(pd.DataFrame, 'topargn', override=True)
def topargn_df(self, N, ascending=None, wrap=True):
    vals = self.values
    rows = vals.shape[0]
    ret = np.ndarray((rows, abs(N)), dtype=int)
    for i in range(rows):
        r = topargn(vals[i], N=N, ascending=ascending)
        ret[i] = r
    if wrap:
        return pd.DataFrame(ret, index=self.index)
    return np.array(ret)

@patch(pd.DataFrame, 'topindexn', override=True)
def topindexn_df(self, N, ascending=None):
    """
    Pretty much topargn, except it returns column key instead of
    positional int
    """
    # get pos args
    ret = topargn_df(self, N=N, ascending=ascending, wrap=False)
    # grab column values
    ret = self.columns[ret]
    return pd.DataFrame(ret, index=self.index)
