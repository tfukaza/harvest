import re
import datetime as dt

import pandas as pd

def expand_interval(interval: str):
	time_search = re.search('([0-9]+)(MIN|HR|DAY)', interval)
	value = int(time_search.group(1))
	unit = time_search.group(2)

	return value, unit

def interval_to_timedelta(interval: str):
	expanded_units = {
		'DAY': 'days',
		'HR': 'hours',
		'MIN': 'minutes'
	}

	value, unit = expand_interval(interval)
	params = {expanded_units[unit]: value}
	return dt.timedelta(**params)


def is_crypto(symbol: str):
	return symbol[0] == '@'

def normalize_pands_dt_index(df: pd.DataFrame):
	return df.index.floor('min')