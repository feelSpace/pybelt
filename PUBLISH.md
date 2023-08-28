## To publish pyBelt on PyPI

### Prerequisite

```
$ pip install twine
$ pip install wheel
```

### Update version

In `setup.py` update the version.

### Building package

```
$ python setup.py sdist bdist_wheel
```

The '.tar.gz' archive in 'dist' must be check to see if it contains the files to publish.

### Testing package

```
$ python -m twine check dist/*
```

### Upload on test PyPI

```
$ twine upload --repository-url https://test.pypi.org/legacy/ dist/*
```

To be checked on: https://test.pypi.org/

### Check install

```
$ pip install --index-url https://test.pypi.org/simple/ pybelt
```

Can be uninstalled using:

```
$ pip uninstall pybelt
```

### Upload on PyPI

```
$ twine upload dist/*
```

To be checked on: https://pypi.org/

### Check install

```
$ pip install pybelt
```



