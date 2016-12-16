from setuptools import setup, find_packages

with open('README.md') as file:
    long_description = file.read()

setup(
    name='scaper',
    version='0.1.0',
    description='Soundscape generation with JAMS annotations',
    author='Justin Salamon & Duncan MacConnell',
    author_email='justin.salamon@gmail.com',
    url='https://github.com/justinsalamon/scaper',
    packages=find_packages(),
    package_data={'': ['namespaces/sound_event.json']},
    include_package_data=True,
    long_description=long_description,
    keywords='audio sound soundscape environmental dsp mixing',
    license='GPL',
    install_requires=[
        'sox >= 1.1.2',
        'jams >= 0.2.0'
    ]
)
