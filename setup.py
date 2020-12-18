import setuptools
import re

with open('README.md', 'r') as readme:
    long_desc = readme.read()

with open('requirements.txt', 'r') as reqf:
    requirements = reqf.read().splitlines()

version = ''
with open('discord/__init__.py') as f:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', f.read(), re.MULTILINE).group(1)

if not version:
    raise RuntimeError('version is not set')

if version.endswith(('a', 'b', 'rc')):
    # append version identifier based on commit count
    try:
        import subprocess
        p = subprocess.Popen(['git', 'rev-list', '--count', 'HEAD'],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        if out:
            version += out.decode('utf-8').strip()
        p = subprocess.Popen(['git', 'rev-parse', '--short', 'HEAD'],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        if out:
            version += '+g' + out.decode('utf-8').strip()
    except Exception:
        pass

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
    packages=['pikalaxbot'],
    install_requires=requirements,
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
