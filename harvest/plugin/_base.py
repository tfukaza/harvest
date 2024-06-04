import sys
from typing import List


class Plugin:
    """
    As the name implies, it implements funtionalities that the Trader class
    alone cannot support, like retrieving earning report dates.

    The name of the plugin will follow the format:
        {Name of source}{Functionality added}Plugin
    """

    def __init__(self, name: str, dependencies: List[str]):
        """
        :name: a string that will serve as the name of the plugin. Must
        be a valid python variable because in the algo class, this plugin
        will be an attribute of the algo and accessible via algo.name.
        :dependencies: a list of python packages as strings that will be
        checked to ensure they are installed.
        Put all imports here in order to test if we have them. If not then
        error and call the installation function.
        """
        self.name = name
        for dep in dependencies:
            if dep not in sys.modules:
                raise ImportError(f"Missing dependency: {dep}. Run the installation steps.")

    def installation(self) -> str:
        """
        Returns how to install the necessary prerequisites for this plugin.
        """
        raise NotImplementedError(f"No installation steps for plugin: {type(self).__name__}")
