from distutils.core import setup

# noinspection SpellCheckingInspection
setup(
    name='radiora',
    version='1.0',
    packages=['radiora'],
    url='https://github.com/ralphlipe/',
    license='BSD',
    author='Ralph Lipe',
    author_email='ralph@lipe.ws',
    description='Lutron RadioRA Chronos System Support',
    classifiers=[
                'Development Status :: 5 - Production/Stable',
                'Intended Audience :: Developers',
                'Intended Audience :: End Users/Desktop',
                'License :: OSI Approved :: BSD License',
                'Natural Language :: English',
                'Operating System :: POSIX',
                'Operating System :: Microsoft :: Windows',
                'Operating System :: MacOS :: MacOS X',
                'Programming Language :: Python',
                'Programming Language :: Python :: 3',
                'Programming Language :: Python :: 3.2',
                'Programming Language :: Python :: 3.3',
                'Programming Language :: Python :: 3.4',
                'Programming Language :: Python :: 3.5',
                'Programming Language :: Python :: 3.6',
                'Topic :: Home Automation',
                'Topic :: Software Development :: Libraries',
                'Topic :: Software Development :: Libraries :: Python Modules',
                ],
    platforms='any',
    requires=['pyserial']
)
