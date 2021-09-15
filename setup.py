import subprocess
from setuptools import Command, setup


class LintCMD(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        subprocess.run(["black", "harvest"])


class CoverageTestCMD(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        subprocess.run(
            [
                "coverage",
                "run",
                "--source",
                "harvest",
                "--omit",
                "harvest/api/robinhood.py,harvest/api/alpaca.py",
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
            ]
        )
        subprocess.run(["coverage", "report"])
        subprocess.run(["coverage", "html"])


setup(
    cmdclass={
        "lint": LintCMD,
        "test": CoverageTestCMD,
    },
    include_package_data=True,
)
