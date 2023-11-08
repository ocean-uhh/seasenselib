from setuptools import setup, find_packages

setup(
    name='ctd-tools',
    version='0.1',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'ctd-tools=ctd_tools.__main__:main'
        ]
    },
    install_requires=[
        'pycnv',
        'pandas',
        'xarray',
        'numpy',
        'scipy',
        'pylablib',
        'matplotlib',
        'netcdf4',
    ],
    # Additional metadata about your package.
    description='Read, convert, and plot Seabird CNV files.',
    long_description=open('README.md').read(),
    author='The CTD Tools team',
    license='MIT',
    url='https://gitlab.rrz.uni-hamburg.de/ifmeo-sea-practical/ctd-tools',
)