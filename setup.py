from setuptools import find_packages, setup
setup(
    name='harvest',
    packages=['harvest', 'harvest.trader', 'harvest.broker'],
    version='0.1.0',
    description='A framework providing a high-level interface for algorithmic trading.',
    author='Tomoki T. Fukazawa',
    license='MIT',
    install_requires=[
        'pandas',
        'finta',
        'yahoo-earnings-calendar',
        'pyyaml',
        'tqdm',
        'pytz'
    ],
    extras_require={
        "AlpacaMarket": [
            'alpaca-trade-api'
        ],
        "Robinhood":[
            'pyotp',
            'robin_stocks'
        ]
    }
)