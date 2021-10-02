import subprocess
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
            command.append("--check")

        exit(subprocess.run(command).returncode)


class CoverageTestCMD(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        a = subprocess.run(
            ["coverage", "run", "-m", "unittest", "discover", "-s", "tests"]
        ).returncode
        b = subprocess.run(["coverage", "report"]).returncode
        c = subprocess.run(["coverage", "html"]).returncode
        exit(a + b + c)


setup(
    cmdclass={
        "lint": LintCMD,
        "test": CoverageTestCMD,
    },
    include_package_data=True,
)
