import setuptools

with open('README.md', 'r') as f:
    long_description = f.read()

setuptools.setup(
    name='wg_utilities',
    version='0.0.1',
    author='Will Garside',
    author_email='worgarside@gmail.com',
    description='Utilities for the using in personal projects.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/worgarside/wg-utilities',
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    install_requires=[]
)
