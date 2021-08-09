import subprocess
from setuptools import Command, setup

class CoverageTestCMD(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        subprocess.run(['coverage', 'run', '--source', 'harvest', '-m', 'unittest', 'discover', '-s', 'tests'])
        subprocess.run(['coverage', 'report'])
        subprocess.run(['coverage', 'html'])
        
setup(
    cmdclass={
        'test': CoverageTestCMD,
    },
)