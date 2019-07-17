"""
Tests the usecols functionality during parsing
for all of the parsers defined in parsers.py
"""
from io import StringIO

import numpy as np
import pytest

from pandas._libs.tslib import Timestamp

from pandas import DataFrame, Index
import pandas.util.testing as tm

_msg_validate_usecols_arg = (
    "'usecols' must either be list-like "
    "of all strings, all unicode, all "
    "integers or a callable."
)
_msg_validate_usecols_names = (
    "Usecols do not match columns, columns expected but not found: {0}"
)


def test_raise_on_mixed_dtype_usecols(all_parsers):
    # See gh-12678
    data = """a,b,c
        1000,2000,3000
        4000,5000,6000
        """
    usecols = [0, "b", 2]
    parser = all_parsers

    with pytest.raises(ValueError, match=_msg_validate_usecols_arg):
        parser.read_csv(StringIO(data), usecols=usecols)


@pytest.mark.parametrize("usecols", [(1, 2), ("b", "c")])
def test_usecols(all_parsers, usecols):
    data = """\
a,b,c
1,2,3
4,5,6
7,8,9
10,11,12"""
    parser = all_parsers
    result = parser.read_csv(StringIO(data), usecols=usecols)

    expected = DataFrame([[2, 3], [5, 6], [8, 9], [11, 12]], columns=["b", "c"])
    tm.assert_frame_equal(result, expected)


def test_usecols_with_names(all_parsers):
    data = """\
a,b,c
1,2,3
4,5,6
7,8,9
10,11,12"""
    parser = all_parsers
    names = ["foo", "bar"]
    result = parser.read_csv(StringIO(data), names=names, usecols=[1, 2], header=0)

    expected = DataFrame([[2, 3], [5, 6], [8, 9], [11, 12]], columns=names)
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize(
    "names,usecols", [(["b", "c"], [1, 2]), (["a", "b", "c"], ["b", "c"])]
)
def test_usecols_relative_to_names(all_parsers, names, usecols):
    data = """\
1,2,3
4,5,6
7,8,9
10,11,12"""
    parser = all_parsers
    result = parser.read_csv(StringIO(data), names=names, header=None, usecols=usecols)

    expected = DataFrame([[2, 3], [5, 6], [8, 9], [11, 12]], columns=["b", "c"])
    tm.assert_frame_equal(result, expected)


def test_usecols_relative_to_names2(all_parsers):
    # see gh-5766
    data = """\
1,2,3
4,5,6
7,8,9
10,11,12"""
    parser = all_parsers
    result = parser.read_csv(
        StringIO(data), names=["a", "b"], header=None, usecols=[0, 1]
    )

    expected = DataFrame([[1, 2], [4, 5], [7, 8], [10, 11]], columns=["a", "b"])
    tm.assert_frame_equal(result, expected)


def test_usecols_name_length_conflict(all_parsers):
    data = """\
1,2,3
4,5,6
7,8,9
10,11,12"""
    parser = all_parsers
    msg = (
        "Number of passed names did not match number of header fields in the file"
        if parser.engine == "python"
        else "Passed header names mismatches usecols"
    )

    with pytest.raises(ValueError, match=msg):
        parser.read_csv(StringIO(data), names=["a", "b"], header=None, usecols=[1])


def test_usecols_single_string(all_parsers):
    # see gh-20558
    parser = all_parsers
    data = """foo, bar, baz
1000, 2000, 3000
4000, 5000, 6000"""

    with pytest.raises(ValueError, match=_msg_validate_usecols_arg):
        parser.read_csv(StringIO(data), usecols="foo")


@pytest.mark.parametrize(
    "data", ["a,b,c,d\n1,2,3,4\n5,6,7,8", "a,b,c,d\n1,2,3,4,\n5,6,7,8,"]
)
def test_usecols_index_col_false(all_parsers, data):
    # see gh-9082
    parser = all_parsers
    usecols = ["a", "c", "d"]
    expected = DataFrame({"a": [1, 5], "c": [3, 7], "d": [4, 8]})

    result = parser.read_csv(StringIO(data), usecols=usecols, index_col=False)
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize("index_col", ["b", 0])
@pytest.mark.parametrize("usecols", [["b", "c"], [1, 2]])
def test_usecols_index_col_conflict(all_parsers, usecols, index_col):
    # see gh-4201: test that index_col as integer reflects usecols
    parser = all_parsers
    data = "a,b,c,d\nA,a,1,one\nB,b,2,two"
    expected = DataFrame({"c": [1, 2]}, index=Index(["a", "b"], name="b"))

    result = parser.read_csv(StringIO(data), usecols=usecols, index_col=index_col)
    tm.assert_frame_equal(result, expected)


def test_usecols_index_col_conflict2(all_parsers):
    # see gh-4201: test that index_col as integer reflects usecols
    parser = all_parsers
    data = "a,b,c,d\nA,a,1,one\nB,b,2,two"

    expected = DataFrame({"b": ["a", "b"], "c": [1, 2], "d": ("one", "two")})
    expected = expected.set_index(["b", "c"])

    result = parser.read_csv(
        StringIO(data), usecols=["b", "c", "d"], index_col=["b", "c"]
    )
    tm.assert_frame_equal(result, expected)


def test_usecols_implicit_index_col(all_parsers):
    # see gh-2654
    parser = all_parsers
    data = "a,b,c\n4,apple,bat,5.7\n8,orange,cow,10"

    result = parser.read_csv(StringIO(data), usecols=["a", "b"])
    expected = DataFrame({"a": ["apple", "orange"], "b": ["bat", "cow"]}, index=[4, 8])
    tm.assert_frame_equal(result, expected)


def test_usecols_regex_sep(all_parsers):
    # see gh-2733
    parser = all_parsers
    data = "a  b  c\n4  apple  bat  5.7\n8  orange  cow  10"
    result = parser.read_csv(StringIO(data), sep=r"\s+", usecols=("a", "b"))

    expected = DataFrame({"a": ["apple", "orange"], "b": ["bat", "cow"]}, index=[4, 8])
    tm.assert_frame_equal(result, expected)


def test_usecols_with_whitespace(all_parsers):
    parser = all_parsers
    data = "a  b  c\n4  apple  bat  5.7\n8  orange  cow  10"

    result = parser.read_csv(StringIO(data), delim_whitespace=True, usecols=("a", "b"))
    expected = DataFrame({"a": ["apple", "orange"], "b": ["bat", "cow"]}, index=[4, 8])
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize(
    "usecols,expected",
    [
        # Column selection by index.
        ([0, 1], DataFrame(data=[[1000, 2000], [4000, 5000]], columns=["2", "0"])),
        # Column selection by name.
        (["0", "1"], DataFrame(data=[[2000, 3000], [5000, 6000]], columns=["0", "1"])),
    ],
)
def test_usecols_with_integer_like_header(all_parsers, usecols, expected):
    parser = all_parsers
    data = """2,0,1
1000,2000,3000
4000,5000,6000"""

    result = parser.read_csv(StringIO(data), usecols=usecols)
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize("usecols", [[0, 2, 3], [3, 0, 2]])
def test_usecols_with_parse_dates(all_parsers, usecols):
    # see gh-9755
    data = """a,b,c,d,e
0,1,20140101,0900,4
0,1,20140102,1000,4"""
    parser = all_parsers
    parse_dates = [[1, 2]]

    cols = {
        "a": [0, 0],
        "c_d": [Timestamp("2014-01-01 09:00:00"), Timestamp("2014-01-02 10:00:00")],
    }
    expected = DataFrame(cols, columns=["c_d", "a"])
    result = parser.read_csv(StringIO(data), usecols=usecols, parse_dates=parse_dates)
    tm.assert_frame_equal(result, expected)


def test_usecols_with_parse_dates2(all_parsers):
    # see gh-13604
    parser = all_parsers
    data = """2008-02-07 09:40,1032.43
2008-02-07 09:50,1042.54
2008-02-07 10:00,1051.65"""

    names = ["date", "values"]
    usecols = names[:]
    parse_dates = [0]

    index = Index(
        [
            Timestamp("2008-02-07 09:40"),
            Timestamp("2008-02-07 09:50"),
            Timestamp("2008-02-07 10:00"),
        ],
        name="date",
    )
    cols = {"values": [1032.43, 1042.54, 1051.65]}
    expected = DataFrame(cols, index=index)

    result = parser.read_csv(
        StringIO(data),
        parse_dates=parse_dates,
        index_col=0,
        usecols=usecols,
        header=None,
        names=names,
    )
    tm.assert_frame_equal(result, expected)


def test_usecols_with_parse_dates3(all_parsers):
    # see gh-14792
    parser = all_parsers
    data = """a,b,c,d,e,f,g,h,i,j
2016/09/21,1,1,2,3,4,5,6,7,8"""

    usecols = list("abcdefghij")
    parse_dates = [0]

    cols = {
        "a": Timestamp("2016-09-21"),
        "b": [1],
        "c": [1],
        "d": [2],
        "e": [3],
        "f": [4],
        "g": [5],
        "h": [6],
        "i": [7],
        "j": [8],
    }
    expected = DataFrame(cols, columns=usecols)

    result = parser.read_csv(StringIO(data), usecols=usecols, parse_dates=parse_dates)
    tm.assert_frame_equal(result, expected)


def test_usecols_with_parse_dates4(all_parsers):
    data = "a,b,c,d,e,f,g,h,i,j\n2016/09/21,1,1,2,3,4,5,6,7,8"
    usecols = list("abcdefghij")
    parse_dates = [[0, 1]]
    parser = all_parsers

    cols = {
        "a_b": "2016/09/21 1",
        "c": [1],
        "d": [2],
        "e": [3],
        "f": [4],
        "g": [5],
        "h": [6],
        "i": [7],
        "j": [8],
    }
    expected = DataFrame(cols, columns=["a_b"] + list("cdefghij"))

    result = parser.read_csv(StringIO(data), usecols=usecols, parse_dates=parse_dates)
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize("usecols", [[0, 2, 3], [3, 0, 2]])
@pytest.mark.parametrize(
    "names",
    [
        list("abcde"),  # Names span all columns in original data.
        list("acd"),  # Names span only the selected columns.
    ],
)
def test_usecols_with_parse_dates_and_names(all_parsers, usecols, names):
    # see gh-9755
    s = """0,1,20140101,0900,4
0,1,20140102,1000,4"""
    parse_dates = [[1, 2]]
    parser = all_parsers

    cols = {
        "a": [0, 0],
        "c_d": [Timestamp("2014-01-01 09:00:00"), Timestamp("2014-01-02 10:00:00")],
    }
    expected = DataFrame(cols, columns=["c_d", "a"])

    result = parser.read_csv(
        StringIO(s), names=names, parse_dates=parse_dates, usecols=usecols
    )
    tm.assert_frame_equal(result, expected)


def test_usecols_with_unicode_strings(all_parsers):
    # see gh-13219
    data = """AAA,BBB,CCC,DDD
0.056674973,8,True,a
2.613230982,2,False,b
3.568935038,7,False,a"""
    parser = all_parsers

    exp_data = {
        "AAA": {0: 0.056674972999999997, 1: 2.6132309819999997, 2: 3.5689350380000002},
        "BBB": {0: 8, 1: 2, 2: 7},
    }
    expected = DataFrame(exp_data)

    result = parser.read_csv(StringIO(data), usecols=["AAA", "BBB"])
    tm.assert_frame_equal(result, expected)


def test_usecols_with_single_byte_unicode_strings(all_parsers):
    # see gh-13219
    data = """A,B,C,D
0.056674973,8,True,a
2.613230982,2,False,b
3.568935038,7,False,a"""
    parser = all_parsers

    exp_data = {
        "A": {0: 0.056674972999999997, 1: 2.6132309819999997, 2: 3.5689350380000002},
        "B": {0: 8, 1: 2, 2: 7},
    }
    expected = DataFrame(exp_data)

    result = parser.read_csv(StringIO(data), usecols=["A", "B"])
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize("usecols", [["AAA", b"BBB"], [b"AAA", "BBB"]])
def test_usecols_with_mixed_encoding_strings(all_parsers, usecols):
    data = """AAA,BBB,CCC,DDD
0.056674973,8,True,a
2.613230982,2,False,b
3.568935038,7,False,a"""
    parser = all_parsers

    with pytest.raises(ValueError, match=_msg_validate_usecols_arg):
        parser.read_csv(StringIO(data), usecols=usecols)


@pytest.mark.parametrize("usecols", [["あああ", "いい"], ["あああ", "いい"]])
def test_usecols_with_multi_byte_characters(all_parsers, usecols):
    data = """あああ,いい,ううう,ええええ
0.056674973,8,True,a
2.613230982,2,False,b
3.568935038,7,False,a"""
    parser = all_parsers

    exp_data = {
        "あああ": {0: 0.056674972999999997, 1: 2.6132309819999997, 2: 3.5689350380000002},
        "いい": {0: 8, 1: 2, 2: 7},
    }
    expected = DataFrame(exp_data)

    result = parser.read_csv(StringIO(data), usecols=usecols)
    tm.assert_frame_equal(result, expected)


def test_empty_usecols(all_parsers):
    data = "a,b,c\n1,2,3\n4,5,6"
    expected = DataFrame()
    parser = all_parsers

    result = parser.read_csv(StringIO(data), usecols=set())
    tm.assert_frame_equal(result, expected)


def test_np_array_usecols(all_parsers):
    # see gh-12546
    parser = all_parsers
    data = "a,b,c\n1,2,3"
    usecols = np.array(["a", "b"])

    expected = DataFrame([[1, 2]], columns=usecols)
    result = parser.read_csv(StringIO(data), usecols=usecols)
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize(
    "usecols,expected",
    [
        (
            lambda x: x.upper() in ["AAA", "BBB", "DDD"],
            DataFrame(
                {
                    "AaA": {
                        0: 0.056674972999999997,
                        1: 2.6132309819999997,
                        2: 3.5689350380000002,
                    },
                    "bBb": {0: 8, 1: 2, 2: 7},
                    "ddd": {0: "a", 1: "b", 2: "a"},
                }
            ),
        ),
        (lambda x: False, DataFrame()),
    ],
)
def test_callable_usecols(all_parsers, usecols, expected):
    # see gh-14154
    data = """AaA,bBb,CCC,ddd
0.056674973,8,True,a
2.613230982,2,False,b
3.568935038,7,False,a"""
    parser = all_parsers

    result = parser.read_csv(StringIO(data), usecols=usecols)
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize("usecols", [["a", "c"], lambda x: x in ["a", "c"]])
def test_incomplete_first_row(all_parsers, usecols):
    # see gh-6710
    data = "1,2\n1,2,3"
    parser = all_parsers
    names = ["a", "b", "c"]
    expected = DataFrame({"a": [1, 1], "c": [np.nan, 3]})

    result = parser.read_csv(StringIO(data), names=names, usecols=usecols)
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize(
    "data,usecols,kwargs,expected",
    [
        # see gh-8985
        (
            "19,29,39\n" * 2 + "10,20,30,40",
            [0, 1, 2],
            dict(header=None),
            DataFrame([[19, 29, 39], [19, 29, 39], [10, 20, 30]]),
        ),
        # see gh-9549
        (
            ("A,B,C\n1,2,3\n3,4,5\n1,2,4,5,1,6\n1,2,3,,,1,\n1,2,3\n5,6,7"),
            ["A", "B", "C"],
            dict(),
            DataFrame(
                {
                    "A": [1, 3, 1, 1, 1, 5],
                    "B": [2, 4, 2, 2, 2, 6],
                    "C": [3, 5, 4, 3, 3, 7],
                }
            ),
        ),
    ],
)
def test_uneven_length_cols(all_parsers, data, usecols, kwargs, expected):
    # see gh-8985
    parser = all_parsers
    result = parser.read_csv(StringIO(data), usecols=usecols, **kwargs)
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize(
    "usecols,kwargs,expected,msg",
    [
        (
            ["a", "b", "c", "d"],
            dict(),
            DataFrame({"a": [1, 5], "b": [2, 6], "c": [3, 7], "d": [4, 8]}),
            None,
        ),
        (
            ["a", "b", "c", "f"],
            dict(),
            None,
            _msg_validate_usecols_names.format(r"\['f'\]"),
        ),
        (["a", "b", "f"], dict(), None, _msg_validate_usecols_names.format(r"\['f'\]")),
        (
            ["a", "b", "f", "g"],
            dict(),
            None,
            _msg_validate_usecols_names.format(r"\[('f', 'g'|'g', 'f')\]"),
        ),
        # see gh-14671
        (
            None,
            dict(header=0, names=["A", "B", "C", "D"]),
            DataFrame({"A": [1, 5], "B": [2, 6], "C": [3, 7], "D": [4, 8]}),
            None,
        ),
        (
            ["A", "B", "C", "f"],
            dict(header=0, names=["A", "B", "C", "D"]),
            None,
            _msg_validate_usecols_names.format(r"\['f'\]"),
        ),
        (
            ["A", "B", "f"],
            dict(names=["A", "B", "C", "D"]),
            None,
            _msg_validate_usecols_names.format(r"\['f'\]"),
        ),
    ],
)
def test_raises_on_usecols_names_mismatch(all_parsers, usecols, kwargs, expected, msg):
    data = "a,b,c,d\n1,2,3,4\n5,6,7,8"
    kwargs.update(usecols=usecols)
    parser = all_parsers

    if expected is None:
        with pytest.raises(ValueError, match=msg):
            parser.read_csv(StringIO(data), **kwargs)
    else:
        result = parser.read_csv(StringIO(data), **kwargs)
        tm.assert_frame_equal(result, expected)


@pytest.mark.xfail(
    reason="see gh-16469: works on the C engine but not the Python engine", strict=False
)
@pytest.mark.parametrize("usecols", [["A", "C"], [0, 2]])
def test_usecols_subset_names_mismatch_orig_columns(all_parsers, usecols):
    data = "a,b,c,d\n1,2,3,4\n5,6,7,8"
    names = ["A", "B", "C", "D"]
    parser = all_parsers

    result = parser.read_csv(StringIO(data), header=0, names=names, usecols=usecols)
    expected = DataFrame({"A": [1, 5], "C": [3, 7]})
    tm.assert_frame_equal(result, expected)
