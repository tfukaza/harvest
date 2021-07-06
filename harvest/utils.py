import re
import datetime as dt

import pandas as pd

def interval_to_timedelta(interval: str):
	time_search = re.search('([0-9]+)(MIN|HR|DAY)', interval)
	expanded_units = {
		'DAY': 'days',
		'HR': 'hours',
		'MIN': 'minutes'
	}

	value, unit = int(time_search.group(1)), expanded_units[time_search.group(2)]
	params = {unit: value}
	return dt.timedelta(**params)


def is_crypto(symbol: str):
	return symbol[0] == '@'

def normalize_pands_dt_index(df: pd.DataFrame):
	return df.index.floor('min')