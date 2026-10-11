from pathlib import Path
import sys
import pandas as pd
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ml'))

@pytest.fixture(scope='session')
def frame():return pd.read_csv(ROOT/'examples/example_internal_input.csv')

@pytest.fixture
def manager(tmp_path):
    from service import Manager
    m=Manager('pytest',ROOT/'examples/example_internal_input.csv',tmp_path)
    yield m
    m.close()
