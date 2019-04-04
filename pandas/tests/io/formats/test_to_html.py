# -*- coding: utf-8 -*-

from datetime import datetime
from io import StringIO
import re

import numpy as np
import pytest

from pandas.compat import lrange

import pandas as pd
from pandas import DataFrame, Index, MultiIndex, option_context
from pandas.util import testing as tm

import pandas.io.formats.format as fmt

lorem_ipsum = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod"
    " tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim"
    " veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex"
    " ea commodo consequat. Duis aute irure dolor in reprehenderit in"
    " voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur"
    " sint occaecat cupidatat non proident, sunt in culpa qui officia"
    " deserunt mollit anim id est laborum.")


def expected_html(datapath, name):
    """
    Read HTML file from formats data directory.

    Parameters
    ----------
    datapath : pytest fixture
        The datapath fixture injected into a test by pytest.
    name : str
        The name of the HTML file without the suffix.

    Returns
    -------
    str : contents of HTML file.
    """
    filename = '.'.join([name, 'html'])
    filepath = datapath('io', 'formats', 'data', 'html', filename)
    with open(filepath, encoding='utf-8') as f:
        html = f.read()
    return html.rstrip()


@pytest.fixture(params=['mixed', 'empty'])
def biggie_df_fixture(request):
    """Fixture for a big mixed Dataframe and an empty Dataframe"""
    if request.param == 'mixed':
        df = DataFrame({'A': np.random.randn(200),
                        'B': tm.makeStringIndex(200)},
                       index=lrange(200))
        df.loc[:20, 'A'] = np.nan
        df.loc[:20, 'B'] = np.nan
        return df
    elif request.param == 'empty':
        df = DataFrame(index=np.arange(200))
        return df


@pytest.fixture(params=fmt._VALID_JUSTIFY_PARAMETERS)
def justify(request):
    return request.param


@pytest.mark.parametrize('col_space', [30, 50])
def test_to_html_with_col_space(col_space):
    df = DataFrame(np.random.random(size=(1, 3)))
    # check that col_space affects HTML generation
    # and be very brittle about it.
    result = df.to_html(col_space=col_space)
    hdrs = [x for x in result.split(r"\n") if re.search(r"<th[>\s]", x)]
    assert len(hdrs) > 0
    for h in hdrs:
        assert "min-width" in h
        assert str(col_space) in h


def test_to_html_with_empty_string_label():
    # GH 3547, to_html regards empty string labels as repeated labels
    data = {'c1': ['a', 'b'], 'c2': ['a', ''], 'data': [1, 2]}
    df = DataFrame(data).set_index(['c1', 'c2'])
    result = df.to_html()
    assert "rowspan" not in result


@pytest.mark.parametrize('df,expected', [
    (DataFrame({'\u03c3': np.arange(10.)}), 'unicode_1'),
    (DataFrame({'A': ['\u03c3']}), 'unicode_2')
])
def test_to_html_unicode(df, expected, datapath):
    expected = expected_html(datapath, expected)
    result = df.to_html()
    assert result == expected


def test_to_html_decimal(datapath):
    # GH 12031
    df = DataFrame({'A': [6.0, 3.1, 2.2]})
    result = df.to_html(decimal=',')
    expected = expected_html(datapath, 'gh12031_expected_output')
    assert result == expected


@pytest.mark.parametrize('kwargs,string,expected', [
    (dict(), "<type 'str'>", 'escaped'),
    (dict(escape=False), "<b>bold</b>", 'escape_disabled')
])
def test_to_html_escaped(kwargs, string, expected, datapath):
    a = 'str<ing1 &amp;'
    b = 'stri>ng2 &amp;'

    test_dict = {'co<l1': {a: string,
                           b: string},
                 'co>l2': {a: string,
                           b: string}}
    result = DataFrame(test_dict).to_html(**kwargs)
    expected = expected_html(datapath, expected)
    assert result == expected


@pytest.mark.parametrize('index_is_named', [True, False])
def test_to_html_multiindex_index_false(index_is_named, datapath):
    # GH 8452
    df = DataFrame({
        'a': range(2),
        'b': range(3, 5),
        'c': range(5, 7),
        'd': range(3, 5)
    })
    df.columns = MultiIndex.from_product([['a', 'b'], ['c', 'd']])
    if index_is_named:
        df.index = Index(df.index.values, name='idx')
    result = df.to_html(index=False)
    expected = expected_html(datapath, 'gh8452_expected_output')
    assert result == expected


@pytest.mark.parametrize('multi_sparse,expected', [
    (False, 'multiindex_sparsify_false_multi_sparse_1'),
    (False, 'multiindex_sparsify_false_multi_sparse_2'),
    (True, 'multiindex_sparsify_1'),
    (True, 'multiindex_sparsify_2')
])
def test_to_html_multiindex_sparsify(multi_sparse, expected, datapath):
    index = MultiIndex.from_arrays([[0, 0, 1, 1], [0, 1, 0, 1]],
                                   names=['foo', None])
    df = DataFrame([[0, 1], [2, 3], [4, 5], [6, 7]], index=index)
    if expected.endswith('2'):
        df.columns = index[::2]
    with option_context('display.multi_sparse', multi_sparse):
        result = df.to_html()
    expected = expected_html(datapath, expected)
    assert result == expected


@pytest.mark.parametrize('max_rows,expected', [
    (60, 'gh14882_expected_output_1'),

    # Test that ... appears in a middle level
    (56, 'gh14882_expected_output_2')
])
def test_to_html_multiindex_odd_even_truncate(max_rows, expected, datapath):
    # GH 14882 - Issue on truncation with odd length DataFrame
    index = MultiIndex.from_product([[100, 200, 300],
                                     [10, 20, 30],
                                     [1, 2, 3, 4, 5, 6, 7]],
                                    names=['a', 'b', 'c'])
    df = DataFrame({'n': range(len(index))}, index=index)
    result = df.to_html(max_rows=max_rows)
    expected = expected_html(datapath, expected)
    assert result == expected


@pytest.mark.parametrize('df,formatters,expected', [
    (DataFrame(
        [[0, 1], [2, 3], [4, 5], [6, 7]],
        columns=['foo', None], index=lrange(4)),
     {'__index__': lambda x: 'abcd' [x]},
     'index_formatter'),

    (DataFrame(
        {'months': [datetime(2016, 1, 1), datetime(2016, 2, 2)]}),
     {'months': lambda x: x.strftime('%Y-%m')},
     'datetime64_monthformatter'),

    (DataFrame({'hod': pd.to_datetime(['10:10:10.100', '12:12:12.120'],
                                      format='%H:%M:%S.%f')}),
     {'hod': lambda x: x.strftime('%H:%M')},
     'datetime64_hourformatter')
])
def test_to_html_formatters(df, formatters, expected, datapath):
    expected = expected_html(datapath, expected)
    result = df.to_html(formatters=formatters)
    assert result == expected


def test_to_html_regression_GH6098():
    df = DataFrame({
        'clé1': ['a', 'a', 'b', 'b', 'a'],
        'clé2': ['1er', '2ème', '1er', '2ème', '1er'],
        'données1': np.random.randn(5),
        'données2': np.random.randn(5)})

    # it works
    df.pivot_table(index=['clé1'], columns=['clé2'])._repr_html_()


def test_to_html_truncate(datapath):
    index = pd.date_range(start='20010101', freq='D', periods=20)
    df = DataFrame(index=index, columns=range(20))
    result = df.to_html(max_rows=8, max_cols=4)
    expected = expected_html(datapath, 'truncate')
    assert result == expected


@pytest.mark.parametrize('sparsify,expected', [
    (True, 'truncate_multi_index'),
    (False, 'truncate_multi_index_sparse_off')
])
def test_to_html_truncate_multi_index(sparsify, expected, datapath):
    arrays = [['bar', 'bar', 'baz', 'baz', 'foo', 'foo', 'qux', 'qux'],
              ['one', 'two', 'one', 'two', 'one', 'two', 'one', 'two']]
    df = DataFrame(index=arrays, columns=arrays)
    result = df.to_html(max_rows=7, max_cols=7, sparsify=sparsify)
    expected = expected_html(datapath, expected)
    assert result == expected


@pytest.mark.parametrize('option,result,expected', [
    (None, lambda df: df.to_html(), '1'),
    (None, lambda df: df.to_html(border=0), '0'),
    (0, lambda df: df.to_html(), '0'),
    (0, lambda df: df._repr_html_(), '0'),
])
def test_to_html_border(option, result, expected):
    df = DataFrame({'A': [1, 2]})
    if option is None:
        result = result(df)
    else:
        with option_context('display.html.border', option):
            result = result(df)
    expected = 'border="{}"'.format(expected)
    assert expected in result


def test_display_option_warning():
    with tm.assert_produces_warning(FutureWarning,
                                    check_stacklevel=False):
        pd.options.html.border


@pytest.mark.parametrize('biggie_df_fixture', ['mixed'], indirect=True)
def test_to_html(biggie_df_fixture):
    # TODO: split this test
    df = biggie_df_fixture
    s = df.to_html()

    buf = StringIO()
    retval = df.to_html(buf=buf)
    assert retval is None
    assert buf.getvalue() == s

    assert isinstance(s, str)

    df.to_html(columns=['B', 'A'], col_space=17)
    df.to_html(columns=['B', 'A'],
               formatters={'A': lambda x: '{x:.1f}'.format(x=x)})

    df.to_html(columns=['B', 'A'], float_format=str)
    df.to_html(columns=['B', 'A'], col_space=12, float_format=str)


@pytest.mark.parametrize('biggie_df_fixture', ['empty'], indirect=True)
def test_to_html_empty_dataframe(biggie_df_fixture):
    df = biggie_df_fixture
    df.to_html()


def test_to_html_filename(biggie_df_fixture, tmpdir):
    df = biggie_df_fixture
    expected = df.to_html()
    path = tmpdir.join('test.html')
    df.to_html(path)
    result = path.read()
    assert result == expected


def test_to_html_with_no_bold():
    df = DataFrame({'x': np.random.randn(5)})
    html = df.to_html(bold_rows=False)
    result = html[html.find("</thead>")]
    assert '<strong' not in result


def test_to_html_columns_arg():
    df = DataFrame(tm.getSeriesData())
    result = df.to_html(columns=['A'])
    assert '<th>B</th>' not in result


@pytest.mark.parametrize('columns,justify,expected', [
    (MultiIndex.from_tuples(
        list(zip(np.arange(2).repeat(2), np.mod(lrange(4), 2))),
        names=['CL0', 'CL1']),
     'left',
     'multiindex_1'),

    (MultiIndex.from_tuples(
        list(zip(range(4), np.mod(lrange(4), 2)))),
     'right',
     'multiindex_2')
])
def test_to_html_multiindex(columns, justify, expected, datapath):
    df = DataFrame([list('abcd'), list('efgh')], columns=columns)
    result = df.to_html(justify=justify)
    expected = expected_html(datapath, expected)
    assert result == expected


def test_to_html_justify(justify, datapath):
    df = DataFrame({'A': [6, 30000, 2],
                    'B': [1, 2, 70000],
                    'C': [223442, 0, 1]},
                   columns=['A', 'B', 'C'])
    result = df.to_html(justify=justify)
    expected = expected_html(datapath, 'justify').format(justify=justify)
    assert result == expected


@pytest.mark.parametrize("justify", ["super-right", "small-left",
                                     "noinherit", "tiny", "pandas"])
def test_to_html_invalid_justify(justify):
    # GH 17527
    df = DataFrame()
    msg = "Invalid value for justify parameter"

    with pytest.raises(ValueError, match=msg):
        df.to_html(justify=justify)


def test_to_html_index(datapath):
    # TODO: split this test
    index = ['foo', 'bar', 'baz']
    df = DataFrame({'A': [1, 2, 3],
                    'B': [1.2, 3.4, 5.6],
                    'C': ['one', 'two', np.nan]},
                   columns=['A', 'B', 'C'],
                   index=index)
    expected_with_index = expected_html(datapath, 'index_1')
    assert df.to_html() == expected_with_index

    expected_without_index = expected_html(datapath, 'index_2')
    result = df.to_html(index=False)
    for i in index:
        assert i not in result
    assert result == expected_without_index
    df.index = Index(['foo', 'bar', 'baz'], name='idx')
    expected_with_index = expected_html(datapath, 'index_3')
    assert df.to_html() == expected_with_index
    assert df.to_html(index=False) == expected_without_index

    tuples = [('foo', 'car'), ('foo', 'bike'), ('bar', 'car')]
    df.index = MultiIndex.from_tuples(tuples)

    expected_with_index = expected_html(datapath, 'index_4')
    assert df.to_html() == expected_with_index

    result = df.to_html(index=False)
    for i in ['foo', 'bar', 'car', 'bike']:
        assert i not in result
    # must be the same result as normal index
    assert result == expected_without_index

    df.index = MultiIndex.from_tuples(tuples, names=['idx1', 'idx2'])
    expected_with_index = expected_html(datapath, 'index_5')
    assert df.to_html() == expected_with_index
    assert df.to_html(index=False) == expected_without_index


@pytest.mark.parametrize('classes', [
    "sortable draggable",
    ["sortable", "draggable"]
])
def test_to_html_with_classes(classes, datapath):
    df = DataFrame()
    expected = expected_html(datapath, 'with_classes')
    result = df.to_html(classes=classes)
    assert result == expected


def test_to_html_no_index_max_rows(datapath):
    # GH 14998
    df = DataFrame({"A": [1, 2, 3, 4]})
    result = df.to_html(index=False, max_rows=1)
    expected = expected_html(datapath, 'gh14998_expected_output')
    assert result == expected


def test_to_html_multiindex_max_cols(datapath):
    # GH 6131
    index = MultiIndex(levels=[['ba', 'bb', 'bc'], ['ca', 'cb', 'cc']],
                       codes=[[0, 1, 2], [0, 1, 2]],
                       names=['b', 'c'])
    columns = MultiIndex(levels=[['d'], ['aa', 'ab', 'ac']],
                         codes=[[0, 0, 0], [0, 1, 2]],
                         names=[None, 'a'])
    data = np.array(
        [[1., np.nan, np.nan], [np.nan, 2., np.nan], [np.nan, np.nan, 3.]])
    df = DataFrame(data, index, columns)
    result = df.to_html(max_cols=2)
    expected = expected_html(datapath, 'gh6131_expected_output')
    assert result == expected


def test_to_html_multi_indexes_index_false(datapath):
    # GH 22579
    df = DataFrame({'a': range(10), 'b': range(10, 20), 'c': range(10, 20),
                    'd': range(10, 20)})
    df.columns = MultiIndex.from_product([['a', 'b'], ['c', 'd']])
    df.index = MultiIndex.from_product([['a', 'b'],
                                        ['c', 'd', 'e', 'f', 'g']])
    result = df.to_html(index=False)
    expected = expected_html(datapath, 'gh22579_expected_output')
    assert result == expected


@pytest.mark.parametrize('index_names', [True, False])
@pytest.mark.parametrize('header', [True, False])
@pytest.mark.parametrize('index', [True, False])
@pytest.mark.parametrize('column_index, column_type', [
    (Index([0, 1]), 'unnamed_standard'),
    (Index([0, 1], name='columns.name'), 'named_standard'),
    (MultiIndex.from_product([['a'], ['b', 'c']]), 'unnamed_multi'),
    (MultiIndex.from_product(
        [['a'], ['b', 'c']], names=['columns.name.0',
                                    'columns.name.1']), 'named_multi')
])
@pytest.mark.parametrize('row_index, row_type', [
    (Index([0, 1]), 'unnamed_standard'),
    (Index([0, 1], name='index.name'), 'named_standard'),
    (MultiIndex.from_product([['a'], ['b', 'c']]), 'unnamed_multi'),
    (MultiIndex.from_product(
        [['a'], ['b', 'c']], names=['index.name.0',
                                    'index.name.1']), 'named_multi')
])
def test_to_html_basic_alignment(
        datapath, row_index, row_type, column_index, column_type,
        index, header, index_names):
    # GH 22747, GH 22579
    df = DataFrame(np.zeros((2, 2), dtype=int),
                   index=row_index, columns=column_index)
    result = df.to_html(
        index=index, header=header, index_names=index_names)

    if not index:
        row_type = 'none'
    elif not index_names and row_type.startswith('named'):
        row_type = 'un' + row_type

    if not header:
        column_type = 'none'
    elif not index_names and column_type.startswith('named'):
        column_type = 'un' + column_type

    filename = 'index_' + row_type + '_columns_' + column_type
    expected = expected_html(datapath, filename)
    assert result == expected


@pytest.mark.parametrize('index_names', [True, False])
@pytest.mark.parametrize('header', [True, False])
@pytest.mark.parametrize('index', [True, False])
@pytest.mark.parametrize('column_index, column_type', [
    (Index(np.arange(8)), 'unnamed_standard'),
    (Index(np.arange(8), name='columns.name'), 'named_standard'),
    (MultiIndex.from_product(
        [['a', 'b'], ['c', 'd'], ['e', 'f']]), 'unnamed_multi'),
    (MultiIndex.from_product(
        [['a', 'b'], ['c', 'd'], ['e', 'f']], names=['foo', None, 'baz']),
        'named_multi')
])
@pytest.mark.parametrize('row_index, row_type', [
    (Index(np.arange(8)), 'unnamed_standard'),
    (Index(np.arange(8), name='index.name'), 'named_standard'),
    (MultiIndex.from_product(
        [['a', 'b'], ['c', 'd'], ['e', 'f']]), 'unnamed_multi'),
    (MultiIndex.from_product(
        [['a', 'b'], ['c', 'd'], ['e', 'f']], names=['foo', None, 'baz']),
        'named_multi')
])
def test_to_html_alignment_with_truncation(
        datapath, row_index, row_type, column_index, column_type,
        index, header, index_names):
    # GH 22747, GH 22579
    df = DataFrame(np.arange(64).reshape(8, 8),
                   index=row_index, columns=column_index)
    result = df.to_html(
        max_rows=4, max_cols=4,
        index=index, header=header, index_names=index_names)

    if not index:
        row_type = 'none'
    elif not index_names and row_type.startswith('named'):
        row_type = 'un' + row_type

    if not header:
        column_type = 'none'
    elif not index_names and column_type.startswith('named'):
        column_type = 'un' + column_type

    filename = 'trunc_df_index_' + row_type + '_columns_' + column_type
    expected = expected_html(datapath, filename)
    assert result == expected


@pytest.mark.parametrize('index', [False, 0])
def test_to_html_truncation_index_false_max_rows(datapath, index):
    # GH 15019
    data = [[1.764052, 0.400157],
            [0.978738, 2.240893],
            [1.867558, -0.977278],
            [0.950088, -0.151357],
            [-0.103219, 0.410599]]
    df = DataFrame(data)
    result = df.to_html(max_rows=4, index=index)
    expected = expected_html(datapath, 'gh15019_expected_output')
    assert result == expected


@pytest.mark.parametrize('index', [False, 0])
@pytest.mark.parametrize('col_index_named, expected_output', [
    (False, 'gh22783_expected_output'),
    (True, 'gh22783_named_columns_index')
])
def test_to_html_truncation_index_false_max_cols(
        datapath, index, col_index_named, expected_output):
    # GH 22783
    data = [[1.764052, 0.400157, 0.978738, 2.240893, 1.867558],
            [-0.977278, 0.950088, -0.151357, -0.103219, 0.410599]]
    df = DataFrame(data)
    if col_index_named:
        df.columns.rename('columns.name', inplace=True)
    result = df.to_html(max_cols=4, index=index)
    expected = expected_html(datapath, expected_output)
    assert result == expected


@pytest.mark.parametrize('notebook', [True, False])
def test_to_html_notebook_has_style(notebook):
    df = DataFrame({"A": [1, 2, 3]})
    result = df.to_html(notebook=notebook)

    if notebook:
        assert "tbody tr th:only-of-type" in result
        assert "vertical-align: middle;" in result
        assert "thead th" in result
    else:
        assert "tbody tr th:only-of-type" not in result
        assert "vertical-align: middle;" not in result
        assert "thead th" not in result


def test_to_html_with_index_names_false():
    # GH 16493
    df = DataFrame({"A": [1, 2]}, index=Index(['a', 'b'],
                                              name='myindexname'))
    result = df.to_html(index_names=False)
    assert 'myindexname' not in result


def test_to_html_with_id():
    # GH 8496
    df = DataFrame({"A": [1, 2]}, index=Index(['a', 'b'],
                                              name='myindexname'))
    result = df.to_html(index_names=False, table_id="TEST_ID")
    assert ' id="TEST_ID"' in result


@pytest.mark.parametrize('value,float_format,expected', [
    (0.19999, '%.3f', 'gh21625_expected_output'),
    (100.0, '%.0f', 'gh22270_expected_output'),
])
def test_to_html_float_format_no_fixed_width(
        value, float_format, expected, datapath):
    # GH 21625, GH 22270
    df = DataFrame({'x': [value]})
    expected = expected_html(datapath, expected)
    result = df.to_html(float_format=float_format)
    assert result == expected


@pytest.mark.parametrize("render_links,expected", [
    (True, 'render_links_true'),
    (False, 'render_links_false'),
])
def test_to_html_render_links(render_links, expected, datapath):
    # GH 2679
    data = [
        [0, 'http://pandas.pydata.org/?q1=a&q2=b', 'pydata.org'],
        [0, 'www.pydata.org', 'pydata.org']
    ]
    df = DataFrame(data, columns=['foo', 'bar', None])

    result = df.to_html(render_links=render_links)
    expected = expected_html(datapath, expected)
    assert result == expected


@pytest.mark.parametrize('method,expected', [
    ('to_html', lambda x:lorem_ipsum),
    ('_repr_html_', lambda x:lorem_ipsum[:x - 4] + '...')  # regression case
])
@pytest.mark.parametrize('max_colwidth', [10, 20, 50, 100])
def test_ignore_display_max_colwidth(method, expected, max_colwidth):
    # see gh-17004
    df = DataFrame([lorem_ipsum])
    with pd.option_context('display.max_colwidth', max_colwidth):
        result = getattr(df, method)()
    expected = expected(max_colwidth)
    assert expected in result


@pytest.mark.parametrize("classes", [True, 0])
def test_to_html_invalid_classes_type(classes):
    # GH 25608
    df = DataFrame()
    msg = "classes must be a string, list, or tuple"

    with pytest.raises(TypeError, match=msg):
        df.to_html(classes=classes)


def test_to_html_round_column_headers():
    # GH 17280
    df = DataFrame([1], columns=[0.55555])
    with pd.option_context('display.precision', 3):
        html = df.to_html(notebook=False)
        notebook = df.to_html(notebook=True)
    assert "0.55555" in html
    assert "0.556" in notebook
