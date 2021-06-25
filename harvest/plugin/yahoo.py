import pandas as pd

import harvest.plugin._base as base

class YahooEarningPlugin(base.Plugin):
    """
    Uses a scraper to get earning report dates from the Yahoo Finance website.
    WARNING: Yahoo also lists *predicted* dates, so future dates may not be accurate.
    NOTE: The first entry is the date a day after the company IPO'ed (first day on market).    
    """
    yec = None

    def set_func(self, trader) -> None:
        trader.plugins.fetch_earning_dates = self.fetch_earning_dates

    def fetch_earning_dates(self, ticker) -> pd.DataFrame:
        if self.yec == None:
            from yahoo_earnings_calendar import YahooEarningsCalendar
            self.yec = YahooEarningsCalendar()
        ret = self.yec.get_earnings_of(ticker)
        #ret = json.dumps(ret, indent=2)
        df = pd.DataFrame.from_dict(ret)
        df['date'] = pd.to_datetime(df['startdatetime'])
        df.set_index('date', inplace=True)
        df.index = df.index.tz_localize(None) 
        df = df[['ticker', 'epsestimate', 'epsactual']]

        return df 