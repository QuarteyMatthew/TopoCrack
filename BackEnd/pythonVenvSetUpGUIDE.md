# Setting up a venv (virtual environment) in python

## Installing python

Before installing python, check if it is already installed on your machine:

```bash
python --version
```

If python isn't installed, go to [python.org]("www.python.org") to download it and install it.

## Creating a venv

```bash
python -m venv .venv
```

Change ".venv" with your preferred name for the directory containing the venv.

## Activating the venv

```bash
# On windows:
.venv\Scripts\activate
# or, if on linux:
source projectname/bin/activate
```

If you want to try installing a package, try:

```bash
pip install cowsay
```

And then try to run a .py file with

> include cowsay
> In it, and if no errors occour, you have done everything correctly.

## Deactivating a venv

```bash
deactivate
```

Now, if you try to run the file you just ran successfully, it shouldn't work (if cowsay isn't installed in the global version of Python) since you have just exited the venv in whitch cowsay is installed.

## Deleting a venv

To delete a venv, just delete its folder (in this example, ".venv\").
