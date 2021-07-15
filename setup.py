import subprocess
from setuptools import Command, find_packages, setup

class CoverageTestCMD(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        subprocess.run(['coverage', 'run', '--source', 'harvest', '-m', 'unittest', 'discover', '-s', 'test'])
        subprocess.run(['coverage', 'report'])
        subprocess.run(['coverage', 'html'])
        

setup(
    name='harvest',
    packages=['harvest', 'harvest.trader', 'harvest.api', 'harvest.storage'],
    version='0.1.0',
    description='A framework providing a high-level interface for algorithmic trading.',
    author='Harvest Team',
    license='MIT',
    cmdclass={
        'test': CoverageTestCMD,
    },
    install_requires=[
        'pandas',
        'finta',
        'pyyaml',
        'tqdm',
        'pytz'
    ],
    extras_require={
        "AlpacaMarket": [
            'alpaca-trade-api'
        ],
        "Robinhood": [
            'pyotp',
            'robin_stocks'
        ],
        "Yahoo": [ 
            "yfinance"
        ]
    }
)