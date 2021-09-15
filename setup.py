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
        command = ['black', 'harvest']

        if self.check:
            command.append('--check')

        subprocess.run(command)

class CoverageTestCMD(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        subprocess.run(['coverage', 'run', '--source', 'harvest', '--omit', 'harvest/api/robinhood.py,harvest/api/alpaca.py', '-m', 'unittest', 'discover', '-s', 'tests'])
        subprocess.run(['coverage', 'report'])
        subprocess.run(['coverage', 'html'])

setup(
    cmdclass={
        'lint': LintCMD,
        'test': CoverageTestCMD,
    },
    include_package_data=True
)
