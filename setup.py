from setuptools import setup

setup(
        name='nbas',
        version='11.1.1',
        author='Alvin Zhu @ Kignis',
        author_email='alvin.zhuge@gmail.com',
        packages=['nbas'],
        entry_points = {
        "console_scripts": ['nbasm = nbas.__main__:main']
        }
)
