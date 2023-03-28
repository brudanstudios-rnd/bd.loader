name = "bd.loader"

version = "0.0.1"

build_command = "python -m rezutil build {root} --ignore .env"
private_build_requires = ["rezutil"]

requires = ["appdirs", "arrow", "bd.context", "bd.hooks"]


def commands():
    env.PYTHONPATH.prepend("{root}/python")
    if "bd.maya" in resolve:
        env.BD_HOOKPATH.append("{root}/hooks/maya")
        env.XBMLANGPATH.append("{root}/icons")
