import re
import random
import datetime as dt

import pytz
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

def aggregate_df(df, interval: str):
	sym = df.columns[0][0]
	df = df[sym]
	op_dict = {
		'open': 'first',
		'high':'max',
		'low':'min',
		'close':'last',
		'volume':'sum'
	}
	val = re.sub("[^0-9]", "", interval)
	if interval[-1] == 'N':     # MIN interval
		val = val+'T'
	elif interval[-1] == 'R':   # 1HR interval
		val = 'H'
	else:                       # 1DAY interval
		val = 'D'
	df = df.resample(val).agg(op_dict)
	df.columns = pd.MultiIndex.from_product([[sym], df.columns])

	return df

def now():
	return pytz.utc.localize(dt.datetime.utcnow().replace(microsecond=0, second=0))

def epoch_zero():
	return pytz.utc.localize(dt.datetime(1970, 1, 1))

############ Functions used for testing #################


def gen_data(symbol:str, points: int=50):
	n = now()
	index = [n - dt.timedelta(minutes=1) * i for i in range(points)][::-1]
	df = pd.DataFrame(index=index, columns=['low', 'high', 'close', 'open', 'volume'])
	df['low'] = [random.random() for _ in range(points)]
	df['high'] = [random.random() for _ in range(points)]
	df['close'] = [random.random() for _ in range(points)]
	df['open'] = [random.random() for _ in range(points)]
	df['volume'] = [random.random() for _ in range(points)]
	#df.index = normalize_pands_dt_index(df)
	df.columns = pd.MultiIndex.from_product([[symbol], df.columns])
	
	return df