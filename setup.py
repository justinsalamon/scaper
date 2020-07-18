from setuptools import setup
import imp


with open('README.md') as file:
    long_description = file.read()

version = imp.load_source('scaper.version', 'scaper/version.py')

setup(
    name='scaper',
    version=version.version,
    description='A library for soundscape synthesis and augmentation',
    author='Justin Salamon & Duncan MacConnell',
    author_email='justin.salamon@gmail.com',
    url='https://github.com/justinsalamon/scaper',
    download_url='http://github.com/justinsalamon/scaper/releases',
    packages=['scaper'],
    long_description=long_description,
    long_description_content_type='text/markdown',
    keywords='audio sound soundscape environmental dsp mixing',
    license='BSD-3-Clause',
    classifiers=[
            "License :: OSI Approved :: BSD License",
            "Programming Language :: Python",
            "Development Status :: 3 - Alpha",
            "Intended Audience :: Developers",
            "Intended Audience :: Science/Research",
            "Topic :: Multimedia :: Sound/Audio :: Analysis",
            "Topic :: Multimedia :: Sound/Audio :: Sound Synthesis",
            "Programming Language :: Python :: 2",
            "Programming Language :: Python :: 2.7",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.4",
            "Programming Language :: Python :: 3.5",
            "Programming Language :: Python :: 3.6",
        ],
    install_requires=[
        'sox>=1.3.3',
        'jams>=0.3.2',
        'numpy>=1.13.3',
        'soundfile'
    ],
    extras_require={
        'docs': [
                'sphinx',  # autodoc was broken in 1.3.1
                'sphinx_rtd_theme',
                'sphinx_issues',
            ],
        'tests': ['backports.tempfile', 'pytest', 'pytest-cov', 'tqdm']
    }
)
