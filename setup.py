# setup.py
from setuptools import setup, find_packages

setup(
    name="plutonium",
    version="0.1.0",
    description="Dependency analyzer for multiple programming environments",
    author="Justin Lietz",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "requests",
        "jsonschema",
    ],
    entry_points={
        'console_scripts': [
            'plutonium=plutonium.main:main',
        ],
    },
    python_requires='>=3.6',
)