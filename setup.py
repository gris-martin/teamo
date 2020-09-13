from setuptools import setup, find_packages

with open('README.md', encoding='utf8') as f:
    readme = f.read()

with open('LICENSE', encoding='utf8') as f:
    license = f.read()

with open('VERSION', encoding='utf8') as f:
    version = f.read()

setup(
    name="teamo",
    packages=find_packages(),
    license=license,
    url='https://github.com/hassanbot/TeamoPy',
    author='Martin Törnqvist',
    author_email='gris_martin@hotmail.com',
    description='A Discord bot for creating teams',
    long_description=readme,
    version=version,
    install_requires=[
        'aiosqlite',
        'dateparser',
        'discord.py~=1.4',
        'python-dotenv'
    ],
    data_files=[
        ('resources', ['resources/adjectives.list', 'resources/nouns.list', 'resources/.env'])
    ],
    entry_points={
        'console_scripts': [
            'teamo = teamo.__main__:main'
        ]
    }
)
