from setuptools import find_packages, setup
setup(
    name='harvest',
    packages=find_packages(include=['harvest', 'harvest.plugin', 'harvest.broker', 'harvest.trader']),
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
        "TDAmeritrade": [
            'selenium',
            'splinter',
            'requests',
            'PyVirtualDisplay',
            'tda-api==1.1.0'
        ],
        "AlpacaMarket": [
            'alpaca-trade-api'
        ],
        "Robinhood":[
            'pyotp',
            'robin_stocks'
        ]
    }
)