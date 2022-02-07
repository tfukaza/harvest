import subprocess
from glob import glob
from setuptools import Command, setup


class LintCMD(Command):
    user_options = [
        (
            "check=",
            "c",
            "if True check if files pass linting checks; don't actually lint",
        )
    ]

    def initialize_options(self):
        self.check = False

    def finalize_options(self):
        self.check = self.check == "True"

    def run(self):
        command = ["black", "harvest"]

        if self.check:
            command.extend(["--check", "-v", "--diff"])

        exit(subprocess.run(command).returncode)


class CoverageTestCMD(Command):
    user_options = [("live=", "l", "a list of files in the livetest folder to run")]

    def initialize_options(self):
        self.live = ""

    def finalize_options(self):
        self.live = ["tests/livetest/test_api_" + test + ".py" for test in self.live.split(',')]

    def run(self):
        exit_code = subprocess.run(
            ["coverage", "run", "-p", "-m", "unittest", "discover", "-s", "tests/unittest"]
        ).returncode

        for test in self.live:
            exit_code += subprocess.run(
                ["coverage", "run", "-p", test]
            ).returncode

        exit_code += subprocess.run(["coverage", "combine"] + glob(".coverage.*")).returncode
        exit_code += subprocess.run(["coverage", "report"]).returncode
        exit_code += subprocess.run(["coverage", "html"]).returncode
        exit(exit_code)


setup(
    cmdclass={
        "lint": LintCMD,
        "test": CoverageTestCMD,
    },
    include_package_data=True,
)
