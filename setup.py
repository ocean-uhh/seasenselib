from setuptools import setup, find_packages

setup(
    name='ctd-tools',
    version='0.1.0',
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
    classifiers=[
        # Classifiers help users find the package.
        # Full list: https://pypi.org/classifiers/
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Operating System :: OS Independent',
        'Topic :: Scientific/Engineering :: Oceanography',
        'Intended Audience :: Science/Research',
        'Intended Audience :: Developers',
        'Natural Language :: English'
    ],
    project_urls = {
        'Source Code': 'https://gitlab.rrz.uni-hamburg.de/ifmeo-sea-practical/ctd-tools',
    },
    # Additional metadata about your package.
    description='Read, convert, and plot CTD data of Seabird CNV files.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Yves Sorge',
    license='MIT',
    url='https://gitlab.rrz.uni-hamburg.de/ifmeo-sea-practical/ctd-tools',
    download_url='https://pypi.org/project/ctd-tools/',
)