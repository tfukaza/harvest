import pandas as pd

from harvest.plugin._base import Plugin


class DoltOptionsPlugin:
    """
    Interfaces with the Dolt CLI to get data from the
    `https://www.dolthub.com/repositories/post-no-preference/options`
    database.
    """

    def __init__(self, name: str = "dolt_options", path: str = "options"):
        """
        :path: The path to the post-no-preference/options repo.
        """
        super.__init__(name, ["doltpy"])
        from doltpy.cli import Dolt
        from doltpy.cli import read

        self.dolt = Dolt(path)
        self.read = read

    def installation(self) -> str:
        """
        Returns how to install the necessary prerequsites for this plugin.
        """
        return """
        Useful Links:
        https://www.dolthub.com/
        https://github.com/dolthub/doltpy

        Install dolt (*nix):
        sudo curl -L https://github.com/dolthub/dolt/releases/latest/download/install.sh | sudo bash

        Get post-no-preference/options repo:
        dolt clone post-no-preference/options

        Install doltpy:
        pip install doltpy
        """

    # -------------- Plugin specific methods -------------- #

    def query(self, query: str) -> pd.DataFrame:
        return self.read.read_pandas_sql(self.dolt, query)
