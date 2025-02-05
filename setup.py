from setuptools import setup, find_packages

setup(
    name='clembench',
    version='0.1',
    packages=find_packages(),
    install_requires=[], #tbd
    entry_points={
        'console_scripts': [
            'clem=clemcore.cli:main',
        ],
    },
    include_package_data=True,
    description="The cLLM (chat-optimized Large Language Model, 'clem') framework tests such models' ability "
                "to engage in games, that is, rule-constituted activities played using language.",
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Philipp Sadler',
    author_email='first.last@uni-potsdam.de',
    url='https://github.com/clp-research/clembench',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)
