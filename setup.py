from setuptools import setup, find_packages

with open('README.md') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(
    name="teamo",
    packages=find_packages(),
    license=license,
    url='https://github.com/hassanbot/TeamoPy',
    author='Martin Törnqvist',
    author_email='gris_martin@hotmail.com',
    description='A Discord bot for creating teams',
    long_description=readme,
    version='0.1.0',
    install_requires=[
        'aiosqlite',
        'dateparser',
        'discord.py~=1.4'
    ],
    data_files=[
        ('lists', ['lists/adjectives.list', 'lists/nouns.list'])
    ],
    entry_points={
        'console_scripts': [
            'teamo = teamo.__main__:main'
        ]
    }
)
