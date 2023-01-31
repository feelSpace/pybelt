import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pybelt",
    version="1.0.5",
    author="feelSpace GmbH",
    author_email="dev@feelspace.de",
    description="An Python library to control the feelSpace naviBelt from your application",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/feelSpace/pybelt",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.3',
    install_requires=["pyserial", "bleak"],
)