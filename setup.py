from setuptools import setup, find_packages


setup(
    name="docker_xylem",
    version='0.1.9',
    url='http://github.com/praekeltfoundation/docker-xylem',
    license='MIT',
    description="A docker storage plugin",
    author='Colin Alston',
    author_email='colin@praekelt.com',
    packages=find_packages() + [
        "twisted.plugins",
    ],
    package_data={
        'twisted.plugins': ['twisted/plugins/docker_xylem_plugin.py']
    },
    include_package_data=True,
    install_requires=[
        'Twisted',
        'pyyaml'
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Topic :: System :: Distributed Computing',
    ],
)
