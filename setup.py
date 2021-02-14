from setuptools import setup
import os

desc = open("readme.rst").read() if os.path.isfile("readme.rst") else ""


setup(
    name='flask_datatables',
    version='0.6.18',
    packages=['flask_datatables', 'flask_datatables.views'],
    url='https://github.com/tahoe/flask_datatables/',
    download_url='https://github.com/tahoe/flask_datatables/tarball/0.6.15',
    license='MIT',
    long_description=desc,
    keywords='datatables sqlalchemy flask',
    author='Dennis Durling',
    author_email='djdtahoe@gmail.com',
    description='Integrates SQLAlchemy with DataTables (framework Flask)',
    zip_safe=False,
    include_package_data=True,
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Flask',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    install_requires=[
        'querystring_parser==1.2.3',
        'sqlalchemy>=1.0.11',
        'flask>=0.10.1',
        'flask-restful>=0.3.5',
        'Faker==0.7.12',
    ],
)
