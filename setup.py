import setuptools

with open('README.md', 'r') as readme:
    long_desc = readme.read()

with open('requirements.txt', 'r') as reqf:
    requirements = reqf.read().splitlines()

with open('version.txt', 'r') as verf:
    version = verf.read().strip()
if not version:
    raise RuntimeError('version is not set')

extras_require = {
    'twitch': 'twitchio>=1.0.0'
}

setuptools.setup(
    name='pikalaxbot',
    version=version,
    author='PikalaxALT',
    author_email='pikalaxalt@gmail.com',
    license='GPLv3',
    include_package_data=True,
    description='Combination Discord Bot and Twitch WIP Bot.',
    long_description=long_desc,
    long_description_content_type='text/markdown',
    url='https://github.com/PikalaxALT/pikalaxbot',
    packages=['pikalaxbot', 'pikalaxbot.ext.twitch'],
    install_requires=requirements,
    extras_require=extras_require,
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3.7',
        'Operating System :: OS Independent',
        'Natural Language :: English',
        'Topic :: Internet',
        'Topic :: Utilities',
        'Topic :: Communications :: Chat'
    ]
)
