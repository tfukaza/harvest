import subprocess
from setuptools import Command, setup


class LintCMD(Command):
    user_options = [
        ('check=', 'c', 'if True check if files pass linting checks; don\'t actually lint')
    ]

    def initialize_options(self):
        self.check = False

    def finalize_options(self):
        self.check = self.check == 'True'

    def run(self):
<<<<<<< HEAD
        subprocess.run(["black", "harvest"])

=======
        command = ['black', 'harvest']

        if self.check:
            command.append('--check')

        exit(subprocess.run(command).returncode)
>>>>>>> main

class CoverageTestCMD(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
<<<<<<< HEAD
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

=======
        a = subprocess.run(['coverage', 'run', '--source', 'harvest', '--omit', 'harvest/api/robinhood.py,harvest/api/alpaca.py', '-m', 'unittest', 'discover', '-s', 'tests']).resturncode
        b = subprocess.run(['coverage', 'report']).returncode
        c = subprocess.run(['coverage', 'html']).returncode
        exit(a + b + c)
>>>>>>> main

setup(
    cmdclass={
        "lint": LintCMD,
        "test": CoverageTestCMD,
    },
    include_package_data=True,
)
